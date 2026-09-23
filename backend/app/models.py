from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

DocumentType = Literal["invoice", "contract", "receipt", "form", "report", "letter", "resume", "unknown"]


class Classification(BaseModel):
    doc_type: DocumentType
    confidence: float = Field(ge=0, le=1)
    reasoning: str = Field(min_length=1, max_length=500)


class ValidationResult(BaseModel):
    valid: bool
    confidence: float = Field(ge=0, le=1)
    issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    human_review_required: bool
    review_reason: str | None = None


class PipelineStages(BaseModel):
    agent1_classification: Classification
    agent2_extraction: dict[str, Any]
    agent3_validation: ValidationResult


class ProcessResponse(BaseModel):
    job_id: str
    status: Literal["complete"] = "complete"
    llm_provider: str
    pipeline: PipelineStages
    processing_time_ms: int = Field(ge=0)


class TextRequest(BaseModel):
    text: str = Field(min_length=10, max_length=200_000)

    @field_validator("text")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if len(value.strip()) < 10:
            raise ValueError("text must contain at least 10 non-whitespace characters")
        return value


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    llm_provider: str
    mode: Literal["demo", "llm"]
    max_upload_mb: int
