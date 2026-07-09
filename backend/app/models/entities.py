from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RecordMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    created_source: Mapped[str] = mapped_column(String(64), default="system", nullable=False)
    record_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class User(RecordMixin, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    roles: Mapped[list[Role]] = relationship(secondary=user_roles, back_populates="users")


class Role(RecordMixin, Base):
    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    permissions: Mapped[list[str]] = mapped_column(JSON, default=list)
    users: Mapped[list[User]] = relationship(secondary=user_roles, back_populates="roles")


class Project(RecordMixin, Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(300), index=True)
    code: Mapped[str | None] = mapped_column(String(100), index=True)
    mode: Mapped[str] = mapped_column(String(32), default="single_file")
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    owner: Mapped[User] = relationship()
    bidders: Mapped[list[Bidder]] = relationship(back_populates="project")
    documents: Mapped[list[SourceDocument]] = relationship(back_populates="project")


class Bidder(RecordMixin, Base):
    __tablename__ = "bidders"
    __table_args__ = (UniqueConstraint("project_id", "name", name="bidder_project_name"),)

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(300))
    unified_credit_code_masked: Mapped[str | None] = mapped_column(String(64))
    unified_credit_code_hmac: Mapped[bytes | None] = mapped_column(LargeBinary(32), index=True)
    project: Mapped[Project] = relationship(back_populates="bidders")


class SourceDocument(RecordMixin, Base):
    __tablename__ = "source_documents"
    __table_args__ = (
        UniqueConstraint("project_id", "sha256", "version_number", name="document_digest_version"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    bidder_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bidders.id"))
    document_type: Mapped[str] = mapped_column(String(64), index=True)
    original_filename: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(100))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    file_size: Mapped[int] = mapped_column(BigInteger)
    page_count: Mapped[int | None] = mapped_column(Integer)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    storage_path: Mapped[str] = mapped_column(String(1000))
    scan_status: Mapped[str] = mapped_column(String(32), default="pending")
    parse_status: Mapped[str] = mapped_column(String(32), default="pending")
    project: Mapped[Project] = relationship(back_populates="documents")
    bidder: Mapped[Bidder | None] = relationship()
    versions: Mapped[list[DocumentVersion]] = relationship(back_populates="document")
    pages: Mapped[list[DocumentPage]] = relationship(back_populates="document")


class DocumentVersion(RecordMixin, Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="document_version_number"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_documents.id", ondelete="CASCADE")
    )
    version_number: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_path: Mapped[str] = mapped_column(String(1000))
    change_reason: Mapped[str | None] = mapped_column(Text)
    document: Mapped[SourceDocument] = relationship(back_populates="versions")


class DocumentPage(RecordMixin, Base):
    __tablename__ = "document_pages"
    __table_args__ = (
        UniqueConstraint("document_id", "pdf_page_number", name="document_pdf_page"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_documents.id", ondelete="CASCADE"), index=True
    )
    pdf_page_number: Mapped[int] = mapped_column(Integer)
    printed_page_number: Mapped[str | None] = mapped_column(String(64))
    text_content: Mapped[str | None] = mapped_column(Text)
    ocr_text: Mapped[str | None] = mapped_column(Text)
    image_path: Mapped[str | None] = mapped_column(String(1000))
    width: Mapped[float | None] = mapped_column(Float)
    height: Mapped[float | None] = mapped_column(Float)
    parse_status: Mapped[str] = mapped_column(String(32), default="pending")
    extraction_method: Mapped[str | None] = mapped_column(String(64))
    document: Mapped[SourceDocument] = relationship(back_populates="pages")


class ProcessingRun(RecordMixin, Base):
    __tablename__ = "processing_runs"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    mode: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    requested_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    pipeline_version: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message_masked: Mapped[str | None] = mapped_column(Text)
    tasks: Mapped[list[ProcessingTask]] = relationship(back_populates="run")


class ProcessingTask(RecordMixin, Base):
    __tablename__ = "processing_tasks"
    __table_args__ = (
        UniqueConstraint("run_id", "task_key", name="processing_run_task_key"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("processing_runs.id", ondelete="CASCADE"), index=True
    )
    task_key: Mapped[str] = mapped_column(String(200))
    task_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    trace_id: Mapped[str | None] = mapped_column(String(64), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    run: Mapped[ProcessingRun] = relationship(back_populates="tasks")


class ExtractedFact(RecordMixin, Base):
    __tablename__ = "extracted_facts"

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("processing_runs.id"), index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_documents.id"), index=True)
    fact_type: Mapped[str] = mapped_column(String(100), index=True)
    normalized_value: Mapped[dict[str, Any]] = mapped_column(JSON)
    display_value_masked: Mapped[str | None] = mapped_column(Text)
    sensitive_value_hmac: Mapped[bytes | None] = mapped_column(LargeBinary(32), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    extraction_method: Mapped[str] = mapped_column(String(64))
    extractor_version: Mapped[str] = mapped_column(String(64))
    evidence: Mapped[list[Evidence]] = relationship(back_populates="fact")


class Evidence(RecordMixin, Base):
    __tablename__ = "evidence"

    fact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("extracted_facts.id"))
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_documents.id"), index=True)
    page_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("document_pages.id"))
    pdf_page_number: Mapped[int] = mapped_column(Integer)
    printed_page_number: Mapped[str | None] = mapped_column(String(64))
    bounding_box: Mapped[dict[str, float] | None] = mapped_column(JSON)
    quote_masked: Mapped[str] = mapped_column(Text)
    screenshot_path: Mapped[str | None] = mapped_column(String(1000))
    extraction_method: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float)
    fact: Mapped[ExtractedFact | None] = relationship(back_populates="evidence")


class PersonnelRecord(RecordMixin, Base):
    __tablename__ = "personnel_records"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    bidder_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bidders.id"), index=True)
    name_masked: Mapped[str] = mapped_column(String(200))
    name_hmac: Mapped[bytes | None] = mapped_column(LargeBinary(32), index=True)
    role_name: Mapped[str | None] = mapped_column(String(200))
    title: Mapped[str | None] = mapped_column(String(200))
    specialty: Mapped[str | None] = mapped_column(String(200))
    source_fact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("extracted_facts.id"))
    aliases: Mapped[list[PersonnelAlias]] = relationship(back_populates="personnel")
    credentials: Mapped[list[CredentialRecord]] = relationship(back_populates="personnel")
    social_security_refs: Mapped[list[SocialSecurityReference]] = relationship(
        back_populates="personnel"
    )


class PersonnelAlias(RecordMixin, Base):
    __tablename__ = "personnel_aliases"

    personnel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("personnel_records.id", ondelete="CASCADE")
    )
    alias_masked: Mapped[str] = mapped_column(String(200))
    alias_hmac: Mapped[bytes | None] = mapped_column(LargeBinary(32), index=True)
    alias_type: Mapped[str] = mapped_column(String(32), default="extracted")
    personnel: Mapped[PersonnelRecord] = relationship(back_populates="aliases")


class CredentialRecord(RecordMixin, Base):
    __tablename__ = "credential_records"

    personnel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("personnel_records.id"))
    credential_type: Mapped[str] = mapped_column(String(100), index=True)
    level: Mapped[str | None] = mapped_column(String(100))
    specialty: Mapped[str | None] = mapped_column(String(200))
    number_masked: Mapped[str | None] = mapped_column(String(200))
    number_hmac: Mapped[bytes | None] = mapped_column(LargeBinary(32), index=True)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_fact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("extracted_facts.id"))
    personnel: Mapped[PersonnelRecord] = relationship(back_populates="credentials")


class SocialSecurityReference(RecordMixin, Base):
    __tablename__ = "social_security_references"

    personnel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("personnel_records.id"))
    employer_name_masked: Mapped[str | None] = mapped_column(String(300))
    employer_name_hmac: Mapped[bytes | None] = mapped_column(LargeBinary(32), index=True)
    account_masked: Mapped[str | None] = mapped_column(String(100))
    account_hmac: Mapped[bytes | None] = mapped_column(LargeBinary(32), index=True)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_status: Mapped[str] = mapped_column(String(32), default="unverified")
    source_fact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("extracted_facts.id"))
    personnel: Mapped[PersonnelRecord] = relationship(back_populates="social_security_refs")


class Finding(RecordMixin, Base):
    __tablename__ = "findings"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("processing_runs.id"), index=True)
    rule_code: Mapped[str] = mapped_column(String(100), index=True)
    rule_version: Mapped[str] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text)
    risk_level: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending_review", index=True)
    requires_materials: Mapped[list[str]] = mapped_column(JSON, default=list)
    evidence_links: Mapped[list[FindingEvidence]] = relationship(back_populates="finding")
    decisions: Mapped[list[ReviewDecision]] = relationship(back_populates="finding")


class FindingEvidence(RecordMixin, Base):
    __tablename__ = "finding_evidence"
    __table_args__ = (
        UniqueConstraint("finding_id", "evidence_id", name="finding_evidence_pair"),
    )

    finding_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE")
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE")
    )
    relevance: Mapped[str | None] = mapped_column(String(200))
    finding: Mapped[Finding] = relationship(back_populates="evidence_links")
    evidence: Mapped[Evidence] = relationship()


class CrossDocumentMatch(RecordMixin, Base):
    __tablename__ = "cross_document_matches"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("processing_runs.id"))
    match_type: Mapped[str] = mapped_column(String(100), index=True)
    left_document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_documents.id"))
    right_document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_documents.id"))
    score: Mapped[float] = mapped_column(Float)
    details: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="clue")


class ReviewDecision(RecordMixin, Base):
    __tablename__ = "review_decisions"
    __table_args__ = (Index("ix_review_decision_finding_created", "finding_id", "created_at"),)

    finding_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("findings.id"), index=True)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(32))
    revised_risk_level: Mapped[str | None] = mapped_column(String(32))
    revised_description: Mapped[str | None] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    finding_version: Mapped[int] = mapped_column(Integer)
    finding: Mapped[Finding] = relationship(back_populates="decisions")


class GeneratedReport(RecordMixin, Base):
    __tablename__ = "generated_reports"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("processing_runs.id"))
    report_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="queued")
    template_version: Mapped[str] = mapped_column(String(64))
    storage_path: Mapped[str | None] = mapped_column(String(1000))
    sha256: Mapped[str | None] = mapped_column(String(64))
    generated_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class PromptVersion(RecordMixin, Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (UniqueConstraint("code", "version", name="prompt_code_version"),)

    code: Mapped[str] = mapped_column(String(100))
    version: Mapped[str] = mapped_column(String(64))
    task_type: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text)
    schema_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    checksum: Mapped[str] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)


class RuleVersion(RecordMixin, Base):
    __tablename__ = "rule_versions"
    __table_args__ = (UniqueConstraint("code", "version", name="rule_code_version"),)

    code: Mapped[str] = mapped_column(String(100))
    version: Mapped[str] = mapped_column(String(64))
    rule_type: Mapped[str] = mapped_column(String(64))
    definition: Mapped[dict[str, Any]] = mapped_column(JSON)
    checksum: Mapped[str] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)


class ModelCallLog(RecordMixin, Base):
    __tablename__ = "model_call_logs"

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("processing_runs.id"), index=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("processing_tasks.id"))
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_documents.id"))
    task_type: Mapped[str] = mapped_column(String(100))
    page_range: Mapped[str | None] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(64))
    model_name: Mapped[str] = mapped_column(String(200))
    prompt_version: Mapped[str] = mapped_column(String(64))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message_masked: Mapped[str | None] = mapped_column(Text)


class AuditLog(RecordMixin, Base):
    __tablename__ = "audit_logs"

    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"), index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100), index=True)
    resource_type: Mapped[str] = mapped_column(String(100), index=True)
    resource_id: Mapped[str | None] = mapped_column(String(100))
    request_id: Mapped[str | None] = mapped_column(String(64), index=True)
    ip_address_masked: Mapped[str | None] = mapped_column(String(100))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    before_data_masked: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after_data_masked: Mapped[dict[str, Any] | None] = mapped_column(JSON)
