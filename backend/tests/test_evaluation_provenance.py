from pathlib import Path

from app.schemas.evaluation_merge import ImportedEvaluationResult
from app.schemas.phase_a import ExtractedFactItem
from app.services.evaluation_merge import merge_evaluation_results
from tests.evaluation_test_support import generic_payload


def test_provenance_keeps_pages_paths_and_source_types(
    tmp_path: Path,
) -> None:
    result_path = tmp_path / "page_005_bid_letter.json"
    result_path.write_text("{}", encoding="utf-8")
    imported = ImportedEvaluationResult(
        evaluation_dir=tmp_path,
        result_path=result_path,
        pdf_page=5,
        task_type="bid_letter",
        payload=generic_payload("bid_letter", "项目名称", "同一项目"),
        match_method="sha256",
        manual_review_required=False,
        modified_time=1,
    )
    local = ExtractedFactItem(
        category="基础信息",
        field_name="项目名称",
        value="同一项目",
        status="已提取",
    )

    merged = merge_evaluation_results(
        [local],
        [],
        [imported],
        source_file="sample.pdf",
    )
    provenance = next(
        item for item in merged.provenance if item.field_name == "项目名称"
    )

    assert provenance.merge_status == "corroborated"
    assert provenance.source_types == [
        "pdf_text",
        "qwen_page_evaluation",
    ]
    assert provenance.source_pdf_pages == [5]
    assert provenance.source_result_paths == [str(result_path)]
    assert provenance.conflict_detected is False
