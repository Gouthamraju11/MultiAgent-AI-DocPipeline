#!/usr/bin/env python3
"""Small zero-credential smoke test. Run after installing backend requirements."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.pipeline import DocumentPipeline
from app.providers import DeterministicProvider

SAMPLE = """
INVOICE
Vendor: Northstar Software
Invoice Number: NS-1042
Invoice Date: September 2, 2026
1. Platform subscription $900.00
Total Due: $900.00
Payment Terms: Net 30
"""


def main() -> None:
    result = DocumentPipeline(DeterministicProvider()).run(SAMPLE)
    assert result.agent1_classification.doc_type == "invoice"
    assert result.agent2_extraction["vendor"] == "Northstar Software"
    assert result.agent2_extraction["invoice_number"] == "NS-1042"
    assert result.agent2_extraction["total_amount"] == "$900.00"
    assert result.agent3_validation.valid is True
    print("DocPipeline smoke test passed")
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
