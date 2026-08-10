from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[str]
    role: str
    is_active: bool
    class Config:
        from_attributes = True

class CheckCreate(BaseModel):
    priority: int = 5

class CheckOut(BaseModel):
    id: int
    filename: str
    status: str
    priority: int
    pages_total: int
    pages_done: int
    created_at: datetime
    finished_at: Optional[datetime]
    meta_json: Optional[Any]
    errors_json: Optional[Any]
    summary: Optional[str]
    class Config:
        from_attributes = True

class GostOut(BaseModel):
    id: int
    designation: str
    title: str
    status: str
    created_at: datetime
    class Config:
        from_attributes = True

class GalleryOut(BaseModel):
    id: int
    title: str
    category: str
    gost_ref: Optional[str]
    error_type: Optional[str]
    filepath: str
    class Config:
        from_attributes = True

class FeedbackIn(BaseModel):
    check_id: int
    page_number: Optional[int] = None
    error_id: Optional[str] = None
    vote: str  # like/dislike or 👍/👎
    comment: Optional[str] = None

class AnalyticsOut(BaseModel):
    period: str
    total_checks: int
    top_errors: List[Any]
    summary: str
