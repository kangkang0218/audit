from pathlib import Path

import fitz


def make_planner_pdf(
    path: Path,
    pages: list[tuple[str, bool]],
) -> None:
    document = fitz.open()
    try:
        for text, with_image in pages:
            page = document.new_page()
            if text:
                page.insert_textbox(
                    fitz.Rect(40, 40, 550, 800),
                    text,
                    fontname="china-s",
                    fontsize=12,
                )
            if with_image:
                pixmap = fitz.Pixmap(
                    fitz.csRGB,
                    fitz.IRect(0, 0, 200, 300),
                    False,
                )
                pixmap.clear_with(220)
                page.insert_image(
                    fitz.Rect(80, 160, 500, 760),
                    pixmap=pixmap,
                )
        document.save(path)
    finally:
        document.close()
