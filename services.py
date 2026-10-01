import os
import re
import json
import math

from dotenv import load_dotenv

load_dotenv()

import chromadb  # noqa: E402
from faster_whisper import WhisperModel  # noqa: E402
from langchain_core.output_parsers import StrOutputParser  # noqa: E402
from langchain_core.prompts import ChatPromptTemplate  # noqa: E402
from langchain_openai import ChatOpenAI, OpenAIEmbeddings  # noqa: E402
from langchain_text_splitters import RecursiveCharacterTextSplitter  # noqa: E402

from schemas import MeetingAnalysis  # noqa: E402

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
LLM = ChatOpenAI(model=MODEL, temperature=0)
STRUCTURED_LLM = LLM.with_structured_output(MeetingAnalysis)

EXTRACT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an information extraction engine for meeting transcripts.\n"
            "Your job is to convert the transcript into the MeetingAnalysis schema as accurately as possible.\n"
            "Use only facts stated in the transcript. Never invent names, dates, decisions, or tasks.\n"
            "If a field is not supported by the transcript, return an empty list or null-equivalent value instead of guessing.\n\n"
            "Extraction rules:\n"
            "1. summary: write 2 to 4 sentences that cover the meeting purpose, the main decisions, and the main follow-ups.\n"
            "2. decisions: include only final decisions or commitments that were actually agreed upon. Do not include discussion points or proposals.\n"
            "3. action_items: create one item per distinct task or follow-up. Use a short verb phrase for task, for example 'Complete payment API integration'.\n"
            "   - assignee: include only if the transcript clearly names the responsible person.\n"
            "   - deadline: keep the deadline exactly as stated when possible, for example '15 September' or 'tomorrow'.\n"
            "   - priority: use high for urgent or blocking items, medium for normal follow-ups, and low for minor or informational items.\n"
            "   - status: use open unless the transcript explicitly says the item is done, complete, resolved, or closed.\n"
            "   - confidence: use a number from 0 to 1 to reflect how clearly the item is stated in the transcript.\n"
            "4. risks_blockers: include only explicit risks, blockers, or issues that may prevent progress.\n"
            "5. unresolved_items: include topics that were deferred, still not decided, or still being discussed.\n"
            "6. participants: include only clearly identified speakers or named participants. Remove duplicates.\n"
            "7. confidence: provide an overall confidence score from 0 to 1 for the quality of the extracted analysis.\n\n"
            "Normalization rules:\n"
            "- Keep dates and deadlines in the same wording as the transcript when possible.\n"
            "- Merge repeated action items that mean the same thing.\n"
            "- Prefer concrete commitments over vague suggestions.\n"
            "- If the transcript contains multiple mentions of the same decision, keep one clean version.\n"
            "- Do not add commentary, explanations, or markdown. Return only structured data through the schema.",
        ),
        ("user", "Transcript:\n{transcript}"),
    ]
)

ANSWER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a meeting question-answering assistant.\n"
            "Answer only from the provided meeting analysis and transcript excerpts.\n"
            "Do not use outside knowledge or guess missing details.\n"
            "If the answer is not explicitly supported by the inputs, say it is not available.\n\n"
            "How to answer:\n"
            "- Be direct and concise.\n"
            "- Prefer short factual sentences or bullets.\n"
            "- When the user asks who, return the named person or people.\n"
            "- When the user asks what tasks were assigned, list the action items that match the question.\n"
            "- When the user asks about deadlines, return the deadline exactly as stated when possible.\n"
            "- When the user asks about decisions, return only final decisions or commitments.\n"
            "- When the user asks about blockers or unresolved topics, return the explicit blocker or unresolved issue.\n"
            "- If multiple excerpts support the answer, combine them into one clean response.\n"
            "- If the transcript suggests something is still open, mention that it remains open rather than pretending it is resolved.\n\n"
            "Common question patterns to handle well:\n"
            "1. 'What tasks were assigned to Rahul?' -> list only Rahul's assigned action items.\n"
            "2. 'What are the deadlines?' -> list the deadlines mentioned in the meeting, grouped by task if helpful.\n"
            "3. 'What decisions were finalized?' -> list final decisions only, not discussion or proposals.\n"
            "4. 'What blockers are still open?' -> list unresolved risks, blockers, or open issues.\n"
            "5. 'Why is pricing still unresolved?' -> explain only if the analysis or excerpts explicitly mention pricing being deferred or not finalized; otherwise say it is not available.",
        ),
        (
            "user",
            "Meeting analysis:\n{analysis}\n\n"
            "Transcript excerpts:\n{context}\n\n"
            "User question:\n{question}\n\n"
            "Answer using only the evidence above.",
        ),
    ]
)


def extract_analysis(transcript):
    chain = EXTRACT_PROMPT | STRUCTURED_LLM
    analysis = chain.invoke({"transcript": transcript})
    analysis.action_items = dedupe_action_items(analysis.action_items)
    return analysis


def dedupe_action_items(action_items):
    seen = set()
    unique_items = []
    for item in action_items:
        key = _action_item_key(item)
        if key in seen:
            continue
        seen.add(key)
        unique_items.append(item)
    return unique_items


def _action_item_key(item):
    return (
        re.sub(r"\s+", " ", item.task).strip().lower(),
        (item.assignee or "").strip().lower(),
        (item.deadline or "").strip().lower(),
    )


def answer_question(question, analysis, chunks):
    if hasattr(analysis, "model_dump_json"):
        analysis_text = analysis.model_dump_json(indent=2)
    else:
        analysis_text = json.dumps(analysis, indent=2, ensure_ascii=False)

    chain = ANSWER_PROMPT | LLM | StrOutputParser()
    return chain.invoke(
        {
            "analysis": analysis_text,
            "context": "\n\n".join(chunks),
            "question": question,
        }
    ).strip()


class TranscriptionService:
    def __init__(self):
        self.model = WhisperModel(os.getenv("WHISPER_MODEL", "base"), device="cpu", compute_type="int8")

    def transcribe(self, audio_path):
        segments, _ = self.model.transcribe(audio_path, beam_size=5)
        return " ".join(segment.text.strip() for segment in segments).strip()


class RetrievalService:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=os.getenv("CHROMA_DIR", "chroma_store"))
        self.embedding_fn = OpenAIEmbeddings(model="text-embedding-3-small")
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=600,
            chunk_overlap=120,
            separators=["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " "],
        )
        self.min_score = float(os.getenv("RETRIEVAL_MIN_SCORE", "0.32"))
        self.max_similarity = float(os.getenv("RETRIEVAL_MAX_CHUNK_SIMILARITY", "0.88"))

    def collection(self, meeting_id):
        return self.client.get_or_create_collection(f"meeting_{meeting_id}")

    def index(self, meeting_id, transcript):
        chunks = self.splitter.split_text(transcript)
        if chunks:
            embeddings = self.embedding_fn.embed_documents(chunks)
            self.collection(meeting_id).add(
                ids=[f"{meeting_id}_{i}" for i in range(len(chunks))],
                documents=chunks,
                embeddings=embeddings,
                metadatas=[{"chunk_index": i} for i in range(len(chunks))],
            )

    def search(self, meeting_id, question, top_k=3):
        query_embedding = self.embedding_fn.embed_query(question)
        candidate_count = max(top_k * 4, top_k)
        result = self.collection(meeting_id).query(
            query_embeddings=[query_embedding],
            n_results=candidate_count,
        )
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]

        ranked = self._rerank_chunks(question, query_embedding, documents, metadatas)
        filtered = [item for item in ranked if item[3] >= self.min_score]
        if not filtered:
            filtered = ranked[:1]

        chosen = self._select_diverse_chunks(filtered, top_k)
        return [item[1] for item in chosen], [f"chunk_{item[0]}" for item in chosen]

    def _rerank_chunks(self, question, query_embedding, documents, metadatas):
        query_tokens = set(self._tokenize(question))
        document_embeddings = self.embedding_fn.embed_documents(documents) if documents else []

        scored = []
        for index, document, document_embedding in zip(range(len(documents)), documents, document_embeddings):
            semantic_score = self._cosine_similarity(query_embedding, document_embedding)
            lexical_score = self._lexical_overlap(query_tokens, document)
            score = (semantic_score * 0.75) + (lexical_score * 0.25)
            chunk_index = metadatas[index].get("chunk_index", index) if index < len(metadatas) else index
            scored.append((chunk_index, document, document_embedding, score))

        scored.sort(key=lambda item: item[3], reverse=True)
        return scored

    def _select_diverse_chunks(self, ranked_chunks, top_k):
        chosen = []
        for candidate in ranked_chunks:
            if len(chosen) >= top_k:
                break

            candidate_embedding = candidate[2]
            if any(self._cosine_similarity(candidate_embedding, item[2]) >= self.max_similarity for item in chosen):
                continue

            chosen.append(candidate)

        if not chosen and ranked_chunks:
            return ranked_chunks[:top_k]

        return chosen

    def _tokenize(self, text):
        return re.findall(r"[a-z0-9]+", text.lower())

    def _lexical_overlap(self, query_tokens, document):
        if not query_tokens:
            return 0.0
        document_tokens = set(self._tokenize(document))
        return len(query_tokens & document_tokens) / len(query_tokens)

    def _cosine_similarity(self, left, right):
        numerator = sum(l * r for l, r in zip(left, right))
        left_magnitude = math.sqrt(sum(value * value for value in left))
        right_magnitude = math.sqrt(sum(value * value for value in right))
        if not left_magnitude or not right_magnitude:
            return 0.0
        return numerator / (left_magnitude * right_magnitude)


transcriber = TranscriptionService()
retriever = RetrievalService()
