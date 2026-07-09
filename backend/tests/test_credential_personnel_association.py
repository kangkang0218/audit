from pathlib import Path

import fitz

from app.extractors.personnel import extract_personnel
from app.parsers.pdf_parser import parse_pdf


def test_unlabeled_credential_page_does_not_create_person(tmp_path: Path) -> None:
    path = tmp_path / "credential.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Certificate Level One Engineer")
    document.save(path)
    document.close()

    people = extract_personnel(parse_pdf(path), [])

    assert people == []

