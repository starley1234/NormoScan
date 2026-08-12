from sqlalchemy import String, DateTime, Integer, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from ..db import Base


class Assignment(Base):
    __tablename__ = "assignments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    check_id: Mapped[int] = mapped_column(Integer, ForeignKey("checks.id"), index=True)
    assignee_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    assigned_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    comment: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    check_id: Mapped[int] = mapped_column(Integer, ForeignKey("checks.id"), index=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=True)
    bbox: Mapped[list] = mapped_column(JSON, nullable=True)
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text)
    mentions: Mapped[list] = mapped_column(JSON, nullable=True)
    parent_id: Mapped[int] = mapped_column(Integer, ForeignKey("comments.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationship for eager loading (avoids N+1)
    author = relationship("User", lazy="joined")


class ActiveLearningRun(Base):
    __tablename__ = "active_learning_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    triggered_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    promoted_count: Mapped[int] = mapped_column(Integer, default=0)
    before_hit_rate: Mapped[float] = mapped_column(default=0.0)
    after_hit_rate: Mapped[float] = mapped_column(default=0.0)
    status: Mapped[str] = mapped_column(String(32), default="done")
    details_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
