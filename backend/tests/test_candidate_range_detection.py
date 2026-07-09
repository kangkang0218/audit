from pathlib import Path

from app.services.candidate_planner import plan_single_file_review
from tests.planner_test_support import make_planner_pdf


def test_scan_page_bridges_continuous_attachment_range(
    tmp_path: Path,
) -> None:
    pdf = tmp_path / "sample.pdf"
    make_planner_pdf(
        pdf,
        [
            ("项目组成员 职务 姓名 证号 专业", False),
            ("", True),
            ("主要人员表 职务 姓名 证号 专业", False),
            ("普通说明", False),
        ],
    )

    result = plan_single_file_review(pdf, tmp_path / "out")
    ranges = [
        item
        for item in result["ranges"]
        if item.material_type == "personnel_table"
    ]

    assert any(item.included_pages == [1, 2, 3] for item in ranges)
    assert any(item.boundary_uncertain for item in ranges)


def test_user_overrides_and_vision_limit_do_not_drop_pages(
    tmp_path: Path,
) -> None:
    pdf = tmp_path / "sample.pdf"
    make_planner_pdf(
        pdf,
        [
            ("投标保证金 保证金缴款凭证", True),
            ("养老保险缴纳证明 缴费单位", True),
            ("普通正文", False),
        ],
    )

    result = plan_single_file_review(
        pdf,
        tmp_path / "out",
        include_pages={3},
        exclude_pages={2},
        max_vision_candidates=0,
    )
    pages = {item.pdf_page: item for item in result["pages"]}

    assert "user_forced_include" in pages[3].reason_codes
    assert "user_forced_exclude" in pages[2].reason_codes
    assert pages[1].processing_recommendation == "vision_candidate_deferred"
    assert len(pages) == 3
