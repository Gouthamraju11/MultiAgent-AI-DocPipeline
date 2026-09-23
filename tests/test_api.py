from fastapi.testclient import TestClient

INVOICE = """
INVOICE
Vendor: Northstar Software
Invoice Number: NS-1042
Invoice Date: September 2, 2026
1. Platform subscription $900.00
Tax: $45.00
Total Due: $945.00
Payment Terms: Net 30
"""


def test_health_reports_honest_demo_mode(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "llm_provider": "Deterministic demo mode",
        "mode": "demo",
        "max_upload_mb": 1,
    }


def test_process_text_extracts_values_from_supplied_document(client: TestClient) -> None:
    response = client.post("/process-text", json={"text": INVOICE})
    assert response.status_code == 200
    body = response.json()
    classification = body["pipeline"]["agent1_classification"]
    extraction = body["pipeline"]["agent2_extraction"]
    validation = body["pipeline"]["agent3_validation"]
    assert classification["doc_type"] == "invoice"
    assert extraction["vendor"] == "Northstar Software"
    assert extraction["invoice_number"] == "NS-1042"
    assert extraction["total_amount"] == "$945.00"
    assert validation["valid"] is True
    assert len(body["job_id"]) == 12


def test_text_validation_rejects_blank_input(client: TestClient) -> None:
    response = client.post("/process-text", json={"text": "      "})
    assert response.status_code == 422


def test_file_upload_uses_same_pipeline(client: TestClient) -> None:
    response = client.post(
        "/process",
        files={"file": ("invoice.txt", INVOICE.encode(), "text/plain")},
    )
    assert response.status_code == 200
    assert response.json()["pipeline"]["agent2_extraction"]["vendor"] == "Northstar Software"


def test_unsupported_upload_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/process",
        files={"file": ("payload.exe", b"this should never be parsed", "application/octet-stream")},
    )
    assert response.status_code == 415


def test_oversized_upload_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/process",
        files={"file": ("large.txt", b"x" * 1025, "text/plain")},
    )
    assert response.status_code == 413


def test_every_response_has_request_metadata(client: TestClient) -> None:
    response = client.get("/")
    assert response.headers["x-request-id"]
    assert response.headers["x-process-time-ms"].isdigit()
