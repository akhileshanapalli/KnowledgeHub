from celery import Celery
from app.config import settings

celery_app = Celery(
    "knowledgehub_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.ingestion"],
)

is_eager = (settings.ENVIRONMENT == "test")
if not is_eager:
    try:
        import redis
        r = redis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=0.5, socket_timeout=0.5)
        r.ping()
    except Exception:
        is_eager = True

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,       # 10 minutes hard limit
    task_soft_time_limit=540,  # 9 minutes soft limit
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=False,
    broker_connection_timeout=1.0,
    task_always_eager=is_eager,
)
