from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import fitz

from app.core.privacy import mask_sensitive_text
from app.schemas.phase_a import PageItem

PRINTED_PAGE_PATTERNS = (
    re.compile(r"^\s*[-—]\s*(\d{1,4})\s*[-—]\s*$"),
    re.compile(r"^\s*第?\s*(\d{1,4})\s*页?\s*$"),
)

HEADING_KEYWORDS = [
    "投标函附录",
    "投标函",
    "法定代表人身份证明",
    "授权委托书",
    "投标保证金",
    "投标人基本情况表",
    "拟派项目负责人及项目组成员",
    "项目管理机构组成表",
    "主要人员简历表",
    "劳动合同",
    "养老保险缴纳证明",
    "无行贿犯罪行为承诺书",
    "企业信誉承诺书",
    "反商业贿赂承诺书",
    "企业投标诚信承诺书",
    "信用中国",
    "非联合体",
    "控股、管理关系",
    "不再接受已入围",
    "营业执照",
    "资质",
]


@dataclass
class ParsedPage:
    pdf_page: int
    printed_page: str | None
    raw_text: str
    lines: list[str]
    image_count: int
    detected_headings: list[str]
    ocr_text: str = ""

    @property
    def combined_text(self) -> str:
        return f"{self.raw_text}\n{self.ocr_text}".strip()

    def add_ocr_text(self, text: str) -> None:
        if not text:
            return
        self.ocr_text = text
        self.raw_text = f"{self.raw_text}\n{text}"
        self.lines.extend(text.splitlines())

    def public(self, low_text_threshold: int = 30) -> PageItem:
        text_length = len(self.combined_text)
        low = text_length < low_text_threshold
        return PageItem(
            pdf_page=self.pdf_page,
            printed_page=self.printed_page,
            text=mask_sensitive_text(self.combined_text),
            text_length=text_length,
            is_low_text_page=low,
            is_candidate_for_ocr=low and self.image_count > 0,
            detected_headings=self.detected_headings,
            image_count=self.image_count,
            text_quality="empty" if text_length == 0 else ("low" if low else "normal"),
        )


@dataclass
class ParsedDocument:
    source_path: Path
    sha256: str
    pages: list[ParsedPage]


def _printed_page(lines: list[str]) -> str | None:
    candidates = lines[:4] + lines[-4:]
    for line in candidates:
        for pattern in PRINTED_PAGE_PATTERNS:
            match = pattern.match(line)
            if match:
                return match.group(1)
    return None


def parse_pdf(path: Path) -> ParsedDocument:
    if not path.is_file():
        raise FileNotFoundError(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)

    fitz.TOOLS.mupdf_display_errors(False)
    pages: list[ParsedPage] = []
    with fitz.open(path) as document:
        if document.needs_pass:
            raise ValueError("PDF 已加密，当前未提供密码")
        for index, page in enumerate(document):
            raw_text = page.get_text("text").replace("\x00", "")
            lines = [line.strip() for line in raw_text.splitlines()]
            compact = re.sub(r"\s+", "", raw_text)
            headings = [keyword for keyword in HEADING_KEYWORDS if keyword in compact]
            pages.append(
                ParsedPage(
                    pdf_page=index + 1,
                    printed_page=_printed_page(lines),
                    raw_text=raw_text,
                    lines=lines,
                    image_count=len(page.get_images(full=True)),
                    detected_headings=headings,
                )
            )
    return ParsedDocument(source_path=path, sha256=digest.hexdigest(), pages=pages)
