from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import urllib.request
import urllib.error

from app.parsers.pdf_parser import ParsedDocument

MINERU_API_URL = "http://mineru-api:8000"
REQUEST_TIMEOUT_SECONDS = 600


class MineruTableBlock:
    __slots__ = ("page", "rows")
    def __init__(self, page: int, rows: list[list[str]]) -> None:
        self.page = page
        self.rows = rows


class MineruClient:
    def __init__(self, api_url: str | None = None) -> None:
        self.api_url = api_url or MINERU_API_URL

    def health(self) -> bool:
        try:
            req = urllib.request.Request(
                f"{self.api_url}/health",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception:
            return False

    def parse(
        self, input_path: Path, filename: str | None = None
    ) -> tuple[dict[int, str], list[MineruTableBlock]]:
        boundary = "mineruparseboundary"
        body = _build_multipart_body(input_path, filename, boundary)

        req = urllib.request.Request(
            f"{self.api_url}/file_parse",
            data=body,
            method="POST",
        )
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"MinerU API returned {resp.status}")
                result: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"MinerU API 不可达: {exc}") from exc

        page_texts = _extract_page_texts(result)
        table_blocks = _extract_table_blocks(result)
        return page_texts, table_blocks


def _build_multipart_body(
    input_path: Path,
    filename: str | None,
    boundary: str,
) -> bytes:
    name = filename or input_path.name
    with input_path.open("rb") as f:
        file_content = f.read()

    lines = [
        f"--{boundary}".encode("utf-8"),
        f'Content-Disposition: form-data; name="files"; filename="{name}"'.encode("utf-8"),
        b"Content-Type: application/pdf",
        b"",
        file_content,
        f"--{boundary}--".encode("utf-8"),
    ]
    return b"\r\n".join(lines)


def _extract_page_texts(parsed: dict[str, Any]) -> dict[int, str]:
    page_texts: dict[int, str] = {}
    pages: list[dict[str, Any]] = parsed.get("pages") or []
    for idx, page in enumerate(pages):
        page_num = idx + 1
        blocks: list[dict[str, Any]] = page.get("blocks") or []
        lines: list[str] = []
        for block in blocks:
            if block.get("type") == "table":
                continue
            block_lines = block.get("lines") or []
            for line in block_lines:
                spans = line.get("spans") or []
                line_text = "".join(sp.get("content", "") for sp in spans)
                if line_text.strip():
                    lines.append(line_text.strip())
        if lines:
            page_texts[page_num] = "\n".join(lines)
    return page_texts


def _extract_table_blocks(parsed: dict[str, Any]) -> list[MineruTableBlock]:
    tables: list[MineruTableBlock] = []
    pages: list[dict[str, Any]] = parsed.get("pages") or []
    for idx, page in enumerate(pages):
        page_num = idx + 1
        blocks: list[dict[str, Any]] = page.get("blocks") or []
        for block in blocks:
            if block.get("type") != "table":
                continue
            cells = block.get("cells") or []
            if not cells:
                continue
            max_row = max(int(c.get("row", 0)) for c in cells)
            rows: list[list[str]] = [[] for _ in range(max_row + 1)]
            for cell in cells:
                row_idx = int(cell.get("row", 0))
                col_idx = int(cell.get("col", 0))
                content = cell.get("content", "")
                while len(rows[row_idx]) <= col_idx:
                    rows[row_idx].append("")
                rows[row_idx][col_idx] = content
            headers = block.get("headers") or []
            if headers:
                if len(rows) > 0:
                    rows[0] = headers
                else:
                    rows.append(headers)
            tables.append(MineruTableBlock(page=page_num, rows=rows))
    return tables
