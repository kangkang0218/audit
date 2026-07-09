from app.db.base import Base
import app.models  # noqa: F401


EXPECTED_TABLES = {
    "users",
    "roles",
    "projects",
    "bidders",
    "source_documents",
    "document_versions",
    "document_pages",
    "processing_runs",
    "processing_tasks",
    "extracted_facts",
    "evidence",
    "personnel_records",
    "personnel_aliases",
    "credential_records",
    "social_security_references",
    "findings",
    "finding_evidence",
    "cross_document_matches",
    "review_decisions",
    "generated_reports",
    "prompt_versions",
    "rule_versions",
    "model_call_logs",
    "audit_logs",
}


def test_required_domain_tables_exist() -> None:
    assert EXPECTED_TABLES <= set(Base.metadata.tables)


def test_domain_tables_have_audit_columns() -> None:
    for table_name in EXPECTED_TABLES:
        columns = set(Base.metadata.tables[table_name].columns.keys())
        assert {"id", "created_at", "updated_at", "created_source", "record_version"} <= columns

