from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..db import get_db
from ..models.user import User
from ..security import get_current_user
from ..services.analytics import analytics_summary
from ..models.check import Feedback

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

@router.get("/summary")
def summary(days: int=30, department: str=None, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    return analytics_summary(db, days=days, department=department)

@router.get("/feedbacks")
def feedbacks(limit:int=50, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if user.role not in ("admin","normocontroller"):
        from fastapi import HTTPException
        raise HTTPException(403, "Forbidden")
    items=db.query(Feedback).order_by(Feedback.created_at.desc()).limit(limit).all()
    return {"items": [{"id":f.id,"check_id":f.check_id,"vote":f.vote,"comment":f.comment,"created_at":f.created_at} for f in items]}

@router.get("/stats")
def stats(db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    from ..models.check import Check
    total=db.query(Check).count()
    done=db.query(Check).filter(Check.status=="done").count()
    queued=db.query(Check).filter(Check.status=="queued").count()
    failed=db.query(Check).filter(Check.status=="failed").count()
    return {"total":total,"done":done,"queued":queued,"failed":failed}
