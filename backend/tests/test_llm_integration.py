import os

import pytest

from app.core.config import Settings
from app.llm.router import LLMRouter
from app.schemas.phase_a import ModelPageExtraction


@pytest.mark.skipif(
    os.getenv("RUN_LLM_INTEGRATION_TESTS", "").lower() != "true",
    reason="真实模型测试必须显式启用",
)
def test_configured_text_provider(tmp_path) -> None:
    settings = Settings()
    router = LLMRouter(settings, tmp_path / "llm_calls.jsonl")
    assert router.text.configured, "启用集成测试前必须配置文本 Provider"

    result = router.call(
        task_name="integration_json",
        prompt='仅返回 {"facts": []}',
        output_schema=ModelPageExtraction,
        input_pages=[],
        text="无待提取事实。",
    )

    assert isinstance(result, ModelPageExtraction)
