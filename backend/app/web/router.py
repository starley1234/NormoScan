"""
NormoScan Web UI - Minimal llamacpp-style interface.
Server-rendered pages with Jinja2 templates.
"""
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models.user import User
from ..security import get_current_user_optional, get_current_user

logger = logging.getLogger(__name__)

# Templates
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Disable cache for testing
templates.env.cache = None

# Add custom filters and globals
def tojson_filter(value, indent=None):
    import json
    return json.dumps(value, ensure_ascii=False, indent=indent, default=str)

templates.env.filters['tojson'] = tojson_filter

def status_badge(status):
    """Generate status badge HTML."""
    colors = {
        "done": "badge-success",
        "queued": "badge-warning",
        "processing": "badge-info",
        "failed": "badge-error",
        "dead_letter": "badge-error",
        "dedupe": "badge-info"
    }
    css_class = colors.get(status, "")
    return f'<span class="badge {css_class}">{status}</span>'

def format_date(iso):
    """Format ISO date string."""
    if not iso:
        return "—"
    try:
        from datetime import datetime
        if isinstance(iso, str):
            d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        else:
            d = iso
        return d.strftime("%d.%m.%Y %H:%M")
    except (ValueError, TypeError):
        return str(iso)

templates.env.globals['statusBadge'] = status_badge
templates.env.globals['formatDate'] = format_date

router = APIRouter(prefix="/web", tags=["web"])


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "username": "guest",
            "role": "viewer"
        }
    )


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, user: User = Depends(get_current_user)):
    from ..services.analytics import analytics_summary
    from ..core.metrics import metrics
    from ..models.check import Check
    from ..models.team import Assignment, ActiveLearningRun
    from ..db import SessionLocal
    
    db = SessionLocal()
    try:
        summary = analytics_summary(db, days=7)
        snap = metrics.snapshot()
        total = db.query(Check).count()
        done = db.query(Check).filter(Check.status == "done").count()
        pending = db.query(Assignment).filter(Assignment.status == "pending").count()
        last_run = db.query(ActiveLearningRun).order_by(ActiveLearningRun.created_at.desc()).first()
        last_checks = db.query(Check).order_by(Check.created_at.desc()).limit(5).all()
        
        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "active_page": "dashboard",
                "username": user.username,
                "role": user.role,
                "total": total,
                "done": done,
                "pending": pending,
                "hit_rate": snap.get("gauges", {}).get("normoscan_hit_rate", 0),
                "top_errors": summary.get("top_errors", []),
                "by_day": summary.get("by_day", {}),
                "last_run": last_run,
                "last_checks": last_checks,
                "uptime_hours": round(snap.get("uptime_seconds", 0) / 3600, 1)
            }
        )
    finally:
        db.close()


@router.get("/checks", response_class=HTMLResponse)
def checks_list(request: Request, user: User = Depends(get_current_user),
                status: str = None, q: str = None, page: int = 1):
    from ..models.check import Check
    from ..db import SessionLocal
    
    db = SessionLocal()
    try:
        query = db.query(Check).order_by(Check.created_at.desc())
        if status:
            query = query.filter(Check.status == status)
        if q:
            query = query.filter(Check.filename.ilike(f"%{q}%"))
        
        per_page = 20
        total = query.count()
        items = query.offset((page - 1) * per_page).limit(per_page).all()
        
        return templates.TemplateResponse(
            request=request,
            name="checks.html",
            context={
                "active_page": "checks",
                "username": user.username,
                "role": user.role,
                "checks": items,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page,
                "status_filter": status,
                "search_q": q
            }
        )
    finally:
        db.close()


@router.get("/checks/{check_id}", response_class=HTMLResponse)
def check_detail(check_id: int, request: Request, user: User = Depends(get_current_user)):
    from ..models.check import Check, PageResult
    from ..db import SessionLocal
    
    db = SessionLocal()
    try:
        check = db.query(Check).filter(Check.id == check_id).first()
        if not check:
            return RedirectResponse(url="/web/checks", status_code=302)
        
        pages = db.query(PageResult).filter(PageResult.check_id == check_id).order_by(PageResult.page_number).all()
        
        return templates.TemplateResponse(
            request=request,
            name="check_detail.html",
            context={
                "active_page": "checks",
                "username": user.username,
                "role": user.role,
                "check": check,
                "pages": pages
            }
        )
    finally:
        db.close()


@router.get("/upload", response_class=HTMLResponse)
def upload_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse(
        request=request,
        name="upload.html",
        context={
            "active_page": "upload",
            "username": user.username,
            "role": user.role
        }
    )


@router.get("/gosts", response_class=HTMLResponse)
def gosts_page(request: Request, user: User = Depends(get_current_user)):
    from ..models.gost import Gost
    from ..db import SessionLocal
    
    db = SessionLocal()
    try:
        gosts = db.query(Gost).order_by(Gost.designation).limit(100).all()
        return templates.TemplateResponse(
            request=request,
            name="gosts.html",
            context={
                "active_page": "gosts",
                "username": user.username,
                "role": user.role,
                "gosts": gosts
            }
        )
    finally:
        db.close()


@router.get("/gallery", response_class=HTMLResponse)
def gallery_page(request: Request, user: User = Depends(get_current_user)):
    from ..models.gallery import GalleryItem
    from ..db import SessionLocal
    
    db = SessionLocal()
    try:
        items = db.query(GalleryItem).order_by(GalleryItem.created_at.desc()).limit(100).all()
        return templates.TemplateResponse(
            request=request,
            name="gallery.html",
            context={
                "active_page": "gallery",
                "username": user.username,
                "role": user.role,
                "items": items
            }
        )
    finally:
        db.close()


@router.get("/analytics", response_class=HTMLResponse)
def analytics_page(request: Request, user: User = Depends(get_current_user)):
    from ..services.analytics import analytics_summary, generate_llm_report
    from ..db import SessionLocal
    
    db = SessionLocal()
    try:
        summary = analytics_summary(db, days=30)
        report = generate_llm_report(db, days=30)
        
        return templates.TemplateResponse(
            request=request,
            name="analytics.html",
            context={
                "active_page": "analytics",
                "username": user.username,
                "role": user.role,
                "summary": summary,
                "report": report
            }
        )
    finally:
        db.close()


@router.get("/team", response_class=HTMLResponse)
def team_page(request: Request, user: User = Depends(get_current_user)):
    from ..models.team import Assignment
    from ..db import SessionLocal
    
    db = SessionLocal()
    try:
        assignments = db.query(Assignment).filter(Assignment.assignee_id == user.id).order_by(Assignment.created_at.desc()).all()
        return templates.TemplateResponse(
            request=request,
            name="team.html",
            context={
                "active_page": "team",
                "username": user.username,
                "role": user.role,
                "assignments": assignments
            }
        )
    finally:
        db.close()


@router.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, user: User = Depends(get_current_user)):
    if user.role != "admin":
        return RedirectResponse(url="/web/", status_code=302)
    
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "active_page": "admin",
            "username": user.username,
            "role": user.role,
            "config": settings
        }
    )
