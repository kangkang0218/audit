from pathlib import Path

from app.services.candidate_planner import scan_page_features
from tests.planner_test_support import make_planner_pdf


def test_every_page_is_scanned_and_sensitive_excerpt_is_masked(
    tmp_path: Path,
) -> None:
    pdf = tmp_path / "sample.pdf"
    make_planner_pdf(
        pdf,
        [
            ("投标函 手机号13812345678", False),
            ("", True),
            ("普通正文", False),
        ],
    )

    manifest, features = scan_page_features(pdf)

    assert manifest["input_page_count"] == 3
    assert [item.pdf_page for item in features] == [1, 2, 3]
    assert features[1].scan_like_page is True
    assert "13812345678" not in (features[0].excerpt_masked or "")
    assert features[0].excerpt_masked and "138****5678" in features[0].excerpt_masked
    assert manifest["external_model_calls"] == 0


def test_table_and_duplicate_hints_are_local_features(
    tmp_path: Path,
) -> None:
    pdf = tmp_path / "sample.pdf"
    table = "项目组成员\n职务\n姓名\n证号\n专业\n备注\n" * 4
    make_planner_pdf(pdf, [(table, False), (table, False)])

    _, features = scan_page_features(pdf)

    assert features[0].table_likelihood >= 0.5
    assert features[1].duplicate_or_near_duplicate_hint == 1
