from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import os, logging

from .config import settings
from .db import init_db, SessionLocal
from .routers import auth, checks, gosts, gallery, analytics, admin
from .mcp_server import handle_mcp, mcp_info

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
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
    logger.info(f"NormoScan started: model={settings.vlm_model} quant={settings.vlm_quantization} ctx={settings.max_context_window}")
    yield
    logger.info("NormoScan shutdown")

app = FastAPI(
    title="НормоСкан API",
    description="Сервис интеллектуального нормоконтроля КД (ГОСТ/СТП) — VLM + Hybrid RAG",
    version="1.0.0",
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

# MCP endpoints
@app.post("/mcp")
async def mcp_post(request: Request):
    return await handle_mcp(request)

@app.get("/mcp")
def mcp_get():
    return mcp_info()

# Also support /api/mcp alias
@app.post("/api/mcp")
async def api_mcp_post(request: Request):
    return await handle_mcp(request)

@app.get("/api/mcp")
def api_mcp_get():
    return mcp_info()

@app.get("/health")
def health():
    return {"status":"ok","version":"1.0.0","vrаm_optimized":True,"model":settings.vlm_model,"quant":settings.vlm_quantization,"context_window":settings.max_context_window}

@app.get("/api/health")
def api_health():
    return {"status":"ok"}

@app.get("/")
def root():
    return {"name":"НормоСкан","docs":"/docs","frontend":"http://localhost:8501","mcp":"/mcp"}



# Mount static for gallery/check files if exists
if os.path.isdir(settings.storage_path):
    try:
        app.mount("/storage", StaticFiles(directory=settings.storage_path), name="storage")
    except: pass
