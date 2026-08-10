from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str | None
    role: str
    is_active: bool

class CheckCreate(BaseModel):
    priority: int = 5

class CheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    status: str
    priority: int
    pages_total: int
    pages_done: int
    created_at: datetime
    finished_at: datetime | None
    meta_json: Any | None
    errors_json: Any | None
    summary: str | None

class GostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    designation: str
    title: str
    status: str
    created_at: datetime

class GalleryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: str
    gost_ref: str | None
    error_type: str | None
    filepath: str

class FeedbackIn(BaseModel):
    check_id: int
    page_number: int | None = None
    error_id: str | None = None
    vote: str  # like/dislike or 👍/👎
    comment: str | None = None

class AnalyticsOut(BaseModel):
    period: str
    total_checks: int
    top_errors: list[Any]
    summary: str
