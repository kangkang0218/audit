from types import SimpleNamespace

from pathlib import Path

from app.extractors.personnel import (
    PersonnelTableLayout,
    _merge_table_person,
    _parse_coordinate_table,
    _table_pages,
)
from app.parsers.pdf_parser import ParsedDocument, ParsedPage
from app.schemas.phase_a import PersonnelItem


class FakeTable:
    def __init__(self, data, cells, bbox=(0, 0, 100, 100)):
        self._data = data
        self.rows = [SimpleNamespace(cells=row) for row in cells]
        self.bbox = bbox

    def extract(self):
        return self._data


def _page() -> ParsedPage:
    return ParsedPage(
        pdf_page=25,
        printed_page=None,
        # Deliberately misleading linear order: role then qualification then name.
        raw_text="项目负责人高级造价工程师张三姓名职务职称证号专业",
        lines=[],
        image_count=0,
        detected_headings=[],
    )


def test_coordinate_columns_override_linear_text_order() -> None:
    data = [
        ["职务", "姓名", "职称", "证号", "专业"],
        ["项目负责人", "张三", "高级工程师", "建[造]12345678", "土木建筑"],
    ]
    cells = [
        [(0, 0, 20, 10), (20, 0, 40, 10), (40, 0, 60, 10), (60, 0, 80, 10), (80, 0, 100, 10)],
        [(0, 10, 20, 20), (20, 10, 40, 20), (40, 10, 60, 20), (60, 10, 80, 20), (80, 10, 100, 20)],
    ]
    fake_pdf_page = SimpleNamespace(
        find_tables=lambda: SimpleNamespace(tables=[FakeTable(data, cells)])
    )

    people, audit = _parse_coordinate_table(fake_pdf_page, _page())

    assert [person.name for person in people] == ["张三"]
    assert people[0].role == "项目负责人"
    assert audit[0].source_coordinates == [20.0, 10.0, 40.0, 20.0]


def test_missing_name_header_never_falls_back_to_linear_regex() -> None:
    data = [["职务", "职称"], ["项目负责人", "高级造价工程师"]]
    cells = [[(0, 0, 20, 10), (20, 0, 40, 10)]] * 2
    fake_pdf_page = SimpleNamespace(
        find_tables=lambda: SimpleNamespace(tables=[FakeTable(data, cells)])
    )

    people, audit = _parse_coordinate_table(fake_pdf_page, _page())

    assert people == []
    assert any("table_structure_unreliable" in item.name_validation_reason_codes for item in audit)


def test_pages_237_397_431_never_create_title_prefix_people(
    zhongji_personnel_extraction,
) -> None:
    invalid = {"高级", "中级", "初级", "助理", "一级", "二级", "三级"}
    people = zhongji_personnel_extraction.personnel
    target_pages = {237, 397, 431}

    assert not invalid.intersection(person.name for person in people)
    assert {
        evidence.pdf_page
        for person in people
        for evidence in person.evidence
        if evidence.pdf_page in target_pages
    } == target_pages
    assert all(
        item.creation_decision == "reject"
        for item in zhongji_personnel_extraction.rejected
        if item.source_pdf_page in target_pages
    )


def test_resume_detail_rows_are_not_treated_as_personnel_table() -> None:
    resume = ParsedPage(
        pdf_page=2,
        printed_page=None,
        raw_text=(
            "主要人员简历表 姓名 张三 职务 项目成员 职称 高级工程师 "
            "时间 毕业学校 工作经历"
        ),
        lines=[],
        image_count=0,
        detected_headings=[],
    )
    document = ParsedDocument(
        source_path=Path("unused.pdf"),
        sha256="0" * 64,
        pages=[resume],
    )

    assert _table_pages(document) == []


def test_duplicate_table_row_with_truncated_certificate_is_strongly_merged() -> None:
    people = [
        PersonnelItem(
            name="张三",
            role="其他成员",
            title="中级工程师",
            certificate_name="注册造价工程师",
            certificate_level="一级",
            certificate_numbers=["建[造]11224100009291"],
            specialty="土建",
        )
    ]
    _merge_table_person(
        people,
        PersonnelItem(
            name="张三",
            role="其他成员",
            title="中级工程师",
            certificate_name="注册造价工程师",
            certificate_level="一级",
            certificate_numbers=["建[造]11224100"],
            specialty="土建",
        ),
    )

    assert len(people) == 1
    assert people[0].certificate_numbers == ["建[造]11224100009291"]


def test_same_name_with_conflicting_certificate_is_not_merged() -> None:
    people = [
        PersonnelItem(
            name="张三",
            role="其他成员",
            certificate_numbers=["建[造]11224100009291"],
        )
    ]
    _merge_table_person(
        people,
        PersonnelItem(
            name="张三",
            role="其他成员",
            certificate_numbers=["建[造]99224100001234"],
        ),
    )

    assert len(people) == 2


def test_exact_certificate_merges_identity_but_preserves_title_conflict() -> None:
    people = [
        PersonnelItem(
            name="张三",
            role="安装负责人",
            title="工程师",
            certificate_numbers=["建[造]11234100012300"],
        )
    ]
    _merge_table_person(
        people,
        PersonnelItem(
            name="张三",
            role="安装负责人",
            title="中级工程师",
            certificate_numbers=["建[造]11234100012300"],
        ),
    )

    assert len(people) == 1
    assert people[0].title == "工程师"
    assert "职称" in people[0].note
    assert "人工复核" in people[0].note


def test_headerless_next_page_inherits_matching_table_layout() -> None:
    data = [
        ["张三", "其他成员", "中级工程师", "注册造价工程师", "一级", "建[造]12345678", "土建", "", ""],
    ]
    cells = [[
        (0, 10, 10, 20),
        (10, 10, 20, 20),
        (20, 10, 30, 20),
        (30, 10, 40, 20),
        (40, 10, 50, 20),
        (50, 10, 60, 20),
        (60, 10, 70, 20),
        (70, 10, 80, 20),
        (80, 10, 90, 20),
    ]]
    fake_pdf_page = SimpleNamespace(
        find_tables=lambda: SimpleNamespace(
            tables=[FakeTable(data, cells, bbox=(0, 0, 90, 30))]
        )
    )
    layout = PersonnelTableLayout(
        columns={
            "name": 0,
            "role": 1,
            "title": 2,
            "certificate_name": 3,
            "certificate_level": 4,
            "certificate_numbers": 5,
            "specialty": 6,
            "social_security": 7,
        },
        column_count=9,
        x_start=0,
        x_end=90,
    )

    people, _ = _parse_coordinate_table(fake_pdf_page, _page(), layout)

    assert [(person.name, person.role) for person in people] == [
        ("张三", "其他成员")
    ]


def test_headerless_page_with_different_geometry_is_not_inherited() -> None:
    data = [["张三", "其他成员", "中级工程师"]]
    cells = [[(0, 10, 10, 20), (10, 10, 20, 20), (20, 10, 30, 20)]]
    fake_pdf_page = SimpleNamespace(
        find_tables=lambda: SimpleNamespace(
            tables=[FakeTable(data, cells, bbox=(20, 0, 70, 30))]
        )
    )
    layout = PersonnelTableLayout(
        columns={"name": 0, "role": 1},
        column_count=9,
        x_start=0,
        x_end=90,
    )

    people, audit = _parse_coordinate_table(fake_pdf_page, _page(), layout)

    assert people == []
    assert any(
        "table_structure_unreliable" in item.name_validation_reason_codes
        for item in audit
    )


def test_same_masked_identity_ending_x_is_strong_merge_evidence() -> None:
    people = [
        PersonnelItem(
            name="张三",
            role="其他成员",
            certificate_numbers=["建[造]11234100012300"],
            social_security_id_masked="4101**********001X",
        )
    ]
    _merge_table_person(
        people,
        PersonnelItem(
            name="张三",
            role="其他成员",
            social_security_id_masked="4101**********001X",
        ),
    )

    assert len(people) == 1


def test_semantically_swapped_name_and_role_columns_are_corrected() -> None:
    data = [
        ["姓名", "职务", "职称", "证号", "专业"],
        ["项目负责人", "徐文", "高级工程师", "建[造]12345678", "土建"],
        ["土建负责人", "吴学军", "高级工程师", "建[造]12345679", "土建"],
        ["安装负责人", "王书文", "工程师", "建[造]12345680", "安装"],
        ["其他成员", "艾孟孟", "高级工程师", "建[造]12345681", "土建"],
    ]
    cells = [
        [(0, row, 20, row + 1), (20, row, 40, row + 1), (40, row, 60, row + 1), (60, row, 80, row + 1), (80, row, 100, row + 1)]
        for row in range(len(data))
    ]
    fake_pdf_page = SimpleNamespace(
        find_tables=lambda: SimpleNamespace(
            tables=[FakeTable(data, cells)]
        )
    )

    people, audit = _parse_coordinate_table(fake_pdf_page, _page())

    assert [(person.name, person.role) for person in people] == [
        ("徐文", "项目负责人"),
        ("吴学军", "土建负责人"),
        ("王书文", "安装负责人"),
        ("艾孟孟", "其他成员"),
    ]
    assert all(
        item.extraction_method
        == "pymupdf_coordinate_table_semantic_swap"
        for item in audit
        if item.creation_decision == "create"
    )
