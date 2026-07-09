from __future__ import annotations

import json
from pathlib import Path

from app.importers.page_evaluation_importer import import_page_evaluations
from app.parsers.pdf_parser import parse_pdf
from tests.evaluation_test_support import (
    generic_payload,
    make_evaluation,
    make_pdf,
)


def test_valid_sha_result_imports_and_failed_result_skips(
    tmp_path: Path,
) -> None:
    pdf = tmp_path / "sample.pdf"
    make_pdf(pdf, ["投标函"])
    valid = tmp_path / "valid"
    failed = tmp_path / "failed"
    make_evaluation(valid, pdf)
    make_evaluation(failed, pdf, success=False, schema_valid=False)

    bundle = import_page_evaluations(
        parse_pdf(pdf),
        [valid, failed],
    )

    assert len(bundle.results) == 1
    assert bundle.results[0].match_method == "sha256"
    assert any(
        record.get("skip_reason") == "结果失败或 Schema 不合格"
        for record in bundle.audit_records
    )


def test_legacy_page_count_marks_manual_review(tmp_path: Path) -> None:
    pdf = tmp_path / "sample.pdf"
    make_pdf(pdf, ["投标函"])
    evaluation = tmp_path / "legacy"
    make_evaluation(evaluation, pdf, match="page_count")

    bundle = import_page_evaluations(parse_pdf(pdf), [evaluation])

    assert len(bundle.results) == 1
    assert bundle.results[0].match_method == "legacy_filename_and_page_count"
    assert bundle.results[0].manual_review_required is True


def test_filename_only_requires_explicit_compatibility(tmp_path: Path) -> None:
    pdf = tmp_path / "sample.pdf"
    make_pdf(pdf, ["投标函"])
    evaluation = tmp_path / "legacy"
    make_evaluation(evaluation, pdf, match="filename_only")

    blocked = import_page_evaluations(parse_pdf(pdf), [evaluation])
    allowed = import_page_evaluations(
        parse_pdf(pdf),
        [evaluation],
        allow_legacy_filename_only_match=True,
    )

    assert blocked.results == []
    assert len(allowed.results) == 1
    assert allowed.results[0].match_method == "legacy_filename_only"


def test_historical_selected_page_text_is_accepted_with_warning(
    tmp_path: Path,
) -> None:
    pdf = tmp_path / "sample.pdf"
    make_pdf(pdf, ["投标函"])
    evaluation = tmp_path / "legacy"
    make_evaluation(evaluation, pdf, match="filename_only")
    manifest_path = evaluation / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    document = parse_pdf(pdf)
    manifest["pages"] = [
        {
            "pdf_page": 1,
            "redacted_text": document.pages[0].public().text + "\n",
        }
    ]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    bundle = import_page_evaluations(parse_pdf(pdf), [evaluation])

    assert len(bundle.results) == 1
    assert (
        bundle.results[0].match_method
        == "legacy_filename_and_selected_page_text"
    )
    assert bundle.results[0].manual_review_required is True


def test_file_mismatch_and_duplicate_conflict_are_audited(
    tmp_path: Path,
) -> None:
    pdf = tmp_path / "sample.pdf"
    other = tmp_path / "other.pdf"
    make_pdf(pdf, ["投标函"])
    make_pdf(other, ["其他内容"])
    mismatch = tmp_path / "mismatch"
    make_evaluation(mismatch, other)
    first = tmp_path / "first"
    second = tmp_path / "second"
    make_evaluation(
        first,
        pdf,
        payload=generic_payload("bid_letter", "项目名称", "值一"),
    )
    make_evaluation(
        second,
        pdf,
        payload=generic_payload("bid_letter", "项目名称", "值二"),
    )

    bundle = import_page_evaluations(
        parse_pdf(pdf),
        [mismatch, first, second],
    )

    assert len(bundle.results) == 2
    assert any(
        record.get("status") == "conflict"
        for record in bundle.audit_records
    )
    assert any(
        record.get("skip_reason") == "输入文件名不匹配"
        for record in bundle.audit_records
    )


def test_task_type_mismatch_is_rejected(tmp_path: Path) -> None:
    pdf = tmp_path / "sample.pdf"
    make_pdf(pdf, ["投标函"])
    evaluation = tmp_path / "evaluation"
    result_path = make_evaluation(evaluation, pdf)
    payload = json.loads(result_path.read_text())
    payload["task_type"] = "authorization"
    result_path.write_text(json.dumps(payload), encoding="utf-8")

    bundle = import_page_evaluations(parse_pdf(pdf), [evaluation])

    assert bundle.results == []
