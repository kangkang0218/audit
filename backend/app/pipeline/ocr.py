from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def get_page_count(pdf_path: Path) -> int:
    import fitz
    with fitz.open(pdf_path) as doc:
        return len(doc)


@dataclass
class OcrResult:
    markdown: str
    page_map: dict[int, int]
    page_texts: dict[int, str] = field(default_factory=dict)
    images: list[dict[str, Any]] = field(default_factory=list)

    @property
    def page_count(self) -> int:
        return len(self.page_map)


def run_ocr(input_path: Path, backend: str = "hybrid-engine") -> OcrResult:
    boundary = "mineruocrboundary"
    body = _build_body(input_path, boundary, backend)
    req = urllib.request.Request(
        "http://mineru-api:8000/file_parse",
        data=body,
        method="POST",
    )
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    try:
        with urllib.request.urlopen(req, timeout=1800) as resp:
            if resp.status != 200:
                raise RuntimeError(f"MinerU returned {resp.status}")
            result: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"MinerU API 不可达: {exc}") from exc
    markdown, page_map, page_texts = _extract(result)
    images = _extract_images(result)
    return OcrResult(markdown=markdown, page_map=page_map, page_texts=page_texts, images=images)


def _build_body(input_path: Path, boundary: str, backend: str = "hybrid-engine") -> bytes:
    with input_path.open("rb") as f:
        file_content = f.read()
    name = input_path.name
    lines = [
        f"--{boundary}".encode(),
        f'Content-Disposition: form-data; name="files"; filename="{name}"'.encode(),
        b"Content-Type: application/pdf",
        b"",
        file_content,
        f"--{boundary}".encode(),
        b'Content-Disposition: form-data; name="backend"',
        b"",
        backend.encode(),
        f"--{boundary}".encode(),
        b'Content-Disposition: form-data; name="return_content_list"',
        b"",
        b"true",
        f"--{boundary}".encode(),
        b'Content-Disposition: form-data; name="return_images"',
        b"",
        b"true",
        f"--{boundary}--".encode(),
    ]
    return b"\r\n".join(lines)


def _extract(result: dict[str, Any]) -> tuple[str, dict[int, int], dict[int, str]]:
    markdown = (
        result.get("md") or result.get("markdown") or ""
    )
    pages: list[dict[str, Any]] = result.get("pages") or []

    # MinerU async task response: data nested under results[filename]
    md_content = ""
    if not markdown and not pages:
        results = result.get("results", {})
        if isinstance(results, dict):
            for fname, fdata in results.items():
                if isinstance(fdata, dict):
                    md_content = fdata.get("md_content") or fdata.get("md") or fdata.get("markdown") or ""

    if md_content:
        markdown = md_content
        pages = result.get("content_list") or []

    page_map: dict[int, int] = {}
    page_texts: dict[int, str] = {}
    for idx, page in enumerate(pages):
        page_num = idx + 1
        page_map[page_num] = idx
        lines: list[str] = []
        blocks: list[dict[str, Any]] = page.get("blocks") or []
        for block in blocks:
            block_type = block.get("type", "unknown")
            if block_type == "table":
                cells = block.get("cells") or []
                row_data: dict[int, list[str]] = {}
                for cell in cells:
                    r = int(cell.get("row", 0))
                    row_data.setdefault(r, []).append(cell.get("content", ""))
                for r in sorted(row_data):
                    lines.append(" | ".join(row_data[r]))
                continue
            block_lines = block.get("lines") or []
            for line in block_lines:
                spans = line.get("spans") or []
                text = "".join(sp.get("content", "") for sp in spans)
                if text.strip():
                    lines.append(text.strip())
        if lines:
            page_texts[page_num] = "\n".join(lines)
    return markdown, page_map, page_texts


def _extract_images(result: dict[str, Any]) -> list[dict[str, Any]]:
    images: list[dict[str, Any]] = []
    results = result.get("results", {})
    if isinstance(results, dict):
        for _, fdata in results.items():
            if isinstance(fdata, dict):
                imgs = fdata.get("images") or []
                for img in imgs:
                    if isinstance(img, dict):
                        images.append({
                            "page": img.get("page", 0),
                            "bbox": img.get("bbox", []),
                            "data": img.get("image") or img.get("data") or b"",
                            "filename": img.get("filename", ""),
                        })
    return images
