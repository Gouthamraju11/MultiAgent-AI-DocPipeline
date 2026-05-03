#!/usr/bin/env python3
"""
Quick local test for the DocPipeline backend.
Run from the project root: python test_pipeline.py
No API keys needed — uses mock LLM.
"""

import sys
import json

# ── 1. Check dependencies ──────────────────────────────────────────────
print("=== DocPipeline Local Test ===\n")

missing = []
for pkg in ["fastapi", "uvicorn", "pydantic"]:
    try:
        __import__(pkg)
    except ImportError:
        missing.append(pkg)

if missing:
    print(f"❌ Missing packages: {', '.join(missing)}")
    print("   Run: pip install -r backend/requirements.txt")
    sys.exit(1)

print("✓ Dependencies OK")

# ── 2. Import agents directly from main.py ────────────────────────────
sys.path.insert(0, "backend")
from main import agent_classify, agent_extract, agent_validate, llm_name

print(f"✓ LLM provider: {llm_name}\n")

# ── 3. Sample documents ───────────────────────────────────────────────
SAMPLES = {
    "invoice": """
INVOICE

Vendor: Acme Corp
Invoice Number: INV-2024-001
Invoice Date: January 15, 2024
Due Date: February 14, 2024

Line Items:
1. Software License (Annual)    Qty: 1    $1,000.00
2. Premium Support Package      Qty: 1    $250.00

Total Due: $1,250.00
Payment Terms: Net 30
""",
    "contract": """
SERVICE AGREEMENT

This Agreement is between BuildRight LLC ("Service Provider") and Momentum Ventures ("Client"),
effective March 1, 2024 through February 28, 2025.

Services: Custom software development
Payment: $15,000/month, due Net 15
Governing Law: State of Delaware
Termination: 30 days written notice by either party.
""",
    "receipt": """
RECEIPT — Blue Bottle Coffee
Date: April 22, 2024

Ethiopia Single Origin    $22.00
Cortado                    $5.50
Almond Croissant           $4.75

Subtotal: $32.25
Tax (8.75%): $2.82
Total: $35.07
Payment: Visa ending 4242
"""
}

# ── 4. Run pipeline on each sample ───────────────────────────────────
errors = []

for name, text in SAMPLES.items():
    print(f"─── Testing: {name.upper()} ───────────────────────")
    try:
        # Agent 1
        classification = agent_classify(text)
        doc_type = classification.get("doc_type", "unknown")
        confidence = classification.get("confidence", 0)
        print(f"  Agent 1 → {doc_type} ({confidence*100:.0f}% confidence)")

        # Agent 2
        extraction = agent_extract(text, doc_type)
        filled = sum(1 for v in extraction.values() if v and v != "null")
        print(f"  Agent 2 → {filled}/{len(extraction)} fields extracted")

        # Agent 3
        validation = agent_validate(extraction, doc_type)
        status = "✓ valid" if validation.get("valid") else "✗ invalid"
        review = " — HUMAN REVIEW" if validation.get("human_review_required") else ""
        print(f"  Agent 3 → {status}{review}")

        issues = validation.get("issues", [])
        if issues:
            for issue in issues:
                print(f"           ⚠ {issue}")

        print(f"  ✅ PASS\n")
    except Exception as e:
        print(f"  ❌ FAIL: {e}\n")
        errors.append(f"{name}: {e}")

# ── 5. Test the API endpoints (if server is running) ──────────────────
print("─── API endpoint test (requires server) ───────────────────")
try:
    import urllib.request
    import urllib.error

    req = urllib.request.urlopen("http://localhost:8000/health", timeout=2)
    data = json.loads(req.read())
    print(f"  ✅ Server is running — LLM: {data.get('llm_provider', 'unknown')}")

    # POST to /process-text
    payload = json.dumps({"text": SAMPLES["invoice"]}).encode()
    req2 = urllib.request.Request(
        "http://localhost:8000/process-text",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    resp = urllib.request.urlopen(req2, timeout=10)
    result = json.loads(resp.read())
    doc_type = result["pipeline"]["agent1_classification"]["doc_type"]
    ms = result["processing_time_ms"]
    print(f"  ✅ /process-text → {doc_type} in {ms}ms")

except urllib.error.URLError:
    print("  ℹ  Server not running — start it with:")
    print("     cd backend && uvicorn main:app --reload --port 8000")
except Exception as e:
    print(f"  ⚠  API test error: {e}")

# ── 6. Summary ────────────────────────────────────────────────────────
print("\n=== Summary ===")
if errors:
    print(f"❌ {len(errors)} test(s) failed:")
    for e in errors:
        print(f"   • {e}")
    sys.exit(1)
else:
    print("✅ All agent tests passed!")
    print("\nNext steps:")
    print("  1. cd backend && uvicorn main:app --reload --port 8000")
    print("  2. cd frontend && npm install && npm run dev")
    print("  3. Open http://localhost:5173")
