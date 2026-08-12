from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class GalleryItem(Base):
    __tablename__ = "gallery"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(64), index=True)  # error_type / etalon
    gost_ref: Mapped[str] = mapped_column(String(64), nullable=True)  # e.g., ГОСТ 2.307
    error_type: Mapped[str] = mapped_column(String(128), nullable=True)  # e.g., "Неверная засечка стрелки"
    filepath: Mapped[str] = mapped_column(String(512))
    embedding_id: Mapped[str] = mapped_column(String(64), nullable=True)
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
