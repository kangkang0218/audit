from pathlib import Path

from app.services.candidate_planner import plan_single_file_review
from tests.planner_test_support import make_planner_pdf


def test_typical_material_keywords_and_unknown_are_preserved(
    tmp_path: Path,
) -> None:
    pdf = tmp_path / "sample.pdf"
    make_planner_pdf(
        pdf,
        [
            ("（一）投标函 投标报价 项目负责人", False),
            ("（二）投标函附录 基本费率 审减费率 税率", False),
            ("授权委托书 委托代理人 委托期限", False),
            ("投标保证金 保证金缴款凭证", True),
            ("项目组成员 职务 姓名 证号 专业", False),
            ("养老保险缴纳证明 缴费单位 缴费月份", True),
            ("", True),
        ],
    )

    result = plan_single_file_review(pdf, tmp_path / "out")
    pages = {item.pdf_page: item for item in result["pages"]}

    assert pages[1].primary_material_type == "bid_letter"
    assert pages[2].primary_material_type == "bid_appendix"
    assert pages[3].primary_material_type == "authorization"
    assert "guarantee" in pages[4].material_types
    assert "personnel_table" in pages[5].material_types
    assert "social_security" in pages[6].material_types
    assert pages[7].primary_material_type == "unknown_review"
    assert pages[7].processing_recommendation == "manual_review"


def test_current_sample_regression_discovers_targets_and_more(
    tmp_path: Path,
    real_pdf_path: Path,
) -> None:
    result = plan_single_file_review(real_pdf_path, tmp_path / "plan")
    pages = {item.pdf_page: item for item in result["pages"]}

    expected = {
        5: "bid_letter",
        6: "bid_appendix",
        8: "authorization",
        19: "guarantee",
        25: "personnel_table",
        36: "social_security",
    }
    for page, material_type in expected.items():
        assert material_type in pages[page].material_types
    assert result["processing_summary"]["relevant_candidate_pages"] > 6


def test_toc_keywords_are_navigation_not_content_candidates(
    tmp_path: Path,
) -> None:
    pdf = tmp_path / "toc.pdf"
    make_planner_pdf(
        pdf,
        [
            (
                "目录\n投标函........1\n授权委托书........3\n"
                "投标保证金........8\n项目组成员........12\n"
                "劳动合同........20\n养老保险缴纳证明........30",
                False,
            ),
            ("（一）投标函 投标报价", False),
        ],
    )

    result = plan_single_file_review(pdf, tmp_path / "out")

    assert result["features"][0].is_toc_page is True
    assert result["pages"][0].processing_recommendation == "out_of_scope"
    assert result["pages"][0].material_types == []
