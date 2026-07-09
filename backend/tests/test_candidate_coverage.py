from pathlib import Path

from app.services.candidate_planner import plan_single_file_review
from tests.planner_test_support import make_planner_pdf


def test_coverage_uses_only_allowed_statuses_and_limitations(
    tmp_path: Path,
) -> None:
    pdf = tmp_path / "sample.pdf"
    make_planner_pdf(pdf, [("投标函 投标报价 项目负责人", False)])

    result = plan_single_file_review(pdf, tmp_path / "out")
    statuses = {
        value["status"]
        for value in result["coverage"]["coverage"].values()
    }

    assert statuses <= {
        "found",
        "possible",
        "not_found",
        "uncertain",
        "out_of_scope",
    }
    assert (
        "不代表材料一定未提交"
        in result["coverage"]["limitations"]
    )
