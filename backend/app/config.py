import os
from functools import lru_cache
from typing import Literal

from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    secret_key: str = Field(default="change-me", validation_alias="SECRET_KEY")
    api_host: str = Field(default="0.0.0.0", validation_alias="API_HOST")
    api_port: int = Field(default=8000, validation_alias="API_PORT")

    database_url: str = Field(default="sqlite:///./normoscan.db", validation_alias="DATABASE_URL")
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    celery_broker_url: str = Field(default="redis://localhost:6379/1", validation_alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="redis://localhost:6379/2", validation_alias="CELERY_RESULT_BACKEND")

    vector_db: Literal["qdrant","milvus","memory"] = Field(default="memory", validation_alias="VECTOR_DB")
    qdrant_url: str = Field(default="http://localhost:6333", validation_alias="QDRANT_URL")
    qdrant_api_key: str | None = Field(default=None, validation_alias="QDRANT_API_KEY")
    milvus_uri: str = Field(default="http://localhost:19530", validation_alias="MILVUS_URI")

    vlm_model: str = Field(default="google/gemma-3-12b-it", validation_alias="VLM_MODEL")
    vlm_quantization: Literal["awq-4bit","gptq-4bit","int8","fp16","mock"] = Field(default="mock", validation_alias="VLM_QUANTIZATION")
    vlm_engine: Literal["transformers","vllm","mock"] = Field(default="mock", validation_alias="VLM_ENGINE")
    vlm_device: str = Field(default="cuda", validation_alias="VLM_DEVICE")
    max_context_window: int = Field(default=8192, validation_alias="MAX_CONTEXT_WINDOW")
    image_width: int = Field(default=768, validation_alias="IMAGE_WIDTH")
    vram_limit_gb: int = Field(default=16, validation_alias="VRAM_LIMIT_GB")
    empty_cache_after_page: bool = Field(default=True, validation_alias="EMPTY_CACHE_AFTER_PAGE")
    max_concurrent_vlm: int = Field(default=1, validation_alias="MAX_CONCURRENT_VLM")

    ocr_engine: Literal["easyocr","paddleocr","mock"] = Field(default="mock", validation_alias="OCR_ENGINE")
    ocr_ensemble: bool = Field(default=True, validation_alias="OCR_ENSEMBLE")
    ocr_fallback_threshold: float = Field(default=0.7, validation_alias="OCR_FALLBACK_THRESHOLD")

    storage_path: str = Field(default="./storage", validation_alias="STORAGE_PATH")
    gosts_path: str = Field(default="./storage/gosts", validation_alias="GOSTS_PATH")
    gallery_path: str = Field(default="./storage/gallery", validation_alias="GALLERY_PATH")

    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=1440, validation_alias="JWT_EXPIRE_MINUTES")
    koseven_enabled: bool = Field(default=False, validation_alias="KOSEVEN_ENABLED")
    koseven_db_dsn: str | None = Field(default=None, validation_alias="KOSEVEN_DB_DSN")
    koseven_table: str = Field(default="koseven_users", validation_alias="KOSEVEN_TABLE")

    mcp_enabled: bool = Field(default=True, validation_alias="MCP_ENABLED")
    cors_origins: str = Field(default="*", validation_alias="CORS_ORIGINS")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    # Observability / Reliability
    enable_metrics: bool = Field(default=True, validation_alias="ENABLE_METRICS")
    dedupe_window_minutes: int = Field(default=5, validation_alias="DEDUPE_WINDOW_MINUTES")
    queue_max_retries: int = Field(default=3, validation_alias="QUEUE_MAX_RETRIES")
    enable_sse: bool = Field(default=True, validation_alias="ENABLE_SSE")

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    def effective_vector_db(self) -> str:
        if self.app_env == "development" and self.vector_db in ("qdrant","milvus"):
            return self.vector_db
        return self.vector_db

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()

# Ensure storage dirs
for p in [settings.storage_path, settings.gosts_path, settings.gallery_path, os.path.join(settings.storage_path, "uploads"), os.path.join(settings.storage_path, "checks"), os.path.join(settings.storage_path, "retrain")]:
    os.makedirs(p, exist_ok=True)
