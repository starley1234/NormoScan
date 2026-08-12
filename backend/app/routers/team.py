from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from ..db import get_db
from ..models.user import User
from ..security import get_current_user
from ..services.team import assign_check, set_review, add_comment, list_comments, list_assignments

router = APIRouter(prefix="/api/team", tags=["team"])

class AssignIn(BaseModel):
    assignee_id: int
    comment: Optional[str]=None

class ReviewIn(BaseModel):
    decision: str  # approved | rejected | in_review
    comment: Optional[str]=None

class CommentIn(BaseModel):
    text: str
    page_number: Optional[int]=None
    bbox: Optional[list]=None
    parent_id: Optional[int]=None

@router.post("/checks/{check_id}/assign")
def assign(check_id: int, inp: AssignIn, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if user.role not in ("admin","normocontroller"):
        raise HTTPException(403, "Only admin/normocontroller can assign")
    a = assign_check(db, check_id, inp.assignee_id, user.id, inp.comment)
    return {"id": a.id, "status": a.status}

@router.get("/checks/{check_id}/assignments")
def get_assignments(check_id: int, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    items = list_assignments(db, check_id=check_id)
    return {"items": [{"id":a.id,"check_id":a.check_id,"assignee_id":a.assignee_id,"assigned_by":a.assigned_by,"status":a.status,"comment":a.comment,"created_at":a.created_at} for a in items]}

@router.get("/my/assignments")
def my_assignments(db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    items = list_assignments(db, assignee_id=user.id)
    return {"items": [{"id":a.id,"check_id":a.check_id,"status":a.status,"created_at":a.created_at} for a in items]}

@router.post("/checks/{check_id}/review")
def review(check_id: int, inp: ReviewIn, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if inp.decision not in ("approved","rejected","in_review"):
        raise HTTPException(400, "decision must be approved|rejected|in_review")
    a = set_review(db, check_id, user.id, inp.decision, inp.comment)
    return {"id": a.id, "status": a.status}

@router.post("/checks/{check_id}/comments")
def post_comment(check_id: int, inp: CommentIn, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    c = add_comment(db, check_id, user.id, inp.text, inp.page_number, inp.bbox, inp.parent_id)
    return {"id": c.id, "mentions": c.mentions, "text": c.text}

@router.get("/checks/{check_id}/comments")
def get_comments(check_id: int, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    items = list_comments(db, check_id)
    # enrich author
    from ..models.user import User as U
    out=[]
    for c in items:
        author = db.query(U).filter(U.id==c.author_id).first()
        out.append({"id":c.id,"text":c.text,"mentions":c.mentions,"author": author.username if author else str(c.author_id),"page_number":c.page_number,"bbox":c.bbox,"parent_id":c.parent_id,"created_at":c.created_at})
    return {"items": out}
