from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class Check(Base):
    __tablename__ = "checks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255))
    filepath: Mapped[str] = mapped_column(String(512))
    file_hash: Mapped[str] = mapped_column(String(64), nullable=True, index=True)  # dedupe
    status: Mapped[str] = mapped_column(String(32), default="queued")  # queued|processing|done|failed|dead_letter
    priority: Mapped[int] = mapped_column(Integer, default=5)  # 1 high .. 10 low
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    pages_total: Mapped[int] = mapped_column(Integer, default=0)
    pages_done: Mapped[int] = mapped_column(Integer, default=0)
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=True)  # extracted metadata
    errors_json: Mapped[list] = mapped_column(JSON, nullable=True)  # list of errors with suggested_fix
    summary: Mapped[str] = mapped_column(Text, nullable=True)
    consistency_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    checklist_json: Mapped[dict] = mapped_column(JSON, nullable=True)  # ГОСТ checklist

class PageResult(Base):
    __tablename__ = "page_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    check_id: Mapped[int] = mapped_column(Integer, ForeignKey("checks.id"))
    page_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    ocr_text: Mapped[str] = mapped_column(Text, nullable=True)
    ocr_confidence: Mapped[float] = mapped_column(Float, nullable=True)
    vlm_output: Mapped[dict] = mapped_column(JSON, nullable=True)
    errors: Mapped[list] = mapped_column(JSON, nullable=True)
    crops: Mapped[dict] = mapped_column(JSON, nullable=True)  # zones
    visual_hits: Mapped[list] = mapped_column(JSON, nullable=True)
    text_hits: Mapped[list] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Feedback(Base):
    __tablename__ = "feedbacks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    check_id: Mapped[int] = mapped_column(Integer, ForeignKey("checks.id"))
    page_number: Mapped[int] = mapped_column(Integer, nullable=True)
    error_id: Mapped[str] = mapped_column(String(64), nullable=True)
    vote: Mapped[str] = mapped_column(String(8))  # 👍 / 👎  or like/dislike
    comment: Mapped[str] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class DeadLetter(Base):
    __tablename__ = "dead_letters"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    check_id: Mapped[int] = mapped_column(Integer, ForeignKey("checks.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=True)
    error: Mapped[str] = mapped_column(Text, nullable=True)
    traceback: Mapped[str] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
