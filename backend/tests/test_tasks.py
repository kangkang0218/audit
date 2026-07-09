from app.tasks.pipeline import process_document


def test_pipeline_task_skeleton_contract() -> None:
    result = process_document.run(
        document_id="document-id",
        run_id="run-id",
        idempotency_key="run-id:document-id:pipeline-v1",
    )

    assert result["status"] == "skeleton"
    assert result["idempotency_key"] == "run-id:document-id:pipeline-v1"

