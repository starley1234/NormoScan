from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..db import get_db
from ..models.user import User
from ..security import get_current_user
from ..services.analytics import analytics_summary
from ..core.metrics import metrics
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("/summary")
def summary(days: int=7, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    from ..models.check import Check
    from ..models.team import Assignment
    from sqlalchemy import func
    # Lightweight dashboard (без Grafana)
    base = analytics_summary(db, days=days)
    snap = metrics.snapshot()
    total = db.query(Check).count()
    done = db.query(Check).filter(Check.status=="done").count()
    # pending reviews
    pending = db.query(Assignment).filter(Assignment.status=="pending").count()
    # last active learning
    from ..models.team import ActiveLearningRun
    last_run = db.query(ActiveLearningRun).order_by(ActiveLearningRun.created_at.desc()).first()
    hit_rate = snap.get("gauges",{}).get("normoscan_hit_rate", 0.75)
    # last checks
    last_checks = db.query(Check).order_by(Check.created_at.desc()).limit(5).all()
    return {
        "period": f"{days}d",
        "total": total,
        "done": done,
        "pending_reviews": pending,
        "hit_rate": hit_rate,
        "top_errors": base.get("top_errors",[]),
        "by_day": base.get("by_day",{}),
        "summary": base.get("summary"),
        "metrics": snap,
        "last_run": {"id": last_run.id, "before": last_run.before_hit_rate, "after": last_run.after_hit_rate, "created_at": last_run.created_at} if last_run else None,
        "last_checks": [{"id":c.id,"filename":c.filename,"status":c.status,"created_at":c.created_at} for c in last_checks],
        "uptime_hours": round(snap.get("uptime_seconds",0)/3600,1)
    }

@router.get("/active-learning")
def active_learning_status(db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    from ..services.active_learning import get_last_runs
    runs = get_last_runs(db, limit=10)
    return {"runs": [{"id":r.id,"before":r.before_hit_rate,"after":r.after_hit_rate,"promoted":r.promoted_count,"created_at":r.created_at,"status":r.status} for r in runs]}

@router.post("/active-learning/run")
def run_active(db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if user.role not in ("admin","normocontroller"):
        from fastapi import HTTPException
        raise HTTPException(403, "Only admin/normocontroller")
    from ..services.active_learning import run_active_learning_cycle
    res = run_active_learning_cycle(db, triggered_by=user.id)
    return res
