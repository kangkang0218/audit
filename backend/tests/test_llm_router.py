from app.core.config import Settings
from app.llm.mock import MockProvider
from app.llm.router import LLMRouter
from app.schemas.phase_a import ModelPageExtraction


def test_mock_provider_and_failure_degradation(tmp_path) -> None:
    settings = Settings(_env_file=None, database_url="sqlite+pysqlite:///:memory:")
    success = MockProvider({"facts": [{"field_name": "缴款证明金额", "value": "10000 元", "confidence": 0.9}]})
    router = LLMRouter(settings, tmp_path / "calls.jsonl", visual_provider=success, text_provider=success)
    result = router.call(
        task_name="test",
        prompt="extract",
        output_schema=ModelPageExtraction,
        input_pages=[1],
        image_path=tmp_path / "unused.png",
    )
    assert isinstance(result, ModelPageExtraction)

    failing = MockProvider(fail=True)
    router = LLMRouter(settings, tmp_path / "calls.jsonl", visual_provider=failing, text_provider=failing)
    assert (
        router.call(
            task_name="failure",
            prompt="extract",
            output_schema=ModelPageExtraction,
            input_pages=[2],
        )
        is None
    )
    assert "mock provider failure" in (tmp_path / "calls.jsonl").read_text()
