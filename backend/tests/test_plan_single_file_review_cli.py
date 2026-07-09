from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import httpx
import pytest

from app.services.candidate_planner import inspect_candidate_plan
from tests.planner_test_support import make_planner_pdf


def test_cli_planning_and_inspection_are_offline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = tmp_path / "sample.pdf"
    output = tmp_path / "out"
    make_planner_pdf(pdf, [("投标函 投标报价", False), ("", True)])

    def forbidden(*args, **kwargs):
        raise AssertionError("候选规划不得调用 Provider、HTTP 或 OCR")

    monkeypatch.setattr(httpx, "post", forbidden)
    monkeypatch.setattr(httpx, "request", forbidden)
    monkeypatch.setattr(
        "app.llm.qwen_provider.QwenVisionProvider.__init__",
        forbidden,
    )
    monkeypatch.setattr(
        "app.llm.qwen_provider.QwenTextProvider.__init__",
        forbidden,
    )
    monkeypatch.setattr(
        "app.parsers.ocr_parser.OptionalPaddleOCR.__init__",
        forbidden,
    )
    cli = importlib.import_module("app.cli.main")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "bid-review",
            "plan-single-file-review",
            "--input",
            str(pdf),
            "--output",
            str(output),
        ],
    )
    cli.main()
    response = json.loads(capsys.readouterr().out)

    assert response["external_model_calls"] == 0
    assert (output / "candidate_plan.md").is_file()
    assert (output / "candidate_plan.csv").is_file()
    audit = json.loads((output / "audit_log.json").read_text())
    assert audit[-1]["details"]["providers_initialized"] == 0

    monkeypatch.setattr(
        "app.services.candidate_planner.scan_page_features",
        forbidden,
    )
    inspected = inspect_candidate_plan(output)
    assert inspected["http_calls"] == 0
