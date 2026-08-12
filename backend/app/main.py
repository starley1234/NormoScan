import logging
import os
import secrets
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import settings
from .core.logging import setup_logging
from .core.metrics import metrics
from .db import SessionLocal, init_db
from .mcp_server import handle_mcp, mcp_info
from .routers import admin, analytics, auth, checks, dashboard, gallery, gosts, team
from .web.router import router as web_router

setup_logging()
logger = logging.getLogger(__name__)

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Security: generate secret if default
    if settings.secret_key == "change-me":
        new_secret = secrets.token_hex(32)
        logger.warning(f"SECRET_KEY was default, generated new: {new_secret[:8]}...")
        settings.secret_key = new_secret
    
    init_db()
    # ensure default metadata schema
    try:
        db = SessionLocal()
        from .models.app_settings import MetadataSchema
        from .services.metadata import DEFAULT_SCHEMA
        if not db.query(MetadataSchema).first():
            ms = MetadataSchema(name="default", title="Базовая схема ГОСТ 2.104", schema_json=DEFAULT_SCHEMA, is_active=True)
            db.add(ms)
            db.commit()
        db.close()
    except Exception as e:
        logger.warning(f"metadata schema seed failed: {e}")
    try:
        db = SessionLocal()
        from .routers.auth import seed_admin
        seed_admin(db)
        db.close()
    except Exception as e:
        logger.warning(f"seed failed: {e}")
    try:
        from .vector_store import ensure_collections
        ensure_collections()
    except Exception as e:
        logger.warning(f"vector ensure failed: {e}")
    for p in [settings.storage_path, settings.gosts_path, settings.gallery_path]:
        os.makedirs(p, exist_ok=True)
    logger.info(f"NormoScan started: model={settings.vlm_model} quant={settings.vlm_quantization} engine={settings.vlm_engine} ctx={settings.max_context_window}")
    yield
    logger.info("NormoScan shutdown")


app = FastAPI(
    title="НормоСкан API",
    description="Сервис интеллектуального нормоконтроля КД (ГОСТ/СТП) — VLM + Hybrid RAG | 16GB VRAM optimised | Gemma-3-12B / Qwen2-VL",
    version="1.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# Global exception handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "status": exc.status_code}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "status": 422}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "status": 500}
    )


# CORS - secure by default
_cors_origins = settings.cors_origins
if _cors_origins == "*":
    # In production, restrict this
    if settings.app_env == "production":
        logger.warning("CORS set to '*' in production - this is insecure!")
    allow_origins = ["*"]
else:
    allow_origins = [s.strip() for s in _cors_origins.split(",") if s.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(checks.router)
app.include_router(gosts.router)
app.include_router(gallery.router)
app.include_router(analytics.router)
app.include_router(admin.router)
app.include_router(team.router)
app.include_router(dashboard.router)

# Web UI router
app.include_router(web_router)

# MCP endpoints
@app.post("/mcp")
async def mcp_post(request: Request):
    return await handle_mcp(request)

@app.get("/mcp")
def mcp_get():
    return mcp_info()

@app.post("/api/mcp")
async def api_mcp_post(request: Request):
    return await handle_mcp(request)

@app.get("/api/mcp")
def api_mcp_get():
    return mcp_info()


@app.get("/health")
def health():
    """Health check endpoint."""
    from .utils import clean_url
    clean_vlm_url = clean_url(settings.vlm_api_url) if settings.vlm_api_url else None
    return {
        "status": "ok",
        "version": "1.2.0",
        "vram_optimized": True,
        "model": settings.vlm_model,
        "quant": settings.vlm_quantization,
        "engine": settings.vlm_engine,
        "context_window": settings.max_context_window,
        "ocr_ensemble": settings.ocr_ensemble,
        "vlm_api_url": clean_vlm_url,
        "has_vlm_key": bool(settings.vlm_api_key)
    }


@app.get("/api/health")
def api_health():
    return {"status": "ok"}


@app.get("/metrics", summary="Prometheus metrics")
def prometheus_metrics():
    if not settings.enable_metrics:
        return PlainTextResponse("metrics disabled")
    return PlainTextResponse(metrics.prometheus_text(), media_type="text/plain")


@app.get("/api/metrics", summary="JSON metrics")
def json_metrics():
    return metrics.snapshot()


@app.get("/")
def root():
    """Redirect to web UI."""
    return RedirectResponse(url="/web/", status_code=302)


# Mount static files for web UI
_web_static = Path(__file__).parent / "web" / "static"
if _web_static.is_dir():
    app.mount("/web/static", StaticFiles(directory=str(_web_static)), name="web_static")

# Mount storage for gallery/check files if exists
if os.path.isdir(settings.storage_path):
    try:
        app.mount("/storage", StaticFiles(directory=settings.storage_path), name="storage")
    except Exception:
        pass
