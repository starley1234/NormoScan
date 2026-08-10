from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..db import get_db
from ..models.user import User
from ..security import get_current_user
from ..services.analytics import analytics_summary, generate_llm_report, search_knowledge_base
from ..models.check import Feedback
from typing import Optional

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

@router.get("/summary")
def summary(days: int=30, department: str=None, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    return analytics_summary(db, days=days, department=department)

@router.get("/report", summary="LLM отчёт с рекомендациями (Gemma)")
def report(days: int=30, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    return generate_llm_report(db, days=days)

@router.get("/feedbacks")
def feedbacks(limit:int=50, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if user.role not in ("admin","normocontroller"):
        from fastapi import HTTPException
        raise HTTPException(403, "Forbidden")
    items=db.query(Feedback).order_by(Feedback.created_at.desc()).limit(limit).all()
    return {"items": [{"id":f.id,"check_id":f.check_id,"vote":f.vote,"comment":f.comment,"created_at":f.created_at, "error_id":f.error_id} for f in items]}

@router.get("/stats")
def stats(db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    from ..models.check import Check
    total=db.query(Check).count()
    done=db.query(Check).filter(Check.status=="done").count()
    queued=db.query(Check).filter(Check.status=="queued").count()
    failed=db.query(Check).filter(Check.status=="failed").count()
    dead=db.query(Check).filter(Check.status=="dead_letter").count()
    return {"total":total,"done":done,"queued":queued,"failed":failed,"dead_letter":dead}

@router.get("/knowledge/search")
def knowledge_search(q: str, top_k: int=10, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    return {"query": q, "results": search_knowledge_base(db, q, top_k)}

@router.get("/trends")
def trends(days: int=30, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    base = analytics_summary(db, days=days)
    return {"by_day": base.get("by_day"), "top_errors": base.get("top_errors")}
