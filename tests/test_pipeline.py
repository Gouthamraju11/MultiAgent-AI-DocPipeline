import json

import pytest
from app.pipeline import (
    DocumentPipeline,
    aggregate_extractions,
    chunk_text,
    deterministic_validate,
    parse_json_object,
)
from app.providers import DeterministicProvider


def test_json_parser_handles_fences_and_explanation() -> None:
    value = parse_json_object('Result:\n```json\n{"doc_type":"invoice"}\n```')
    assert value == {"doc_type": "invoice"}


def test_chunking_preserves_tail_and_makes_progress() -> None:
    text = "A" * 3_900 + "\n\n" + "B" * 4_100 + "THE_END"
    chunks = chunk_text(text)
    assert len(chunks) >= 2
    assert chunks[-1].endswith("THE_END")
    assert all(chunks)


def test_aggregation_deduplicates_list_values() -> None:
    merged = aggregate_extractions(
        [
            {"vendor": "Acme", "line_items": [{"description": "A", "amount": "$1"}]},
            {"vendor": None, "line_items": [{"description": "A", "amount": "$1"}, {"description": "B", "amount": "$2"}]},
        ],
        "invoice",
    )
    assert merged["vendor"] == "Acme"
    assert len(merged["line_items"]) == 2


def test_missing_required_invoice_fields_trigger_review() -> None:
    validation = deterministic_validate({"vendor": "Acme"}, "invoice")
    assert validation.valid is False
    assert validation.human_review_required is True
    assert "Invoice number is missing" in validation.issues


def test_unknown_document_is_never_silently_approved() -> None:
    pipeline = DocumentPipeline(DeterministicProvider())
    result = pipeline.run("A generic paragraph without a recognizable business document structure.")
    assert result.agent1_classification.doc_type == "unknown"
    assert result.agent3_validation.human_review_required is True
    assert result.agent2_extraction["raw_content"].startswith("A generic paragraph")


def test_mock_pipeline_does_not_return_canned_vendor() -> None:
    text = """INVOICE\nVendor: Contoso Labs\nInvoice Number: C-99\nTotal Due: $120.00"""
    result = DocumentPipeline(DeterministicProvider()).run(text)
    assert result.agent2_extraction["vendor"] == "Contoso Labs"
    assert "Acme" not in json.dumps(result.model_dump())


def test_contract_extracts_explicit_dates_and_governing_law() -> None:
    text = """SERVICE AGREEMENT
Party A: Northstar LLC
Party B: Meridian Inc
Effective Date: September 1, 2026
Expiration Date: September 1, 2027
Governing Law: Arizona
Northstar shall provide hosting.
Termination: Either party may terminate with notice."""
    result = DocumentPipeline(DeterministicProvider()).run(text)
    assert result.agent1_classification.doc_type == "contract"
    assert result.agent2_extraction["effective_date"] == "September 1, 2026"
    assert result.agent2_extraction["governing_law"] == "Arizona"
    assert result.agent3_validation.valid is True


def test_report_keeps_individual_findings_and_recommendations() -> None:
    text = """PLATFORM REPORT
Executive Summary
Reliability improved.
Key Findings
- Uptime reached 99.9%
- Errors fell 20%
Recommendations
- Add regional drills
- Automate rollbacks"""
    result = DocumentPipeline(DeterministicProvider()).run(text)
    extraction = result.agent2_extraction
    assert extraction["key_findings"] == ["Uptime reached 99.9%", "Errors fell 20%"]
    assert extraction["recommendations"] == ["Add regional drills", "Automate rollbacks"]


@pytest.mark.parametrize(
    ("expected_type", "text"),
    [
        ("receipt", "RECEIPT\nMerchant: Corner Market\nSubtotal: $4.00\nTotal: $4.32\nPayment: Visa"),
        ("form", "APPLICATION FORM\nForm Title: Access Request\nSubmission Date: 2026-09-01\nSubmitted By: Maya"),
        ("letter", "From: Maya\nTo: Alex\nSubject: Update\nDear Alex,\nThe document is ready for your final review.\nSincerely,\nMaya"),
        ("resume", "Maya Chen\nmaya@example.com\nSKILLS\nPython, FastAPI\nEXPERIENCE\nSoftware Engineer\nEDUCATION\nBS Computer Science"),
    ],
)
def test_remaining_supported_document_types(expected_type: str, text: str) -> None:
    result = DocumentPipeline(DeterministicProvider()).run(text)
    assert result.agent1_classification.doc_type == expected_type
