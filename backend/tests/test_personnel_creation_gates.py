from app.extractors.personnel_identity import PersonnelIdentityValidator


def test_role_title_specialty_and_certificate_cannot_create_person() -> None:
    validator = PersonnelIdentityValidator()
    values = ("项目负责人", "高级", "土木", "造价工程师")
    for value in values:
        result = validator.validate(
            value,
            evidence_context="personnel_table_name_column",
            source_pdf_page=2,
            source_coordinates=(0, 0, 10, 10),
        )
        assert result.accepted is False


def test_authorization_requires_explicit_label() -> None:
    validator = PersonnelIdentityValidator()
    rejected = validator.validate(
        "张三",
        evidence_context="authorization",
        source_pdf_page=8,
    )
    accepted = validator.validate(
        "张三",
        evidence_context="authorization_explicit_label",
        source_pdf_page=8,
        has_explicit_label=True,
    )
    assert rejected.accepted is False
    assert accepted.accepted is True

