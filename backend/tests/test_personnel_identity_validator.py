from app.extractors.personnel_identity import PersonnelIdentityValidator


def test_qualification_terms_are_not_names() -> None:
    validator = PersonnelIdentityValidator()
    for value in ("高级", "中级", "一级", "高级造价工程师", "注册证书"):
        result = validator.validate(
            value,
            evidence_context="personnel_table_name_column",
            source_pdf_page=1,
            source_coordinates=(1, 1, 20, 10),
        )
        assert result.accepted is False


def test_resume_field_labels_are_not_names() -> None:
    validator = PersonnelIdentityValidator()
    for value in ("时间", "毕业学校", "工作经历", "出生年月"):
        result = validator.validate(
            value,
            evidence_context="personnel_table_name_column",
            source_pdf_page=239,
            source_coordinates=(1, 1, 20, 10),
        )
        assert result.accepted is False
        assert "blocked_name_term" in result.reason_codes


def test_two_to_four_chinese_characters_alone_are_not_sufficient() -> None:
    result = PersonnelIdentityValidator().validate(
        "土木",
        evidence_context="credential_without_name_label",
        source_pdf_page=1,
    )
    assert result.accepted is False
    assert "blocked_name_term" in result.reason_codes
    assert "unsupported_material_context" in result.reason_codes


def test_name_column_with_coordinates_is_accepted() -> None:
    result = PersonnelIdentityValidator().validate(
        "张三",
        evidence_context="personnel_table_name_column",
        source_pdf_page=25,
        source_coordinates=(100, 200, 140, 220),
    )
    assert result.accepted is True
