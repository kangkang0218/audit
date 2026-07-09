from __future__ import annotations

from pathlib import Path

from app.schemas.evaluation_merge import ImportedEvaluationResult
from app.schemas.phase_a import ExtractedFactItem, PersonnelItem
from app.services.evaluation_merge import merge_evaluation_results
from tests.evaluation_test_support import generic_payload


def _imported(
    tmp_path: Path,
    task_type: str,
    payload: dict,
    page: int = 1,
) -> ImportedEvaluationResult:
    path = tmp_path / f"page_{page:03d}_{task_type}.json"
    path.write_text("{}", encoding="utf-8")
    return ImportedEvaluationResult(
        evaluation_dir=tmp_path,
        result_path=path,
        pdf_page=page,
        task_type=task_type,
        payload=payload,
        match_method="sha256",
        manual_review_required=False,
        modified_time=1,
    )


def test_fact_corroborated_conflict_and_qwen_only(tmp_path: Path) -> None:
    facts = [
        ExtractedFactItem(
            category="基础信息",
            field_name="项目名称",
            value="一致项目",
            status="已提取",
        ),
        ExtractedFactItem(
            category="人员",
            field_name="项目负责人",
            value="本地姓名",
            status="已提取",
        ),
    ]
    imported = [
        _imported(
            tmp_path,
            "bid_letter",
            {
                "task_type": "bid_letter",
                "material_found": True,
                "fields": [
                    {
                        "field_name": "项目名称",
                        "value": "一致项目",
                        "status": "已提取",
                    },
                    {
                        "field_name": "项目负责人",
                        "value": "另一姓名",
                        "status": "已提取",
                    },
                    {
                        "field_name": "日期",
                        "value": "2024年1月1日",
                        "status": "已提取",
                    },
                ],
                "notes": [],
            },
        )
    ]

    merged = merge_evaluation_results(
        facts,
        [],
        imported,
        source_file="sample.pdf",
    )
    by_name = {item.field_name: item for item in merged.provenance}

    assert by_name["项目名称"].merge_status == "corroborated"
    assert by_name["项目负责人"].merge_status == "conflict"
    assert by_name["投标文件日期"].merge_status == "qwen_only"
    assert merged.conflict_count == 1


def test_same_name_and_role_rows_are_not_collapsed(tmp_path: Path) -> None:
    local = [
        PersonnelItem(name="同名人员", role="项目成员"),
        PersonnelItem(name="同名人员", role="项目成员"),
    ]
    payload = {
        "rows": [
            {
                "name": "同名人员",
                "role": "项目成员",
                "title": "高级",
                "certificate_level": "一级",
                "certificate_numbers": [],
                "specialty": "土木建筑",
                "manual_review_required": True,
                "note": "关系不明确",
            },
            {
                "name": "同名人员",
                "role": "项目成员",
                "title": "中级",
                "certificate_level": "一级",
                "certificate_numbers": [],
                "specialty": "安装",
                "manual_review_required": True,
                "note": "关系不明确",
            },
        ],
        "page_has_personnel_table": True,
        "manual_review_notes": [],
    }

    merged = merge_evaluation_results(
        [],
        local,
        [_imported(tmp_path, "personnel_table", payload, page=25)],
        source_file="sample.pdf",
    )

    assert len(merged.personnel) == 4
    assert [
        item["original_table_order"]
        for item in merged.personnel_json[-2:]
    ] == [1, 2]


def test_sensitive_number_is_not_accepted_as_certificate(
    tmp_path: Path,
) -> None:
    payload = {
        "rows": [
            {
                "name": "测试人员",
                "role": "项目成员",
                "title": None,
                "certificate_level": None,
                "certificate_numbers": ["410327198011015611"],
                "specialty": None,
                "manual_review_required": True,
                "note": None,
            }
        ],
        "page_has_personnel_table": True,
        "manual_review_notes": [],
    }

    merged = merge_evaluation_results(
        [],
        [],
        [_imported(tmp_path, "personnel_table", payload, page=25)],
        source_file="sample.pdf",
    )

    assert merged.personnel[0].certificate_numbers == []
