from celery import Celery

from app.core.config import get_settings

settings = get_settings()
celery_app = Celery(
    "bid_review",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.pipeline"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_default_queue="bid-review.default",
    task_time_limit=30 * 60,
    task_soft_time_limit=25 * 60,
    result_expires=24 * 60 * 60,
)

