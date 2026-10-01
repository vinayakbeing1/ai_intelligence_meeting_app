from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text

from database import Base


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    audio_path = Column(String(500), nullable=False)
    status = Column(String(50), default="queued")
    error_message = Column(Text)
    transcript = Column(Text)
    summary = Column(Text)
    analysis = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
