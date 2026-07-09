from pathlib import Path

import fitz


def render_page(pdf_path: Path, pdf_page: int, output_path: Path, dpi: int = 150) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(pdf_path) as document:
        page = document[pdf_page - 1]
        pixmap = page.get_pixmap(dpi=dpi, alpha=False)
        pixmap.save(output_path)
    return output_path

