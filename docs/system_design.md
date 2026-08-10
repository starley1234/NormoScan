# System Design — НормоСкан

## 1. Архитектура

```
[PDF] -> Preprocess (pypdfium2 512-800px) -> Segmentation (OpenCV кроп) -> OCR (Easy/Paddle) -\
                                                                                               -> Hybrid RAG (Qdrant) -> VLM (Gemma-3/Qwen2-VL 4-bit) -> JSON -> Consistency -> Report
```

- **VRAM 16GB**: 4-bit AWQ/GPTQ, 768px width, paged attention (vLLM/SGLang), `torch.cuda.empty_cache()` после каждой страницы, 1 concurrent generation + CPU preprocessing pipeline.
- **Контекстное окно**: `MAX_CONTEXT_WINDOW` 8192 (Gemma до 32768). Суммаризация предыдущих листов: передается `summary_prev` (последние ~800 символов) в промпт следующего листа, чтобы сверять Обозначение/Наименование.

## 2. Схема БД

### PostgreSQL (SQLAlchemy)
```
users(id, username, email, hashed_password, role[admin/normocontroller/engineer/viewer], is_active, koseven_id, created_at)
checks(id, filename, filepath, status[queued/processing/done/failed], priority 1..10, created_by FK users, created_at, finished_at, pages_total/done, meta_json JSONB, errors_json JSONB, summary TEXT, consistency_json JSONB)
page_results(id, check_id FK, page_number, status, ocr_text TEXT, vlm_output JSONB, errors JSONB, crops JSONB, visual_hits JSONB, text_hits JSONB)
feedbacks(id, check_id FK, page_number, error_id, vote[like/dislike], comment, created_by FK, created_at)
gosts(id, designation, title, filepath, content_text TEXT, chunks_json JSONB, status, created_at, updated_at)
gallery(id, title, category[error/etalon], gost_ref, error_type, filepath, embedding_id, meta_json JSONB, created_at)
```

### VectorDB (Qdrant / Milvus / memory)
- Collections:
  - `gosts_text` (dim 384 MiniLM, cosine) — payload: designation, title, text, filepath, chunk_idx
  - `gallery_visual` (CLIP ViT-B/32 or hash mock) — payload: title, category, gost_ref, error_type, filepath
  - `checks_meta` — для knowledge base поиска

## 3. API (FastAPI)

Swagger: `/docs`

| Метод | Путь | Роль | Описание |
|-------|------|------|----------|
| POST | /api/auth/login | - | JWT |
| POST | /api/checks/upload | engineer+ | Загрузка PDF, priority 1..10 |
| GET | /api/checks/ | viewer+ | Реестр |
| GET | /api/checks/{id} | viewer+ | Детали + постранично |
| POST | /api/checks/feedback | any | 👍/👎 |
| POST | /api/gosts/ingest | normocontroller+ | Индексация папки |
| POST | /api/gosts/search | viewer+ | Text RAG |
| POST | /api/gallery/upload | normocontroller+ | Добавить эталон |
| POST | /api/gallery/search | viewer+ | Visual RAG |
| GET | /api/analytics/summary | viewer+ | LLM-отчет |
| GET/POST | /api/admin/settings | admin | Модель, контекст, VRAM |
| POST | /mcp | - | MCP JSON-RPC |
| GET | /health | - | health |

## 4. Очередь и ресурсы

- Celery queues: `high` (priority 1-3), `normoscan` (4-7), `low` (8-10). Redis broker.
- Worker concurrency 1 для VLM (VRAM), OCR/векторизация параллелится на CPU.
- Освобождение VRAM: `torch.cuda.empty_cache()` + `torch.cuda.ipc_collect()` после каждой страницы, vLLM `gpu_memory_utilization=0.9`.

## 5. Безопасность

- Локальный инференс (localhost), нет внешних API.
- JWT + RBAC matrix, Koseven интеграция через `X-Koseven-Role` header и таблицу `koseven_users` (маппинг ролей).
- CORS allow preview host `*.e2b.app`.

## 6. Масштабирование

- Горизонтально: воркеры Celery + Qdrant кластер + S3.
- Модель: vLLM tensor_parallel 1 на 16GB, для 2xGPU — tensor_parallel 2.
