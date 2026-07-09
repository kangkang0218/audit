from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    pdf_page: int = Field(ge=1)
    printed_page: str | None = None
    location: str
    excerpt: str
    confidence: float = Field(ge=0, le=1)
    extraction_method: str = "text"


class ExtractedFactItem(BaseModel):
    category: str
    field_name: str
    value: str | float | int | bool | None
    status: Literal["已提取", "无法确认", "需人工复核"]
    evidence: list[EvidenceItem] = Field(default_factory=list)
    note: str = ""


class PersonnelItem(BaseModel):
    name: str
    role: str
    title: str | None = None
    certificate_name: str | None = None
    certificate_level: str | None = None
    certificate_numbers: list[str] = Field(default_factory=list)
    specialty: str | None = None
    labor_contract_found: bool = False
    social_security_found: bool = False
    social_security_id_masked: str | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
    note: str = ""


class FindingItem(BaseModel):
    rule_code: str
    category: str
    title: str
    result: str
    level: Literal["未发现明显异常", "需人工复核", "存在疑点", "证据不足", "说明"]
    evidence: list[EvidenceItem] = Field(default_factory=list)
    required_materials: list[str] = Field(default_factory=list)
    note: str = ""


class PageItem(BaseModel):
    pdf_page: int
    printed_page: str | None = None
    text: str
    text_length: int
    is_low_text_page: bool
    is_candidate_for_ocr: bool
    detected_headings: list[str] = Field(default_factory=list)
    image_count: int = 0
    text_quality: Literal["empty", "low", "normal"]


class TocItem(BaseModel):
    section_name: str
    pdf_page: int
    printed_page: str | None = None
    source_method: Literal["pdf_toc", "toc_text", "keyword_fallback"]
    confidence: float = Field(ge=0, le=1)
    mapping_note: str


class LLMCallRecord(BaseModel):
    task_name: str
    provider: str
    model: str
    input_pages: list[int]
    duration_ms: int
    success: bool
    pydantic_validation: bool
    error: str | None = None


class ModelPageFact(BaseModel):
    field_name: str
    value: str | None = None
    confidence: float = Field(ge=0, le=1)


class ModelPageExtraction(BaseModel):
    facts: list[ModelPageFact] = Field(default_factory=list)


class AuditEvent(BaseModel):
    timestamp: str
    event: str
    status: str
    details: dict[str, Any] = Field(default_factory=dict)
