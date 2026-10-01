import logging
import queue
import threading

from database import SessionLocal
from models import Meeting
from services import extract_analysis, retriever, transcriber

log = logging.getLogger(__name__)
jobs = queue.Queue()


def process_meeting(meeting_id):
    db = SessionLocal()
    meeting = db.get(Meeting, meeting_id)
    meeting.status = "processing"
    db.commit()

    try:
        meeting.transcript = transcriber.transcribe(meeting.audio_path)
        analysis = extract_analysis(meeting.transcript)
        meeting.summary = analysis.summary
        meeting.analysis = analysis.model_dump()
        retriever.index(meeting_id, meeting.transcript)
        meeting.status = "completed"
    except Exception as error:
        log.exception("Meeting %s failed", meeting_id)
        meeting.status = "failed"
        meeting.error_message = str(error)

    db.commit()
    db.close()


def worker():
    while True:
        process_meeting(jobs.get())


def start_worker():
    threading.Thread(target=worker, daemon=True).start()
