import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from audio_utils import save_upload_file
from database import Base, engine, get_db
from models import Meeting
from queue_worker import jobs, start_worker
from schemas import QueryRequest, QueryResponse
from services import answer_question, retriever

logging.basicConfig(level=logging.INFO)
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app):
    start_worker()
    yield


app = FastAPI(title="AI Meeting Intelligence & Action Tracker", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="static"), name="static")


def find_meeting(db, meeting_id):
    meeting = db.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


@app.post("/api/meetings/upload", status_code=202)
def upload_meeting(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith((".mp3", ".wav", ".m4a", ".mp4")):
        raise HTTPException(status_code=400, detail="Unsupported file type")

    meeting = Meeting(filename=file.filename, audio_path=save_upload_file(file))
    db.add(meeting)
    db.commit()

    jobs.put(meeting.id)
    return {"meeting_id": meeting.id, "status": meeting.status}


@app.get("/api/meetings")
def list_meetings(db: Session = Depends(get_db)):
    meetings = db.query(Meeting).order_by(Meeting.created_at.desc()).all()
    return [
        {"id": m.id, "filename": m.filename, "status": m.status, "created_at": m.created_at}
        for m in meetings
    ]


@app.get("/api/meetings/{meeting_id}")
def get_meeting(meeting_id: int, db: Session = Depends(get_db)):
    meeting = find_meeting(db, meeting_id)
    return {
        "id": meeting.id,
        "filename": meeting.filename,
        "status": meeting.status,
        "error_message": meeting.error_message,
        "transcript": meeting.transcript,
        "summary": meeting.summary,
        "analysis": meeting.analysis,
        "created_at": meeting.created_at,
    }


@app.post("/api/meetings/{meeting_id}/query", response_model=QueryResponse)
def query_meeting(meeting_id: int, body: QueryRequest, db: Session = Depends(get_db)):
    meeting = find_meeting(db, meeting_id)
    if meeting.status != "completed":
        raise HTTPException(status_code=409, detail=f"Meeting is {meeting.status}")

    chunks, sources = retriever.search(meeting_id, body.question)
    answer = answer_question(body.question, meeting.analysis, chunks)
    return QueryResponse(answer=answer, sources=sources)


@app.delete("/api/meetings/{meeting_id}")
def delete_meeting(meeting_id: int, db: Session = Depends(get_db)):
    db.delete(find_meeting(db, meeting_id))
    db.commit()
    return {"message": "Meeting deleted successfully"}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    with open("static/index.html", encoding="utf-8") as file:
        return file.read()
