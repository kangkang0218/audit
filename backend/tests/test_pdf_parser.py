from app.parsers.pdf_parser import parse_pdf


def test_real_pdf_pages_and_masking(parsed_real) -> None:
    assert len(parsed_real.pages) == 640
    assert parsed_real.pages[4].printed_page == "1"
    public_page = parsed_real.pages[24].public()
    assert public_page.pdf_page == 25
    assert public_page.text_length > 500
    assert "********" in public_page.text


def test_parser_detects_low_text_image_page(parsed_real) -> None:
    page = parsed_real.pages[17].public()
    assert page.is_low_text_page is True
    assert page.is_candidate_for_ocr is True
    assert page.image_count > 0

