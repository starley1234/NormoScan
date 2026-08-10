from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

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
    # Versioning / incremental ingest
    file_hash: Mapped[str] = mapped_column(String(64), nullable=True, index=True)
    file_mtime: Mapped[float] = mapped_column(Float, nullable=True)
    file_size: Mapped[int] = mapped_column(Integer, nullable=True)
    version: Mapped[str] = mapped_column(String(32), nullable=True)  # derived from designation or file
    valid_from: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    valid_to: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    is_obsolete: Mapped[bool] = mapped_column(Boolean, default=False)
    superseded_by: Mapped[str] = mapped_column(String(64), nullable=True)  # designation of replacement
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
