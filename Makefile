.PHONY: up down logs backend worker test ingest quantize

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

backend:
	uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

worker:
	celery -A backend.app.celery_app worker --loglevel=INFO -Q high,normoscan,low --concurrency=1

test:
	pytest -q

ingest:
	python scripts/ingest_gosts.py --gost-dir ./storage/gosts

quantize:
	python scripts/quantize_model.py --model google/gemma-3-12b-it --quant awq-4bit

web:
	@echo "Web UI available at http://localhost:8000/web/"
