from celery import Celery

from .config import settings

# логи в файл и буфер как у backend — чтобы UI Логи видел celery
try:
    from .core.logging import setup_logging
    setup_logging()
except:
    pass

celery_app = Celery(
    "normoscan",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.tasks.process_check_high": {"queue": "high"},
        "app.tasks.process_check": {"queue": "normoscan"},
        "app.tasks.process_check_low": {"queue": "low"},
    },
    task_default_queue="normoscan",
    # priority support via redis
    broker_transport_options={"priority_steps": list(range(10)), "queue_order_strategy": "priority"},
)

# For dev without Redis, allow eager
if settings.app_env=="development":
    # if redis not reachable, tasks will fallback to eager in tasks.py
    pass
