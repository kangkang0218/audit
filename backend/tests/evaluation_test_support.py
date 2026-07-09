from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import fitz


def make_pdf(path: Path, texts: list[str]) -> None:
    document = fitz.open()
    try:
        for text in texts:
            page = document.new_page()
            page.insert_textbox(
                fitz.Rect(40, 40, 550, 800),
                text,
                fontname="china-s",
                fontsize=12,
            )
        document.save(path)
    finally:
        document.close()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generic_payload(
    task_type: str,
    field_name: str,
    value: Any,
) -> dict[str, Any]:
    return {
        "task_type": task_type,
        "material_found": True,
        "fields": [
            {
                "field_name": field_name,
                "value": value,
                "status": "已提取",
                "evidence": "当前页字段",
                "conflict_evidence": [],
                "note": "",
            }
        ],
        "notes": [],
    }


def make_evaluation(
    directory: Path,
    pdf: Path,
    *,
    page: int = 1,
    task_type: str = "bid_letter",
    payload: dict[str, Any] | None = None,
    success: bool = True,
    schema_valid: bool = True,
    match: str = "sha256",
) -> Path:
    directory.mkdir(parents=True)
    (directory / "results").mkdir()
    manifest: dict[str, Any] = {
        "manifest_version": 2,
        "input_file_name": pdf.name,
        "requested_pages": [page],
        "pages": [],
    }
    with fitz.open(pdf) as document:
        manifest["input_page_count"] = len(document)
    if match == "sha256":
        manifest["input_sha256"] = sha256(pdf)
    elif match == "filename_only":
        manifest.pop("input_page_count")
    (directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False),
        encoding="utf-8",
    )
    summary = {
        "input_file": pdf.name,
        "provider": "mock",
        "vision_model": "mock",
        "requested_pages": [page],
        "successful_pages": [page] if success else [],
        "failed_pages": [] if success else [page],
        "results": [
            {
                "pdf_page": page,
                "task_type": task_type,
                "success": success,
                "schema_valid": schema_valid,
                "elapsed_seconds": 0,
                "fields_extracted": [],
                "manual_review_fields": [],
                "notes": [],
            }
        ],
    }
    (directory / "evaluation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False),
        encoding="utf-8",
    )
    result_path = (
        directory / "results" / f"page_{page:03d}_{task_type}.json"
    )
    result_path.write_text(
        json.dumps(
            payload or generic_payload(task_type, "项目名称", "测试项目"),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return result_path
