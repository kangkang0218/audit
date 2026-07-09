from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

MAX_SECTION_CHARS = 3000


@dataclass
class Section:
    heading: str
    content: str
    start_page: int | None
    end_page: int | None

    @property
    def label(self) -> str:
        return self.heading[:40]


_PAGE_REF = re.compile(r"<!--\s*page[_\s]*(\d+)\s*-->", re.IGNORECASE)

_MD_HEADING = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)

_CN_SECTION = re.compile(
    r"^[（(]*"
    r"(第[一二三四五六七八九十百千0-9]+[章节条]|"
    r"[一二三四五六七八九十]+[、，,\s]|"
    r"投标函|投标函附录|法定代表人|授权委托|投标保证金|"
    r"项目管理机构|主要人员|劳动合同|养老保险|社保|"
    r"企业信誉|信用|营业执照|资质|"
    r"一[、，]|二[、，]|三[、，]|四[、，]|五[、，]|"
    r"六[、，]|七[、，]|八[、，]|九[、，]|十[、，])"
    r"\s*",
    re.MULTILINE,
)


def split_markdown(markdown: str) -> list[Section]:
    if not markdown.strip():
        return [Section(heading="全文", content=markdown, start_page=None, end_page=None)]

    headings = _find_headings(markdown)
    if not headings:
        headings = _cn_headings(markdown)
    if not headings:
        headings = _page_boundaries(markdown)

    sections: list[Section] = []
    for i, (heading, pos) in enumerate(headings):
        start = pos
        end = headings[i + 1][1] if i + 1 < len(headings) else len(markdown)
        content = markdown[start:end].strip()
        if not content.strip():
            continue
        sp, ep = _page_range(content)
        sub = _split_large(Section(heading=heading, content=content, start_page=sp, end_page=ep))
        sections.extend(sub)

    if not sections:
        sections = _split_large(Section(heading="全文", content=markdown, start_page=None, end_page=None))
    return sections


def _find_headings(text: str) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for m in _MD_HEADING.finditer(text):
        out.append((m.group(2).strip(), m.start()))
    return out


def _cn_headings(text: str) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for m in _CN_SECTION.finditer(text):
        out.append((m.group(0).strip(), m.start()))
    return out


def _page_boundaries(text: str) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    last_page = 0
    for m in _PAGE_REF.finditer(text):
        page = int(m.group(1))
        if last_page == 0 or page >= last_page + 3:
            out.append((f"第{page}页起", m.start()))
            last_page = page
    return out


def _split_large(section: Section) -> list[Section]:
    if len(section.content) <= MAX_SECTION_CHARS:
        return [section]
    parts: list[Section] = []
    i = 0
    text = section.content
    while i < len(text):
        end = min(i + MAX_SECTION_CHARS, len(text))
        chunk = text[i:end].strip()
        if chunk:
            parts.append(Section(
                heading=f"{section.heading}({len(parts)+1})",
                content=chunk,
                start_page=section.start_page,
                end_page=section.end_page,
            ))
        i = end
    return parts


def _page_range(text: str) -> tuple[int | None, int | None]:
    pages = [int(m.group(1)) for m in _PAGE_REF.finditer(text)]
    if not pages:
        return None, None
    return min(pages), max(pages)


class MarkdownLoader:
    @staticmethod
    def from_file(path: Path) -> str:
        return path.read_text(encoding="utf-8")
