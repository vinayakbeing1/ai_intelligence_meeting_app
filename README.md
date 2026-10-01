# AI Meeting Intelligence & Action Tracker

An AI-powered meeting assistant that turns uploaded audio into a searchable, structured meeting record.

The application accepts a meeting recording, transcribes it, extracts decisions and action items, stores the result in SQLite, indexes transcript chunks in ChromaDB, and lets users ask natural-language questions about the meeting.

---

## Project Concept

Meetings contain a lot of useful information, but most of it is buried inside long audio recordings. This project automates the full workflow:

1. upload an audio file
2. transcribe the recording
3. extract meeting intelligence with an LLM
4. store the transcript and structured output
5. retrieve relevant transcript chunks for follow-up questions
6. present everything in a browser UI

It is designed to be a practical backend-first application with a simple dashboard on top.

---

## What The App Produces

For each meeting, the system tries to extract:

* summary
* decisions
* action items
* assignees
* deadlines
* priority
* status
* risks and blockers
* unresolved items
* participants
* confidence score

This makes the output usable for search, review, and follow-up work.

---

## Workflow

```text
Audio upload
    ↓
Saved locally in uploads/
    ↓
Background worker picks up the job
    ↓
Faster-Whisper transcribes the recording
    ↓
LangChain + OpenAI extracts structured meeting data
    ↓
SQLite stores transcript, summary, and analysis
    ↓
ChromaDB stores transcript chunks and embeddings
    ↓
User queries the meeting through the UI or API
```

---

## Techniques Used

### 1. Background queue processing

Uploads do not block the API. The request returns quickly and a worker thread processes the meeting in the background.

### 2. Speech-to-text transcription

The app uses Faster-Whisper to convert the uploaded audio into a text transcript.

### 3. LLM-based structured extraction

The transcript is passed through a carefully written extraction prompt. The output is validated using a Pydantic schema so the result stays structured and predictable.

### 4. LangChain prompt handling

LangChain is used for:

* chat model calls
* structured output generation
* prompt composition
* retrieval embedding calls

### 5. Semantic retrieval with reranking

The retrieval layer uses ChromaDB plus embeddings. To improve accuracy, the app now:

* splits transcripts into sentence-aware chunks
* retrieves more candidate chunks than the final answer needs
* reranks chunks using semantic similarity and lexical overlap
* filters weak matches with a minimum score threshold
* reduces duplicate chunks with a diversity filter

### 6. Local persistence

Meeting metadata, transcript, summary, and extracted analysis are stored in SQLite.

### 7. Browser-based dashboard

The front end is a single-page dashboard that lets the user:

* upload a recording
* view meetings in a table
* open a meeting and inspect transcript and extracted fields
* query the meeting in natural language
* delete a meeting

---

## Main Features

### Upload and processing

* MP3, WAV, M4A, and MP4 uploads
* local file storage
* async background processing
* transcript generation

### Meeting intelligence extraction

The model extracts the most useful meeting fields with a strict output structure.

### Natural-language Q&A

Users can ask questions such as:

* What tasks were assigned to Rahul?
* What are the deadlines?
* What decisions were finalized?
* What blockers are still open?
* Why is pricing still unresolved?

### Retrieval improvements

The retriever now uses a more advanced strategy than simple fixed chunk lookup, which improves answer quality for long meetings.

---

## Technology Stack

| Component | Technology |
| --- | --- |
| Backend | FastAPI |
| API server | Uvicorn |
| Language | Python 3.12 |
| Background jobs | Python thread + queue |
| Transcription | Faster-Whisper |
| LLM orchestration | LangChain |
| Chat model | OpenAI |
| Structured validation | Pydantic |
| Database | SQLite |
| ORM | SQLAlchemy |
| Vector store | ChromaDB |
| Embeddings | OpenAI embeddings |
| Environment loading | python-dotenv |
| Browser UI | Plain HTML, CSS, JavaScript |

---

## Project Structure

```text
ai_intelligence_meeting_app/
├── main.py
├── queue_worker.py
├── services.py
├── audio_utils.py
├── database.py
├── models.py
├── schemas.py
├── static/
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── uploads/
├── chroma_store/
├── meetings.db
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## File Responsibilities

### `main.py`

FastAPI application entrypoint. It serves the UI and exposes the REST API endpoints for upload, list, detail, query, and delete.

### `queue_worker.py`

Background worker that transcribes the uploaded recording, runs extraction, stores the result, and indexes the transcript.

### `services.py`

Contains the core service layer:

* transcription service
* extraction prompt and answer prompt
* retrieval service
* embedding calls
* chunking and reranking logic

### `schemas.py`

Defines the strict Pydantic models for structured output and query requests/responses.

### `models.py`

Defines the SQLAlchemy meeting table.

### `database.py`

Creates the SQLite engine, session factory, and database base.

### `audio_utils.py`

Saves uploaded files into the local upload folder.

### `static/`

Contains the browser dashboard.

---

## API Endpoints

### `POST /api/meetings/upload`

Uploads an audio file and starts background processing.

### `GET /api/meetings`

Returns the list of meetings.

### `GET /api/meetings/{meeting_id}`

Returns the full meeting record, transcript, and extracted analysis.

### `POST /api/meetings/{meeting_id}/query`

Runs a natural-language question against the meeting analysis and transcript chunks.

### `DELETE /api/meetings/{meeting_id}`

Deletes a meeting and its database record.

### `GET /`

Serves the browser dashboard.

---

## Browser UI

Open the app in your browser at:

```text
http://localhost:8000/
```

The dashboard includes:

* an upload panel
* a meetings table
* a detailed meeting view
* a query panel
* delete controls

It also supports re-selecting the same file and shows the selected filename in the upload area.

---

## Example Questions

The app is built to answer questions like:

* What tasks were assigned to Rahul?
* What are the deadlines?
* What decisions were finalized?
* What blockers are still open?
* Why is pricing still unresolved?

---

## Setup

### 1. Create a `.env` file

Use `.env.example` as the template and provide your OpenAI key.

```env
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4o-mini
WHISPER_MODEL=base
UPLOAD_DIR=uploads
CHROMA_DIR=chroma_store
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the app locally

```bash
uvicorn main:app --reload
```

Then open `http://localhost:8000/`.

---

## Run with Docker

```bash
docker compose up --build
```

Docker persists:

* `uploads/`
* `chroma_store/`
* `meetings.db`

---

## Notes On Accuracy

The project uses a few techniques to keep responses reliable:

* strict extraction prompts
* Pydantic structured output
* deduplication of repeated action items
* sentence-aware chunking
* top-k candidate expansion before final selection
* hybrid reranking with semantic similarity and lexical overlap
* score thresholding for retrieval
* diversity filtering to reduce duplicate chunks

These steps improve the quality of both the extracted meeting summary and the retrieval-based question answering.

---

## Meeting Input Example

The system is intended for recordings of conversations such as:

* a manager assigning tasks and deadlines
* team members discussing blockers
* unresolved topics like pricing or implementation issues
* follow-up commitments for the next meeting

---

## Troubleshooting

### Upload works but query is weak

Make sure the meeting has completed processing and that the transcript is long enough to produce meaningful chunks.

### No transcript generated

Check the Whisper model download and the audio file format.

### OpenAI errors

Verify that `.env` contains `OPENAI_API_KEY`.

### Chroma or embedding issues

The app uses local Chroma persistence and OpenAI embeddings. If indexing fails, clear the local `chroma_store/` folder and try again.

---

## Future Improvements

Possible next upgrades include:

* cross-encoder reranking
* BM25 + vector hybrid search
* speaker diarization
* deadline normalization and overdue detection
* export to PDF or CSV
* evaluation against a fixed question set

---

## Summary

This project is a compact AI meeting assistant that combines transcription, structured extraction, semantic retrieval, and a browser UI. It is designed to be practical, easy to run, and easy to extend.

---

## Example Test Recording

To verify the upload and transcription flow, use a meeting recording with a conversation like this:

* finalize the beta launch by 15 September
* complete the payment API integration by 10 September
* prepare QA test cases by 12 September
* investigate the timeout issue reported by the mobile team
* note that product pricing is still not finalized
* provide payment gateway test account access today

When the candidate uploads the audio file through `/api/meetings/upload`, the system will automatically:

* save the file
* transcribe the recording with Faster-Whisper
* extract decisions and action items
* store the transcript and analysis in SQLite
* index the transcript for semantic search

The uploaded meeting should then be available through the meeting list and detail endpoints.

---

## `services.py`

This is the main service layer.

It currently contains the core service implementations.

### Upload Service

`save_upload_file()`

Responsible for:

* Creating the upload directory
* Generating a unique filename
* Saving the uploaded audio file

A UUID is used so that uploaded files do not overwrite each other.

---

## `TranscriptionService`

The transcription service uses Faster-Whisper.

Conceptually:

```text
Audio File
    ↓
Whisper Model
    ↓
Speech Segments
    ↓
Clean Text
    ↓
Transcript
```

The model is configurable using:

```env
WHISPER_MODEL=base
```

The default model is:

```text
base
```

The current implementation runs Whisper on CPU using:

```text
device = cpu
compute_type = int8
```

---

## `ExtractionService`
