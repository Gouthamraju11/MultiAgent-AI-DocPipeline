from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.models import DocumentType

SCHEMAS: dict[DocumentType, dict[str, Any]] = {
    "invoice": {"vendor": None, "invoice_number": None, "date": None, "due_date": None, "total_amount": None, "line_items": [], "tax": None, "payment_terms": None},
    "contract": {"parties": [], "effective_date": None, "expiration_date": None, "governing_law": None, "key_obligations": [], "termination_clause": None},
    "receipt": {"merchant": None, "date": None, "items": [], "subtotal": None, "tax": None, "total": None, "payment_method": None},
    "form": {"form_title": None, "fields": {}, "submission_date": None, "submitted_by": None},
    "report": {"title": None, "author": None, "date": None, "summary": None, "key_findings": [], "recommendations": []},
    "letter": {"sender": None, "recipient": None, "date": None, "subject": None, "body_summary": None},
    "resume": {"name": None, "email": None, "phone": None, "location": None, "summary": None, "skills": [], "experience": [], "education": [], "certifications": [], "languages": []},
    "unknown": {"raw_content": None, "detected_fields": {}},
}


def empty_schema(doc_type: DocumentType) -> dict[str, Any]:
    return deepcopy(SCHEMAS[doc_type])


def normalize_extraction(value: object, doc_type: DocumentType) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("LLM extraction response must be a JSON object")
    normalized = empty_schema(doc_type)
    for key in normalized:
        if key in value:
            normalized[key] = value[key]
    return normalized
