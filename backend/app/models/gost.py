from sqlalchemy import String, DateTime, Integer, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from ..db import Base

class Gost(Base):
    __tablename__ = "gosts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    designation: Mapped[str] = mapped_column(String(64), index=True)  # e.g., ГОСТ 2.104-2006
    title: Mapped[str] = mapped_column(String(512))
    filepath: Mapped[str] = mapped_column(String(512), nullable=True)
    content_text: Mapped[str] = mapped_column(Text, nullable=True)
    chunks_json: Mapped[list] = mapped_column(JSON, nullable=True)  # text chunks with embeddings ids
    status: Mapped[str] = mapped_column(String(32), default="indexed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
