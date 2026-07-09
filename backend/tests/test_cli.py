from pathlib import Path

import fitz

from app.cli.main import inspect_pdf, validate_template
from app.excel.renderer import render_review_workbook
from app.schemas.review import ReviewWorkbook


def test_inspect_pdf_without_leaking_text(tmp_path: Path) -> None:
    path = tmp_path / "sample.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "sensitive source text")
    document.save(path)
    document.close()

    result = inspect_pdf(path)

    assert result["page_count"] == 1
    assert result["text_coverage"] == 1.0
    assert "sensitive source text" not in str(result)


def test_generated_workbook_matches_contract(tmp_path: Path) -> None:
    path = render_review_workbook(
        ReviewWorkbook(source_file="sample.pdf"),
        tmp_path / "sample.xlsx",
    )

    result = validate_template(path)

    assert result["compatible"] is True
    assert result["compatibility"] == "exact"

