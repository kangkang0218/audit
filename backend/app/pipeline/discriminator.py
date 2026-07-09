from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

import fitz


class PdfClass(Enum):
    TEXT = auto()
    MIXED = auto()
    SCANNED = auto()


@dataclass
class DiscriminatorResult:
    pdf_class: PdfClass
    total_pages: int
    text_pages: int
    scanned_pages: int
    avg_chars_per_page: float
    markdown: str = ""


_TEXT_THRESHOLD = 10
_SCANNED_RATIO = 0.1
_TEXT_RATIO = 0.8


def classify_pdf(input_path: Path) -> DiscriminatorResult:
    fitz.TOOLS.mupdf_display_errors(False)
    text_page_count = 0
    total_pages = 0
    total_chars = 0
    page_texts: list[dict] = []
    markdown = ""

    with fitz.open(input_path) as doc:
        if doc.needs_pass:
            raise ValueError("PDF 已加密，当前未提供密码")
        for idx, page in enumerate(doc):
            raw = page.get_text("text")
            chars = len(raw.strip())
            total_chars += chars
            total_pages += 1
            if chars >= _TEXT_THRESHOLD:
                text_page_count += 1
            page_texts.append({"page": idx + 1, "text": raw, "chars": chars})

    scanned_pages = total_pages - text_page_count
    avg_chars = total_chars / max(total_pages, 1)
    text_ratio = text_page_count / max(total_pages, 1)

    if text_ratio >= _TEXT_RATIO:
        pdf_class = PdfClass.TEXT
        markdown = _build_markdown_from_text(page_texts)
    elif text_ratio <= _SCANNED_RATIO:
        pdf_class = PdfClass.SCANNED
    else:
        pdf_class = PdfClass.MIXED

    return DiscriminatorResult(
        pdf_class=pdf_class,
        total_pages=total_pages,
        text_pages=text_page_count,
        scanned_pages=scanned_pages,
        avg_chars_per_page=round(avg_chars, 1),
        markdown=markdown,
    )


def _build_markdown_from_text(page_texts: list[dict]) -> str:
    lines: list[str] = []
    for entry in page_texts:
        text = entry["text"].strip()
        if not text:
            continue
        page_num = entry["page"]
        lines.append(f"\n<!-- page {page_num} -->\n")
        for line in text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if any(keyword in stripped for keyword in [
                "一、", "二、", "三、", "四、", "五、", "六、", "七、", "八、", "九、", "十、",
                "第", "章", "节",
            ]):
                if not stripped.startswith("##"):
                    stripped = f"## {stripped}"
                lines.append(f"\n{stripped}\n")
            else:
                lines.append(stripped)
    return "\n".join(lines)
