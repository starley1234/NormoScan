# НормоСкан — Сервис интеллектуального нормоконтроля

Автоматизация проверки конструкторской документации (КД) на соответствие ГОСТ/СТП с мультимодальными VLM и Visual RAG.

![license](https://img.shields.io/badge/license-MIT-blue) ![python](https://img.shields.io/badge/python-3.11%2B-blue) ![stack](https://img.shields.io/badge/VRAM-16GB%20optimized-green)

## Архитектура

```
┌──────────┐   ┌──────────────┐   ┌─────────┐   ┌──────────┐   ┌─────────┐
│ Frontend │──▶│   FastAPI    │──▶│ Celery  │──▶│ VLM/OCR  │──▶│ VectorDB│
│Streamlit/│   │  REST + MCP  │   │ + Redis │   │Qwen2‑VL  │   │ Qdrant/ │
│  React   │◀──│   RBAC       │◀──│ Queue   │◀──│ Gemma‑3  │◀──│ Milvus  │
└──────────┘   └──────────────┘   └─────────┘   └──────────┘   └─────────┘
                        │                     │
                        ▼                     ▼
                ┌──────────────┐      ┌──────────────┐
                │ PostgreSQL   │      │  S3/MinIO    │
                │ Registry     │      │  Хранилище   │
                └──────────────┘      └──────────────┘
```

**Стек:** Python 3.11, FastAPI, Celery, Redis, PostgreSQL, Qdrant/Milvus, PyTorch, vLLM/SGLang, EasyOCR/PaddleOCR, Streamlit/React, Qwen2-VL-7B / Gemma-3-12B (4-bit AWQ/GPTQ), transformers, bitsandbytes.

**Оптимизация VRAM 16GB:**
- 4-bit AWQ/GPTQ/INT8 квантование
- Постраничный инференс, `torch.cuda.empty_cache()` после каждой страницы
- Вход 512–800px по ширине, интеллектуальный кроп на зоны
- 1 активная генерация + фоновая подготовка OCR/векторизации на CPU (pipeline parallelism)
- vLLM/SGLang с paged attention

## Быстрый старт

### Локально без Docker (для разработки)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt
cp .env.example .env

# БД (SQLite по умолчанию, для prod — Postgres)
alembic upgrade head  # если postgres

# Бэкенд
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# Воркер
celery -A backend.app.celery_app worker --loglevel=INFO -Q normoscan,high,low

# Frontend
streamlit run frontend/app.py --server.port 8501 --server.address 0.0.0.0
```

### Docker Compose
```bash
docker compose up --build
# Frontend: http://localhost:8501
# API: http://localhost:8000/docs
# Qdrant: http://localhost:6333/dashboard
```

## Основные модули

| Модуль | Описание |
|--------|----------|
| **Препроцессинг** | `pypdfium2`/`PyMuPDF` разбивка PDF, адаптивный ресайз 512–800px, интеллектуальный кроп (штамп, техтребования, спецификация, графика) через детекцию контуров + VLM |
| **Hybrid RAG** | Text RAG (эмбеддинги ГОСТов → Qdrant) + Visual RAG (CLIP/ViT галерея эталонов/ошибок, косинусная близость) |
| **Анализ JSON** | Извлечение метаданных (Обозначение, Наименование, Материал, Масса, Литера), сверка консистентности между листами, суммаризация контекста |
| **Очередь** | Celery priority queue (high/normal/low), освобождение VRAM, таймауты, ретраи |
| **Реестр/Аналитика** | История проверок, LLM-отчеты («в отделе №5 рост ошибок ГОСТ 2.307») |

## RBAC и интеграция с Koseven

Роли: `admin`, `normocontroller`, `engineer`, `viewer`. Совместимость с Koseven (Kohana) — JWT/сессия, маппинг ролей через `X-Koseven-Role` header и таблицу `koseven_users`.

## MCP протокол

Сервер MCP (`/mcp`) экспонирует инструменты:
- `check_drawing` — проверить чертеж
- `ask_gost` — вопрос по ГОСТу
- `ask_document` — вопрос по загруженному документу
- `search_gallery` — поиск по галерее ошибок
- `get_check_status` — статус проверки

Совместим с Claude Desktop, Continue, Cursor.

См. [docs/mcp.md](docs/mcp.md)

## База ГОСТов

Укажите папку с PDF ГОСТов — сервис сам проиндексирует:
```bash
python scripts/ingest_gosts.py --gost-dir /data/gosts --vector-db qdrant
# или через API: POST /api/gosts/ingest { "path": "/data/gosts" }
```

## Настройки (Settings)

В `Админка → Настройки` или `.env`:
- `VLM_MODEL` (default: `google/gemma-3-12b-it`, fallback `Qwen/Qwen2-VL-7B-Instruct`)
- `VLM_QUANTIZATION` (`awq-4bit`/`gptq-4bit`/`int8`/`fp16`)
- `MAX_CONTEXT_WINDOW` (токенов, default 8192, max 32768 для Gemma)
- `IMAGE_WIDTH` (512–800px)
- `VRAM_LIMIT_GB`, `EMPTY_CACHE_AFTER_PAGE`, `MAX_CONCURRENT_VLM`

## Тестирование

```bash
pytest -q                          # unit + rag + integration
pytest tests/vlm --run-vlm         # VLM accuracy vs ground truth
locust -f tests/load/locustfile.py # нагрузка 10 юзеров / 16GB
```

Таблица испытаний: см. [docs/system_design.md](docs/system_design.md)

## Документация

- [System Design](docs/system_design.md) — схема БД, архитектура
- [API Spec](docs/api_spec.md) — Swagger
- [Quantization & Deploy](docs/quantization.md) — vLLM/Ollama/llama.cpp
- [User Guide](docs/user_guide.md) — JSON схемы, обучение Visual RAG
- [Admin Guide](docs/admin_guide.md) — очереди, обновление ГОСТов

## Безопасность

Весь инференс локальный, данные не уходят во внешние API. PII маскируется.

## Лицензия

MIT
