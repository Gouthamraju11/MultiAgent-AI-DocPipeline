from __future__ import annotations

import json
from typing import Any

from shared.ai import complete_json

DOCUMENT_TYPES = {"invoice", "contract", "receipt", "form", "report", "letter", "resume", "unknown"}

SCHEMAS: dict[str, dict[str, Any]] = {
    "invoice": {"vendor": None, "invoice_number": None, "date": None, "due_date": None, "total_amount": None, "line_items": [], "tax": None, "payment_terms": None},
    "contract": {"parties": [], "effective_date": None, "expiration_date": None, "governing_law": None, "key_obligations": [], "termination_clause": None},
    "receipt": {"merchant": None, "date": None, "items": [], "subtotal": None, "tax": None, "total": None, "payment_method": None},
    "form": {"form_title": None, "fields": {}, "submission_date": None, "submitted_by": None},
    "report": {"title": None, "author": None, "date": None, "summary": None, "key_findings": [], "recommendations": []},
    "letter": {"sender": None, "recipient": None, "date": None, "subject": None, "body_summary": None},
    "resume": {"name": None, "email": None, "phone": None, "location": None, "summary": None, "skills": [], "experience": [], "education": [], "certifications": [], "languages": []},
    "unknown": {"raw_content": None, "detected_fields": {}},
}

REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "invoice": ("vendor", "invoice_number", "total_amount"),
    "contract": ("parties", "effective_date"),
    "receipt": ("merchant", "total"),
    "form": ("form_title",),
    "report": ("title", "key_findings"),
    "letter": ("sender", "recipient"),
    "resume": ("name",),
    "unknown": (),
}


def classify(text: str) -> dict[str, Any]:
    output = complete_json(
        "You are classification agent 1 in a controlled document pipeline. Classify the document as exactly one of: invoice, contract, receipt, form, report, letter, resume, unknown. Return an object with doc_type, confidence (0 through 1), and concise reasoning.",
        text[:12_000],
    )
    doc_type = str(output.get("doc_type", "unknown")).lower()
    if doc_type not in DOCUMENT_TYPES:
        doc_type = "unknown"
    try:
        confidence = max(0.0, min(1.0, float(output.get("confidence", 0))))
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "doc_type": doc_type,
        "confidence": confidence,
        "reasoning": str(output.get("reasoning") or "No model reasoning supplied")[:500],
    }


def extract(text: str, doc_type: str) -> dict[str, Any]:
    schema = SCHEMAS.get(doc_type, SCHEMAS["unknown"])
    output = complete_json(
        f"You are extraction agent 2. Extract factual values for a {doc_type} document into an object with exactly this shape: {json.dumps(schema)}. Preserve source values; use null or an empty collection when absent. Never invent data.",
        text[:100_000],
    )
    return {key: output.get(key, default) for key, default in schema.items()}


def validate(extracted: dict[str, Any], doc_type: str) -> dict[str, Any]:
    missing = [field for field in REQUIRED_FIELDS.get(doc_type, ()) if extracted.get(field) in (None, "", [], {})]
    deterministic_issues = [f"Required field is missing: {field}" for field in missing]
    output = complete_json(
        "You are validation agent 3. Identify contradictions, malformed values, and likely hallucinations in the extracted JSON. Return an object with valid (boolean), confidence (0 through 1), issues (array of strings), warnings (array of strings), human_review_required (boolean), and review_reason (string or null).",
        json.dumps({"document_type": doc_type, "extracted": extracted}, default=str),
    )
    model_issues = output.get("issues") if isinstance(output.get("issues"), list) else []
    warnings = output.get("warnings") if isinstance(output.get("warnings"), list) else []
    issues = list(dict.fromkeys([*deterministic_issues, *(str(value) for value in model_issues)]))
    if doc_type == "unknown":
        warnings.append("Unknown document type requires human review")
    needs_review = bool(issues) or doc_type == "unknown" or bool(output.get("human_review_required"))
    try:
        confidence = max(0.0, min(1.0, float(output.get("confidence", 0))))
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "valid": not issues and bool(output.get("valid", True)),
        "confidence": confidence,
        "issues": issues,
        "warnings": list(dict.fromkeys(str(value) for value in warnings)),
        "human_review_required": needs_review,
        "review_reason": issues[0] if issues else output.get("review_reason"),
    }
