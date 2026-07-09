from pathlib import Path

from app.core.config import LOCAL_ENV_FILE, PROJECT_ROOT, Settings
from app.llm.config_health import (
    format_llm_config_health,
    get_llm_config_health,
    llm_degradation_message,
)
from app.llm.qwen_provider import QwenTextProvider
from app.llm.router import LLMRouter


def test_local_env_path_is_repository_root() -> None:
    assert LOCAL_ENV_FILE == PROJECT_ROOT / ".env"
    assert LOCAL_ENV_FILE.parent.name == "项目15:港区审计需求"


def test_placeholder_key_is_not_configured() -> None:
    settings = Settings(
        _env_file=None,
        enable_llm=True,
        llm_provider="qwen",
        qwen_api_key="PASTE_YOUR_KEY_HERE",
        qwen_base_url="",
        qwen_vision_model="",
        qwen_text_model="",
    )

    health = get_llm_config_health(settings)

    assert health.api_key_present is False
    assert health.api_key_length == 0
    assert health.configuration_ready is False
    assert set(health.missing_fields) == {
        "BID_REVIEW_QWEN_API_KEY",
        "BID_REVIEW_QWEN_BASE_URL",
        "BID_REVIEW_QWEN_VISION_MODEL",
        "BID_REVIEW_QWEN_TEXT_MODEL",
    }
    assert llm_degradation_message(health) == "Qwen 未配置，自动降级为文本提取/规则流程"
    output = format_llm_config_health(health)
    assert "API key present: false" in output
    assert "API key length: 0" in output
    assert "Configuration ready: false" in output
    assert "PASTE_YOUR_KEY_HERE" not in output


def test_qwen_routes_to_qwen_text_provider(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, enable_llm=True, llm_provider="qwen")

    router = LLMRouter(settings, tmp_path / "calls.jsonl")

    assert isinstance(router.text, QwenTextProvider)
