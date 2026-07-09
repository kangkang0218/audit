from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import fitz
import httpx
import pytest

from app.core.config import Settings
from app.llm.base import LLMProvider
from app.llm.mock import MockProvider
from app.llm.openai_compatible import InvalidJSONResponse
from app.services.page_evaluation import (
    contains_sensitive_leak,
    detect_task_type,
    evaluate_pages,
    inspect_page_evaluation,
)


def _make_pdf(path: Path, texts: list[str]) -> None:
    document = fitz.open()
    try:
        for text in texts:
            page = document.new_page(width=595, height=842)
            page.insert_textbox(
                fitz.Rect(50, 50, 545, 792),
                text,
                fontname="china-s",
                fontsize=12,
            )
        document.save(path)
    finally:
        document.close()


def _settings(secret: str = "test-secret-key") -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        qwen_api_key=secret,
        qwen_base_url="https://invalid.local",
        qwen_vision_model="vision-test",
        qwen_text_model="text-test",
    )


def test_task_detection_prefers_current_subheading_over_section_title() -> None:
    bid_letter = "一、投标函及投标函附录\n（一）投标函\n正文"
    bid_appendix = "一、投标函及投标函附录\n（二）投标函附录\n正文"
    assert detect_task_type(bid_letter) == "bid_letter"
    assert detect_task_type(bid_appendix) == "bid_appendix"


class RecordingProvider(LLMProvider):
    name = "mock"
    model = "vision-mock"

    def __init__(self, fail_pages: set[int] | None = None) -> None:
        self.fail_pages = fail_pages or set()
        self.calls: list[dict[str, Any]] = []

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
        assert image_path is not None
        page = int(image_path.stem.split("_")[1])
        self.calls.append(
            {
                "task_name": task_name,
                "prompt": prompt,
                "text": text,
                "image_path": image_path,
            }
        )
        if page in self.fail_pages:
            raise RuntimeError(
                "Authorization: Bearer test-secret-key data:image/png;base64,AAAA"
            )
        task_type = task_name.rsplit(".", 1)[-1]
        if task_type == "personnel_table":
            return {
                "rows": [
                    {
                        "name": "张三",
                        "role": "项目负责人",
                        "title": "高级",
                        "certificate_level": "一级",
                        "certificate_numbers": ["410327198011015611"],
                        "specialty": "土木建筑",
                        "manual_review_required": False,
                        "note": "社保号 13812345678",
                    }
                ],
                "page_has_personnel_table": True,
                "manual_review_notes": [],
            }
        return {
            "task_type": task_type,
            "material_found": True,
            "fields": [
                {
                    "field_name": "姓名",
                    "value": "张三",
                    "status": "已提取",
                    "evidence": "本页姓名栏",
                },
                {
                    "field_name": "身份证号",
                    "value": 410327198011015611,
                    "status": "需人工复核",
                },
            ],
            "notes": [],
        }


def test_only_requested_pages_are_rendered_and_sent(tmp_path: Path) -> None:
    pdf = tmp_path / "sample.pdf"
    _make_pdf(pdf, ["投标函 姓名 13812345678", "绝不能发送这一页", "授权委托书"])
    provider = RecordingProvider()

    summary = evaluate_pages(
        pdf,
        [1, 3],
        tmp_path / "out",
        _settings(),
        task_map={1: "bid_letter", 3: "authorization"},
        visual_provider=provider,
        repair_provider=MockProvider(),
    )

    assert summary.requested_pages == [1, 3]
    assert [call["image_path"].name for call in provider.calls] == [
        "page_001.png",
        "page_003.png",
    ]
    assert not (tmp_path / "out/pages/page_002.png").exists()
    assert all("绝不能发送" not in (call["text"] or "") for call in provider.calls)
    assert "138****5678" in provider.calls[0]["text"]


def test_each_result_is_schema_validated_and_sanitized(tmp_path: Path) -> None:
    pdf = tmp_path / "sample.pdf"
    _make_pdf(pdf, ["项目负责人及项目组成员 职务 姓名 证号"])
    output = tmp_path / "out"

    summary = evaluate_pages(
        pdf,
        [1],
        output,
        _settings(),
        task_map={1: "personnel_table"},
        visual_provider=RecordingProvider(),
        repair_provider=MockProvider(),
    )

    assert summary.results[0].schema_valid is True
    result = json.loads(
        (output / "results/page_001_personnel_table.json").read_text(encoding="utf-8")
    )
    assert result["rows"][0]["certificate_numbers"] == [
        "410327********5611"
    ]
    assert "138****5678" in result["rows"][0]["note"]
    assert contains_sensitive_leak(result) is False
    assert contains_sensitive_leak("410327198 011015611") is True
    all_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in output.rglob("*")
        if path.is_file() and path.suffix in {".json", ".jsonl"}
    )
    assert "test-secret-key" not in all_text
    assert "Bearer" not in all_text
    assert "base64" not in all_text
    assert "410327198011015611" not in all_text


class NonJSONProvider(RecordingProvider):
    def extract_json(
        self,
        *,
        task_name: str,
        prompt: str,
        text: str | None = None,
        image_path: Path | None = None,
    ) -> dict[str, Any]:
        self.calls.append({"image_path": image_path})
        raise InvalidJSONResponse("not-json")


class CountingRepairProvider(MockProvider):
    def __init__(self, response: dict[str, Any]) -> None:
        super().__init__(response)
        self.calls = 0

    def extract_json(
        self,
        *,
        task_name: str,
        prompt: str,
        text: str | None = None,
        image_path: Path | None = None,
    ) -> dict[str, Any]:
        self.calls += 1
        assert "只修复 JSON 格式，不得补充不存在的事实" in prompt
        return super().extract_json(
            task_name=task_name,
            prompt=prompt,
            text=text,
            image_path=image_path,
        )


def test_non_json_is_repaired_at_most_once(tmp_path: Path) -> None:
    pdf = tmp_path / "sample.pdf"
    _make_pdf(pdf, ["投标函"])
    visual = NonJSONProvider()
    repair = CountingRepairProvider({"still": "invalid"})

    summary = evaluate_pages(
        pdf,
        [1],
        tmp_path / "out",
        _settings(),
        task_map={1: "bid_letter"},
        visual_provider=visual,
        repair_provider=repair,
    )

    assert summary.failed_pages == [1]
    assert len(visual.calls) == 1
    assert repair.calls == 1


def test_one_page_failure_does_not_stop_other_pages(tmp_path: Path) -> None:
    pdf = tmp_path / "sample.pdf"
    _make_pdf(pdf, ["投标函", "投标保证金", "养老保险缴纳证明"])
    provider = RecordingProvider(fail_pages={2})

    summary = evaluate_pages(
        pdf,
        [1, 2, 3],
        tmp_path / "out",
        _settings(),
        task_map={1: "bid_letter", 2: "guarantee", 3: "social_security"},
        visual_provider=provider,
        repair_provider=MockProvider(),
    )

    assert summary.successful_pages == [1, 3]
    assert summary.failed_pages == [2]
    assert len(provider.calls) == 3
    assert (tmp_path / "out/results/page_002_guarantee.json").is_file()


def test_inspect_is_local_and_reports_leak_scan(tmp_path: Path) -> None:
    pdf = tmp_path / "sample.pdf"
    _make_pdf(pdf, ["投标函"])
    output = tmp_path / "out"
    provider = RecordingProvider()
    evaluate_pages(
        pdf,
        [1],
        output,
        _settings(),
        task_map={1: "bid_letter"},
        visual_provider=provider,
        repair_provider=MockProvider(),
    )
    calls_before = len(provider.calls)

    report = inspect_page_evaluation(output)

    assert len(provider.calls) == calls_before
    assert report[0]["pdf_page"] == 1
    assert report[0]["schema_valid"] is True
    assert report[0]["sensitive_number_leak"] is False


def test_missing_external_confirmation_never_loads_settings_or_calls_model(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    cli = importlib.import_module("app.cli.main")
    monkeypatch.setattr(
        cli,
        "get_settings",
        lambda: (_ for _ in ()).throw(AssertionError("不得加载外部模型配置")),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "bid-review",
            "evaluate-pages",
            "--input",
            str(tmp_path / "never-read.pdf"),
            "--pages",
            "1",
            "--output",
            str(tmp_path / "never-created"),
            "--provider",
            "qwen",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        cli.main()

    captured = capsys.readouterr()
    assert exc.value.code != 0
    assert "指定 PDF 页面图片及脱敏文本" in captured.out
    assert "--confirm-external-processing" in captured.err
    assert not (tmp_path / "never-created").exists()
