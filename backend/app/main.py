import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .core.logging import setup_logging
from .core.metrics import metrics
from .db import SessionLocal, init_db
from .mcp_server import handle_mcp, mcp_info
from .routers import admin, analytics, auth, checks, dashboard, gallery, gosts, team

setup_logging()
logger = logging.getLogger(__name__)

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS for preview host
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.cors_origins=="*" else [s.strip() for s in settings.cors_origins.split(",")],
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
    return {"status":"ok","version":"1.1.0","vrаm_optimized":True,"model":settings.vlm_model,"quant":settings.vlm_quantization,"engine":settings.vlm_engine,"context_window":settings.max_context_window, "ocr_ensemble": settings.ocr_ensemble}

@app.get("/api/health")
def api_health():
    return {"status":"ok"}

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
    return {"name":"НормоСкан","docs":"/docs","frontend":"http://localhost:8501","mcp":"/mcp", "metrics":"/metrics"}

# Mount static for gallery/check files if exists
if os.path.isdir(settings.storage_path):
    try:
        app.mount("/storage", StaticFiles(directory=settings.storage_path), name="storage")
    except: pass
if os.path.isdir("frontend/static"):
    try:
        app.mount("/pwa", StaticFiles(directory="frontend/static"), name="pwa")
    except: pass
