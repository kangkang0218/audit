from typing import Any

from app.tasks.celery_app import celery_app


@celery_app.task(
    bind=True,
    autoretry_for=(TimeoutError, ConnectionError),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
    name="bid_review.pipeline.process_document",
)
def process_document(
    self: Any, *, document_id: str, run_id: str, idempotency_key: str
) -> dict[str, str]:
    """Phase B hook for the recoverable PDF processing pipeline."""
    return {
        "status": "skeleton",
        "document_id": document_id,
        "run_id": run_id,
        "idempotency_key": idempotency_key,
        "task_id": self.request.id or "",
    }

