from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from shared.aws import batch_handler, to_dynamo
from shared.documents import DocumentError, extract_text
from shared.pipeline import classify, extract, validate


def test_cloud_document_reader_supports_structured_text() -> None:
    assert extract_text(b'{"invoice": 42}', "input.json") == '{\n  "invoice": 42\n}'
    assert extract_text(b"name,total\nNorthstar,42", "input.csv") == "name | total\nNorthstar | 42"


def test_cloud_document_reader_rejects_bad_utf8() -> None:
    with pytest.raises(DocumentError, match="UTF-8"):
        extract_text(b"\xff\xfe", "input.txt")


def test_bedrock_stage_outputs_are_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter(
        [
            {"doc_type": "INVOICE", "confidence": 2, "reasoning": "Invoice structure"},
            {"vendor": "Northstar", "invoice_number": "N-7", "total_amount": "$25.00", "extra": "ignored"},
            {"valid": True, "confidence": 0.92, "issues": [], "warnings": [], "human_review_required": False},
        ]
    )
    monkeypatch.setattr("shared.pipeline.complete_json", lambda *_args, **_kwargs: next(responses))

    classification = classify("INVOICE\nInvoice Number: N-7\nTotal Due: $25.00")
    extraction = extract("source", classification["doc_type"])
    validation = validate(extraction, classification["doc_type"])

    assert classification == {"doc_type": "invoice", "confidence": 1.0, "reasoning": "Invoice structure"}
    assert extraction["vendor"] == "Northstar"
    assert "extra" not in extraction
    assert validation["valid"] is True
    assert validation["human_review_required"] is False


def test_deterministic_required_fields_override_model_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "shared.pipeline.complete_json",
        lambda *_args, **_kwargs: {
            "valid": True,
            "confidence": 0.99,
            "issues": [],
            "warnings": [],
            "human_review_required": False,
        },
    )
    result = validate({"vendor": "Northstar"}, "invoice")
    assert result["valid"] is False
    assert result["human_review_required"] is True
    assert "invoice_number" in " ".join(result["issues"])


def test_dynamo_conversion_is_recursive() -> None:
    assert to_dynamo({"confidence": 0.95, "items": [1.5]}) == {
        "confidence": Decimal("0.95"),
        "items": [Decimal("1.5")],
    }


def test_batch_handler_reports_only_failed_records(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shared.aws.fail_job", lambda *_args: None)
    monkeypatch.setattr("shared.aws.extend_visibility", lambda *_args: None)

    def processor(payload: dict) -> None:
        if payload["job_id"] == "bad":
            raise RuntimeError("retry me")

    result = batch_handler(
        {
            "Records": [
                {"messageId": "1", "body": '{"job_id":"good"}'},
                {"messageId": "2", "body": '{"job_id":"bad"}'},
            ]
        },
        "extract",
        processor,
    )
    assert result == {"batchItemFailures": [{"itemIdentifier": "2"}]}


def test_sam_template_contains_resume_architecture() -> None:
    template = (Path(__file__).parents[1] / "template.yaml").read_text()
    loader = type("CloudFormationLoader", (yaml.SafeLoader,), {})

    def construct_intrinsic(loader_instance, _suffix, node):
        if isinstance(node, yaml.ScalarNode):
            return loader_instance.construct_scalar(node)
        if isinstance(node, yaml.SequenceNode):
            return loader_instance.construct_sequence(node)
        return loader_instance.construct_mapping(node)

    loader.add_multi_constructor("!", construct_intrinsic)
    parsed = yaml.load(template, Loader=loader)
    assert parsed["Transform"] == "AWS::Serverless-2016-10-31"
    assert template.count("Type: AWS::SQS::Queue\n") == 6
    assert template.count("FunctionResponseTypes: [ReportBatchItemFailures]") == 3
    assert "Type: AWS::DynamoDB::Table" in template
    assert "Type: AWS::S3::Bucket" in template
    assert "Type: AWS::Serverless::HttpApi" in template
    assert "bedrock:InvokeModel" in template
    assert "Tracing: Active" in template
    assert template.count("Type: AWS::CloudWatch::Alarm") == 3
