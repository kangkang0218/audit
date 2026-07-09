from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import fitz
import httpx
import pytest

from app.core.config import Settings
from app.llm.base import LLMProvider
from app.llm.mock import MockProvider
from app.llm.qwen_provider import QwenVisionProvider
from app.services.page_evaluation import evaluate_pages


def _settings(**overrides: Any) -> Settings:
    values = {
        "_env_file": None,
        "environment": "test",
        "qwen_api_key": "test-secret-key",
        "qwen_base_url": "https://invalid.local",
        "qwen_vision_model": "vision-test",
        "qwen_text_model": "text-test",
        "llm_timeout_seconds": 60,
        "personnel_table_timeout_seconds": 150,
        "personnel_table_max_retries": 1,
        "personnel_table_dpi": 180,
        "personnel_table_max_long_edge": 1800,
        "personnel_table_retry_max_long_edge": 900,
    }
    values.update(overrides)
    return Settings(**values)


def _make_pdf(path: Path, page_count: int = 1) -> None:
    document = fitz.open()
    try:
        for index in range(page_count):
            page = document.new_page(width=595, height=842)
            text = (
                "人员表 职务 姓名 证号"
                if index == page_count - 1
                else f"普通页面 {index + 1}"
            )
            page.insert_textbox(
                fitz.Rect(40, 40, 555, 802),
                text,
                fontname="china-s",
                fontsize=12,
            )
        document.save(path)
    finally:
        document.close()


def _payload(
    name: str = "测试人员",
    *,
    certificate_numbers: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "rows": [
            {
                "name": name,
                "role": "项目成员",
                "title": "高级",
                "certificate_level": "一级",
                "certificate_numbers": (
                    ["CERT-MASKED"] if certificate_numbers is None else certificate_numbers
                ),
                "specialty": "土木建筑",
                "manual_review_required": False,
                "note": None,
            }
        ],
        "page_has_personnel_table": True,
        "manual_review_notes": [],
    }


class SequenceProvider(LLMProvider):
    name = "mock"
    model = "personnel-mock"

    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = list(outcomes)
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
        pixmap = fitz.Pixmap(image_path)
        self.calls.append(
            {
                "task_name": task_name,
                "prompt": prompt,
                "text": text,
                "width": pixmap.width,
                "height": pixmap.height,
                "size_bytes": image_path.stat().st_size,
                "filename": image_path.name,
            }
        )
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _read_timeout() -> httpx.ReadTimeout:
    request = httpx.Request("POST", "https://invalid.local")
    return httpx.ReadTimeout("mock read timeout", request=request)


def _http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://invalid.local")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError(
        f"mock status {status}",
        request=request,
        response=response,
    )


def test_personnel_provider_uses_independent_read_timeout() -> None:
    settings = _settings()
    regular = QwenVisionProvider(settings)
    personnel = QwenVisionProvider(settings, personnel_table=True)

    assert regular.timeout.read == 60
    assert regular.timeout.connect == 60
    assert personnel.timeout.read == 150
    assert personnel.timeout.connect == 60
    assert personnel.timeout.write == 60
    assert personnel.timeout.pool == 60


def test_timeout_retries_once_with_smaller_image(tmp_path: Path) -> None:
    pdf = tmp_path / "sample.pdf"
    _make_pdf(pdf)
    provider = SequenceProvider([_read_timeout(), _payload()])
    output = tmp_path / "out"

    summary = evaluate_pages(
        pdf,
        [1],
        output,
        _settings(),
        task_type="personnel_table",
        retry_timeout_failures=True,
        visual_provider=provider,
        repair_provider=MockProvider(),
    )

    assert summary.successful_pages == [1]
    assert len(provider.calls) == 2
    first, second = provider.calls
    assert max(second["width"], second["height"]) < max(
        first["width"], first["height"]
    )
    assert second["size_bytes"] < first["size_bytes"]
    records = [
        json.loads(line)
        for line in (output / "llm_calls.jsonl").read_text().splitlines()
    ]
    assert [record["attempt"] for record in records] == [1, 2]
    assert records[0]["timeout_type"] == "ReadTimeout"
    assert records[1]["success"] is True


@pytest.mark.parametrize(
    "failure",
    [
        _http_error(401),
        _http_error(403),
        _http_error(429),
        RuntimeError("qwen Provider 配置不完整"),
    ],
)
def test_non_timeout_failures_do_not_retry(
    tmp_path: Path,
    failure: Exception,
) -> None:
    pdf = tmp_path / "sample.pdf"
    _make_pdf(pdf)
    provider = SequenceProvider([failure, _payload()])

    summary = evaluate_pages(
        pdf,
        [1],
        tmp_path / "out",
        _settings(),
        task_type="personnel_table",
        retry_timeout_failures=True,
        visual_provider=provider,
        repair_provider=MockProvider(),
    )

    assert summary.failed_pages == [1]
    assert len(provider.calls) == 1


def test_schema_error_does_not_retry(tmp_path: Path) -> None:
    pdf = tmp_path / "sample.pdf"
    _make_pdf(pdf)
    provider = SequenceProvider([{"unexpected": "value"}, _payload()])

    summary = evaluate_pages(
        pdf,
        [1],
        tmp_path / "out",
        _settings(),
        task_type="personnel_table",
        retry_timeout_failures=True,
        visual_provider=provider,
        repair_provider=MockProvider(),
    )

    assert summary.failed_pages == [1]
    assert len(provider.calls) == 1


def test_only_explicit_page_25_is_sent(tmp_path: Path) -> None:
    pdf = tmp_path / "sample.pdf"
    _make_pdf(pdf, page_count=25)
    provider = SequenceProvider([_payload()])

    summary = evaluate_pages(
        pdf,
        [25],
        tmp_path / "out",
        _settings(),
        task_type="personnel_table",
        visual_provider=provider,
        repair_provider=MockProvider(),
    )

    assert summary.requested_pages == [25]
    assert len(provider.calls) == 1
    assert provider.calls[0]["filename"].startswith("page_025_")
    assert not (tmp_path / "out/pages/page_024.png").exists()


def test_incomplete_result_is_marked_for_manual_review(tmp_path: Path) -> None:
    pdf = tmp_path / "sample.pdf"
    _make_pdf(pdf)
    provider = SequenceProvider([_payload(certificate_numbers=[])])
    output = tmp_path / "out"

    summary = evaluate_pages(
        pdf,
        [1],
        output,
        _settings(),
        task_type="personnel_table",
        visual_provider=provider,
        repair_provider=MockProvider(),
    )

    result = json.loads(
        (output / "results/page_001_personnel_table.json").read_text()
    )
    assert result["rows"][0]["manual_review_required"] is True
    assert summary.results[0].manual_review_fields == ["rows[0]"]


def test_auto_chunks_merge_in_reading_order(tmp_path: Path) -> None:
    pdf = tmp_path / "sample.pdf"
    _make_pdf(pdf)
    provider = SequenceProvider(
        [
            _payload(name="整页", certificate_numbers=[]),
            _payload(name="上半部分"),
            _payload(name="下半部分"),
        ]
    )
    output = tmp_path / "out"

    summary = evaluate_pages(
        pdf,
        [1],
        output,
        _settings(),
        task_type="personnel_table",
        personnel_table_strategy="auto",
        visual_provider=provider,
        repair_provider=MockProvider(),
    )

    result = json.loads(
        (output / "results/page_001_personnel_table.json").read_text()
    )
    assert summary.successful_pages == [1]
    assert [row["name"] for row in result["rows"]] == [
        "上半部分",
        "下半部分",
    ]
    records = [
        json.loads(line)
        for line in (output / "llm_calls.jsonl").read_text().splitlines()
    ]
    assert [record["phase"] for record in records] == [
        "整页",
        "上半部分",
        "下半部分",
    ]
    assert records[1]["region"][1] < records[2]["region"][1]


def test_existing_success_is_not_called_again(tmp_path: Path) -> None:
    pdf = tmp_path / "sample.pdf"
    _make_pdf(pdf)
    output = tmp_path / "out"
    first = SequenceProvider([_payload()])
    evaluate_pages(
        pdf,
        [1],
        output,
        _settings(),
        task_type="personnel_table",
        visual_provider=first,
        repair_provider=MockProvider(),
    )
    second = SequenceProvider([RuntimeError("must not be called")])

    summary = evaluate_pages(
        pdf,
        [1],
        output,
        _settings(),
        task_type="personnel_table",
        visual_provider=second,
        repair_provider=MockProvider(),
    )

    assert summary.successful_pages == [1]
    assert second.calls == []
