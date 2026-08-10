# Инструкция администратора — НормоСкан

## 1. Установка

```bash
git clone https://github.com/starley1234/NormoScan
cp .env.example .env
# отредактируйте .env (см. ниже)
docker compose up --build
```

Или локально:
```bash
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
celery -A backend.app.celery_app worker -Q high,normoscan,low --concurrency=1
streamlit run frontend/app.py --server.port 8501
```

## 2. Настройка лимитов очереди

В `.env`:
```
CELERY_BROKER_URL=redis://redis:6379/1
MAX_CONCURRENT_VLM=1        # 1 для 16GB, 2 для 24GB+
VRAM_LIMIT_GB=16
EMPTY_CACHE_AFTER_PAGE=true
```

В админке (`/api/admin/queue`):
- Просмотр активных/зарезервированных задач
- `POST /api/admin/queue/purge` — очистить очередь
- Приоритеты: `?priority=1` (high) … `10` (low) при загрузке

Мониторинг: `celery -A backend.app.celery_app flower --port 5555`

## 3. Обновление базы ГОСТов

### Вариант A: Папка (рекомендуется)
```bash
# Положите PDF ГОСТов в ./storage/gosts (подпапки поддерживаются)
python scripts/ingest_gosts.py --gost-dir ./storage/gosts --vector-db qdrant
# или через API
curl -X POST http://localhost:8000/api/gosts/ingest -H "Authorization: Bearer <token>" -d '{"path":"./storage/gosts"}'
```

### Вариант B: Один файл
```bash
curl -X POST http://localhost:8000/api/gosts/upload \
  -H "Authorization: Bearer <token>" \
  -F file=@ГОСТ_2.104-2006.pdf -F designation="ГОСТ 2.104-2006"
```

Проверка:
```bash
curl -X POST http://localhost:8000/api/gosts/search -H "Authorization: Bearer <token>" -d '{"query":"основная надпись","top_k":3}'
```

Переиндексация: просто повторно запустите ingest — чанки перезапишутся (upsert по ID).

## 4. Управление пользователями и RBAC

- `GET /api/admin/users` — список
- `POST /api/admin/users/{id}/role?role=normocontroller` — смена роли
- Роли: `admin`, `normocontroller`, `engineer`, `viewer`

Koseven интеграция:
```
KOSEVEN_ENABLED=true
KOSEVEN_DB_DSN=mysql://user:pass@host/koseven
KOSEVEN_TABLE=koseven_users
```
Прилетает заголовок `X-Koseven-Role: admin|normocontrol|engineer|user` → маппится во внутреннюю роль.

## 5. Настройки модели

`GET/POST /api/admin/settings` (только admin):

```json
{
  "vlm_model": "google/gemma-3-12b-it",
  "vlm_quantization": "awq-4bit",
  "max_context_window": 8192,
  "image_width": 768,
  "vram_limit_gb": 16,
  "empty_cache_after_page": true,
  "max_concurrent_vlm": 1
}
```

Ограничения:
- `max_context_window` 2048..32768
- `image_width` 512..800

После смены `vlm_model` перезапустите worker: `docker compose restart celery_worker`.

## 6. Резервное копирование

- PostgreSQL: `pg_dump -h localhost -U normoscan normoscan > backup.sql`
- Qdrant: snapshot `curl -X POST http://localhost:6333/snapshots`
- Storage: `tar czf storage_backup.tar.gz storage/`

## 7. Логи и отладка

- Backend: `docker compose logs backend`
- Worker: `docker compose logs celery_worker`
- Feedback на дообучение: `storage/retrain/feedback.log`
- Health: `GET /health`

## 8. Безопасность

- Весь инференс локальный, `mcp` и `api` — внутри сети
- Смените `SECRET_KEY` в `.env`
- Для prod: `APP_ENV=production`, `CORS_ORIGINS=https://yourdomain`
