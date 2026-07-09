from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.llm.base import LLMProvider
from app.llm.mock import MockProvider
from app.llm.openai_compatible import InvalidJSONResponse
from app.llm.verification import verify_qwen, verify_qwen_vision


def ready_settings() -> Settings:
    return Settings(
        _env_file=None,
        enable_llm=True,
        llm_provider="qwen",
        qwen_api_key="x" * 16,
        qwen_base_url="https://invalid.local",
        qwen_vision_model="vision-test-model",
        qwen_text_model="text-test-model",
    )


def test_verify_uses_minimal_mock_request() -> None:
    provider = MockProvider({"status": "ok"})

    result = verify_qwen(ready_settings(), provider=provider)

    assert result.reachable is True
    assert result.schema_validated is True
    assert result.model_name == "deterministic-test"


class SecretEchoFailure(LLMProvider):
    name = "mock"
    model = "failure-test"

    def __init__(self, secret: str) -> None:
        self.secret = secret

    @property
    def configured(self) -> bool:
        return True

    def extract_json(
        self,
        *,
        task_name: str,
        prompt: str,
        text: str | None = None,
        image_path: Path | None = None,
    ) -> dict[str, Any]:
        raise RuntimeError(
            f"Authorization: Bearer {self.secret} data:image/png;base64,AAAA"
        )


def test_verify_redacts_key_from_error() -> None:
    settings = ready_settings()
    provider = SecretEchoFailure(settings.qwen_api_key or "")

    result = verify_qwen(settings, provider=provider)

    assert result.reachable is False
    assert result.error_summary is not None
    assert settings.qwen_api_key not in result.error_summary
    assert "[REDACTED]" in result.error_summary
    assert "Bearer" not in result.error_summary
    assert "base64" not in result.error_summary


def test_verify_vision_redacts_transport_details() -> None:
    settings = ready_settings()
    provider = SecretEchoFailure(settings.qwen_api_key or "")

    result = verify_qwen_vision(
        settings,
        provider=provider,
        repair_provider=MockProvider(),
    )

    assert result.reachable is False
    assert result.error_summary is not None
    assert settings.qwen_api_key not in result.error_summary
    assert "Bearer" not in result.error_summary
    assert "base64" not in result.error_summary


class RecordingVisionProvider(LLMProvider):
    name = "mock"
    model = "vision-mock"

    def __init__(self) -> None:
        self.image_path: Path | None = None
        self.prompt = ""
        self.calls = 0

    @property
    def configured(self) -> bool:
        return True

    def extract_json(
        self,
        *,
        task_name: str,
        prompt: str,
        text: str | None = None,
        image_path: Path | None = None,
    ) -> dict[str, Any]:
        self.calls += 1
        self.prompt = prompt
        self.image_path = image_path
        assert image_path is not None
        assert image_path.name == "synthetic-vision-check.png"
        assert image_path.suffix == ".png"
        assert image_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        assert text is None
        return {"name": "张三", "amount": "10000元", "date": "2024年8月13日"}


def test_verify_vision_uses_temporary_synthetic_png_only() -> None:
    provider = RecordingVisionProvider()

    result = verify_qwen_vision(
        ready_settings(),
        provider=provider,
        repair_provider=MockProvider(),
    )

    assert result.reachable is True
    assert result.request_accepted is True
    assert result.schema_validated is True
    assert provider.calls == 1
    assert provider.image_path is not None
    assert provider.image_path.exists() is False
    assert "严格 JSON" in provider.prompt


class NonJSONVisionProvider(RecordingVisionProvider):
    def extract_json(
        self,
        *,
        task_name: str,
        prompt: str,
        text: str | None = None,
        image_path: Path | None = None,
    ) -> dict[str, Any]:
        self.calls += 1
        self.image_path = image_path
        raise InvalidJSONResponse("not-json")


class RecordingRepairProvider(MockProvider):
    def __init__(self, response: dict[str, Any]) -> None:
        super().__init__(response)
        self.calls = 0
        self.prompt = ""

    def extract_json(
        self,
        *,
        task_name: str,
        prompt: str,
        text: str | None = None,
        image_path: Path | None = None,
    ) -> dict[str, Any]:
        self.calls += 1
        self.prompt = prompt
        return super().extract_json(
            task_name=task_name,
            prompt=prompt,
            text=text,
            image_path=image_path,
        )


def test_non_json_vision_response_repairs_exactly_once() -> None:
    visual = NonJSONVisionProvider()
    repair = RecordingRepairProvider(
        {"name": "张三", "amount": "10000元", "date": "2024年8月13日"}
    )

    result = verify_qwen_vision(
        ready_settings(),
        provider=visual,
        repair_provider=repair,
    )

    assert result.schema_validated is True
    assert visual.calls == 1
    assert repair.calls == 1
    assert "只修复 JSON 格式，不得补充不存在的事实" in repair.prompt


def test_failed_repair_is_not_retried() -> None:
    visual = NonJSONVisionProvider()
    repair = RecordingRepairProvider({"name": "不存在的新增事实"})

    result = verify_qwen_vision(
        ready_settings(),
        provider=visual,
        repair_provider=repair,
    )

    assert result.schema_validated is False
    assert visual.calls == 1
    assert repair.calls == 1
