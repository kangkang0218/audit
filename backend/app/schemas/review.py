from typing import Any

from pydantic import BaseModel, Field


class ReviewWorkbook(BaseModel):
    template_version: str = "single-file-legacy-v1"
    source_file: str
    generated_at: str | None = None
    overview: list[dict[str, Any]] = Field(default_factory=list)
    facts: list[dict[str, Any]] = Field(default_factory=list)
    unavailable: list[dict[str, Any]] = Field(default_factory=list)
    findings: list[dict[str, Any]] = Field(default_factory=list)
    personnel: list[dict[str, Any]] = Field(default_factory=list)
    bases: list[dict[str, Any]] = Field(default_factory=list)
    required_materials: list[dict[str, Any]] = Field(default_factory=list)

