"""
Multi-Agent Document Processing Pipeline
Agents: Classifier → Extractor → Validator
LLM priority: Ollama (free, local) → AWS Bedrock → Anthropic API → Mock
"""

from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import re
import io
import time
import uuid
import urllib.request
import os

app = FastAPI(title="DocPipeline API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

def get_llm_client():
    # Option 1: Ollama
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags", method="GET")
        urllib.request.urlopen(req, timeout=2)

        def ollama_call(prompt: str) -> str:
            payload = json.dumps({"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0.1}}).encode()
            req = urllib.request.Request(f"{OLLAMA_URL}/api/generate", data=payload, headers={"Content-Type": "application/json"}, method="POST")
            resp = urllib.request.urlopen(req, timeout=60)
            return json.loads(resp.read())["response"]

        return ollama_call, f"Ollama (local) — {OLLAMA_MODEL}"
    except Exception:
        pass

    # Option 2: AWS Bedrock
    try:
        import boto3
        bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

        def bedrock_call(prompt: str) -> str:
            body = json.dumps({"anthropic_version": "bedrock-2023-05-31", "max_tokens": 1024, "messages": [{"role": "user", "content": prompt}]})
            resp = bedrock.invoke_model(modelId="anthropic.claude-3-sonnet-20240229-v1:0", body=body)
            return json.loads(resp["body"].read())["content"][0]["text"]

        return bedrock_call, "AWS Bedrock (Claude 3 Sonnet)"
    except Exception:
        pass

    # Option 3: Anthropic API
    try:
        import anthropic
        client = anthropic.Anthropic()

        def anthropic_call(prompt: str) -> str:
            msg = client.messages.create(model="claude-opus-4-5", max_tokens=1024, messages=[{"role": "user", "content": prompt}])
            return msg.content[0].text

        return anthropic_call, "Anthropic API (Claude 3)"
    except Exception:
        pass

    # Option 4: Mock
    _MOCK_EXTRACTIONS = {
        "invoice":  {"vendor": "Acme Corp", "invoice_number": "INV-2024-001", "date": "2024-01-15", "due_date": "2024-02-14", "total_amount": "$1,250.00", "line_items": [{"description": "Software License", "amount": "$1,000.00"}, {"description": "Support Package", "amount": "$250.00"}], "tax": "$0.00", "payment_terms": "Net 30"},
        "contract": {"parties": ["BuildRight LLC", "Momentum Ventures"], "effective_date": "2024-03-01", "expiration_date": "2025-02-28", "governing_law": "Delaware", "key_obligations": ["Software development services", "Monthly payment of $15,000"], "termination_clause": "30 days written notice"},
        "receipt":  {"merchant": "Blue Bottle Coffee", "date": "2024-04-22", "items": [{"name": "Ethiopia Single Origin", "price": "$22.00"}, {"name": "Cortado", "price": "$5.50"}], "subtotal": "$32.25", "tax": "$2.82", "total": "$35.07", "payment_method": "Visa ending 4242"},
        "form":     {"form_title": "Application Form", "fields": {"name": "John Doe", "date": "2024-01-15"}, "submission_date": "2024-01-15", "submitted_by": "John Doe"},
        "report":   {"title": "Annual Performance Report", "author": "Analytics Team", "date": "2024-01-01", "summary": "Overview of annual performance metrics", "key_findings": ["Revenue up 15%", "Customer satisfaction at 92%"], "recommendations": ["Expand to new markets", "Invest in automation"]},
        "letter":   {"sender": "Jane Smith", "recipient": "John Doe", "date": "2024-01-15", "subject": "Project Update", "body_summary": "Update regarding project milestones and next steps"},
        "resume":   {"name": "Alex Johnson", "email": "alex@email.com", "phone": "(415) 555-0192", "location": "San Francisco, CA", "summary": "Full-stack engineer with 5 years experience", "skills": ["Python", "React", "FastAPI", "Docker"], "experience": [{"company": "Stripe", "title": "Senior Engineer", "dates": "2022-Present"}], "education": [{"degree": "B.S. Computer Science", "school": "UC Berkeley", "year": "2020"}], "certifications": ["AWS Certified Solutions Architect"], "languages": []},
    }

    def mock_llm(prompt: str) -> str:
        p = prompt.lower()
        if "validation agent" in p:
            return json.dumps({"valid": True, "issues": [], "warnings": [], "confidence": 0.95, "human_review_required": False, "review_reason": None})
        if "classify" in p:
            if any(k in p for k in ["invoice number", "bill to", "total due", "payment terms"]):
                return json.dumps({"doc_type": "invoice", "confidence": 0.93, "reasoning": "Contains invoice number, vendor, and billing information"})
            if any(k in p for k in ["service agreement", "governing law", "termination", "parties"]):
                return json.dumps({"doc_type": "contract", "confidence": 0.91, "reasoning": "Contains parties, terms, and legal agreement language"})
            if any(k in p for k in ["merchant", "subtotal", "receipt"]):
                return json.dumps({"doc_type": "receipt", "confidence": 0.94, "reasoning": "Contains merchant, items, and payment confirmation"})
            if any(k in p for k in ["experience", "skills", "education", "resume", "curriculum vitae"]):
                return json.dumps({"doc_type": "resume", "confidence": 0.92, "reasoning": "Contains work experience, skills, and education sections"})
            if any(k in p for k in ["findings", "recommendations", "executive summary"]):
                return json.dumps({"doc_type": "report", "confidence": 0.89, "reasoning": "Contains structured findings and recommendations"})
            if any(k in p for k in ["dear ", "sincerely", "regards", "to whom"]):
                return json.dumps({"doc_type": "letter", "confidence": 0.90, "reasoning": "Contains salutation and formal correspondence structure"})
            if any(k in p for k in ["form_title", "submitted by", "submission date", "fields:"]):
                return json.dumps({"doc_type": "form", "confidence": 0.88, "reasoning": "Contains form fields and submission metadata"})
            return json.dumps({"doc_type": "unknown", "confidence": 0.50, "reasoning": "Document type could not be determined"})
        if "extraction agent" in p or "extract fields" in p:
            for doc_type, data in _MOCK_EXTRACTIONS.items():
                if f"for {doc_type} documents" in p:
                    return json.dumps(data)
            return json.dumps(_MOCK_EXTRACTIONS["invoice"])
        return json.dumps({"valid": True, "issues": [], "warnings": [], "confidence": 0.95, "human_review_required": False, "review_reason": None})

    return mock_llm, "Mock LLM (Demo Mode — install Ollama for real AI)"


llm_call, llm_name = get_llm_client()

EXTRACTION_SCHEMAS = {
    "invoice": '{"vendor": "", "invoice_number": "", "date": "", "due_date": "", "total_amount": "", "line_items": [], "tax": "", "payment_terms": ""}',
    "contract": '{"parties": [], "effective_date": "", "expiration_date": "", "governing_law": "", "key_obligations": [], "termination_clause": ""}',
    "receipt": '{"merchant": "", "date": "", "items": [], "subtotal": "", "tax": "", "total": "", "payment_method": ""}',
    "form": '{"form_title": "", "fields": {}, "submission_date": "", "submitted_by": ""}',
    "report": '{"title": "", "author": "", "date": "", "summary": "", "key_findings": [], "recommendations": []}',
    "letter": '{"sender": "", "recipient": "", "date": "", "subject": "", "body_summary": ""}',
    "resume": '{"name": "", "email": "", "phone": "", "location": "", "summary": "", "skills": [], "experience": [], "education": [], "certifications": [], "languages": []}',
    "unknown": '{"raw_content": "", "detected_fields": {}}',
}

BUSINESS_RULES = {
    "invoice": ["vendor must be present", "total_amount must be present", "invoice_number must be present"],
    "contract": ["parties list must have at least 2 entries", "effective_date must be present"],
    "receipt": ["merchant must be present", "total must be present"],
    "form": ["form_title must be present"],
    "report": ["title must be present", "key_findings must not be empty"],
    "letter": ["sender must be present", "recipient must be present"],
    "resume": ["name must be present", "experience must not be empty or skills must not be empty"],
    "unknown": [],
}

CHUNK_SIZE = 3000
CHUNK_OVERLAP = 300

def _chunk_text(text: str) -> list:
    if len(text) <= CHUNK_SIZE:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        if end < len(text):
            break_at = text.rfind("\n", start, end)
            if break_at > start:
                end = break_at
        chunks.append(text[start:end])
        start = end - CHUNK_OVERLAP
        if start >= len(text):
            break
    return chunks

def _aggregate_extractions(extractions: list, doc_type: str) -> dict:
    if len(extractions) == 1:
        return extractions[0]
    schema = json.loads(EXTRACTION_SCHEMAS.get(doc_type, EXTRACTION_SCHEMAS["unknown"]))
    merged = {}
    for key in schema:
        vals = [e[key] for e in extractions if e.get(key) not in (None, "", [], {})]
        if not vals:
            merged[key] = schema[key]
        elif isinstance(schema[key], list):
            seen, combined = set(), []
            for v in vals:
                if isinstance(v, list):
                    for item in v:
                        s = json.dumps(item, sort_keys=True) if isinstance(item, dict) else str(item)
                        if s not in seen:
                            seen.add(s)
                            combined.append(item)
            merged[key] = combined
        else:
            merged[key] = vals[0]
    return merged

def _parse_json(raw: str, fallback_prompt: str) -> dict:
    clean = re.sub(r"```json|```", "", raw).strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        retry = re.sub(r"```json|```", "", llm_call(fallback_prompt + "\n\nReturn ONLY the JSON object, no other text.")).strip()
        try:
            return json.loads(retry)
        except json.JSONDecodeError:
            raise ValueError("Could not parse JSON from LLM response — flagged for human review")

def agent_classify(text: str) -> dict:
    prompt = f"""You are a document classification agent. Analyze the document and classify it.
Return ONLY valid JSON in this exact format:
{{"doc_type": "<invoice|contract|receipt|form|report|letter|resume|unknown>", "confidence": <0-1>, "reasoning": "<one sentence>"}}

DOCUMENT:
{text[:CHUNK_SIZE]}"""
    return _parse_json(llm_call(prompt), prompt)

def agent_extract(text: str, doc_type: str) -> dict:
    schema = EXTRACTION_SCHEMAS.get(doc_type, EXTRACTION_SCHEMAS["unknown"])
    chunks = _chunk_text(text)

    def _extract_chunk(chunk: str) -> dict:
        prompt = f"""You are a data extraction agent for {doc_type} documents.
Extract fields from the document. Return ONLY valid JSON matching this schema:
{schema}
Use null for missing fields. Return ONLY JSON, no markdown.

DOCUMENT:
{chunk}"""
        return _parse_json(llm_call(prompt), prompt)

    if len(chunks) == 1:
        return _extract_chunk(chunks[0])

    extractions = []
    for chunk in chunks:
        try:
            extractions.append(_extract_chunk(chunk))
        except Exception:
            pass
    if not extractions:
        raise ValueError("All chunks failed extraction")
    return _aggregate_extractions(extractions, doc_type)

def _validate_deterministic(extracted: dict, doc_type: str) -> dict:
    issues, warnings = [], []

    def present(key):
        v = extracted.get(key)
        return v is not None and str(v).strip() not in ("", "null", "None")

    def nonempty_list(key):
        v = extracted.get(key)
        return isinstance(v, list) and len(v) > 0

    if doc_type == "invoice":
        if not present("vendor"):         issues.append("Vendor is missing")
        if not present("invoice_number"): issues.append("Invoice number is missing")
        if not present("total_amount"):   issues.append("Total amount is missing")
        if not present("date"):           warnings.append("Invoice date is missing")
        if not present("due_date"):       warnings.append("Due date is missing")
        if not nonempty_list("line_items"): warnings.append("No line items found")

    elif doc_type == "contract":
        parties = extracted.get("parties", [])
        if not isinstance(parties, list) or len(parties) < 2:
            issues.append("Contract must list at least 2 parties")
        if not present("effective_date"):  issues.append("Effective date is missing")
        if not present("expiration_date"): warnings.append("Expiration date is missing")
        if not present("governing_law"):   warnings.append("Governing law is missing")
        if not nonempty_list("key_obligations"): warnings.append("No key obligations listed")

    elif doc_type == "receipt":
        if not present("merchant"): issues.append("Merchant name is missing")
        if not present("total"):    issues.append("Total amount is missing")
        if not present("date"):     warnings.append("Date is missing")
        if not nonempty_list("items"): warnings.append("No items found")

    elif doc_type == "form":
        if not present("form_title"): issues.append("Form title is missing")
        fields = extracted.get("fields", {})
        if not isinstance(fields, dict) or len(fields) == 0:
            warnings.append("No form fields were extracted")

    elif doc_type == "report":
        if not present("title"):              issues.append("Report title is missing")
        if not nonempty_list("key_findings"): issues.append("Key findings are empty")
        if not nonempty_list("recommendations"): warnings.append("No recommendations provided")
        if not present("author"):  warnings.append("Author is missing")

    elif doc_type == "letter":
        if not present("sender"):    issues.append("Sender is missing")
        if not present("recipient"): issues.append("Recipient is missing")
        if not present("subject"):   warnings.append("Subject line is missing")
        if not present("date"):      warnings.append("Date is missing")

    elif doc_type == "resume":
        if not present("name"): issues.append("Name is missing")
        if not present("email") and not present("phone"):
            issues.append("No contact information (email or phone) found")
        if not nonempty_list("experience") and not nonempty_list("skills"):
            issues.append("No experience or skills found")
        if not nonempty_list("education"): warnings.append("Education section is missing")
        email = str(extracted.get("email") or "")
        if email and not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            warnings.append(f"Email format appears invalid: {email}")

    valid = len(issues) == 0
    confidence = 1.0 if valid and not warnings else (0.75 if valid else 0.4)
    return {
        "valid": valid,
        "confidence": confidence,
        "issues": issues,
        "warnings": warnings,
        "human_review_required": not valid,
        "review_reason": issues[0] if issues else None,
    }

def agent_validate(extracted: dict, doc_type: str) -> dict:
    det = _validate_deterministic(extracted, doc_type)
    # If hard issues found, skip LLM and return immediately
    if det["issues"]:
        return det
    prompt = f"""You are a validation agent. Review the extracted data for semantic correctness and data quality issues.
DOCUMENT TYPE: {doc_type}
DATA: {json.dumps(extracted)}

Check for suspicious values, inconsistencies, or data quality problems.
Return ONLY valid JSON:
{{"valid": true, "confidence": <0-1>, "issues": [], "warnings": ["<any quality issues found>"], "human_review_required": <true|false>, "review_reason": <null|"reason">}}"""
    try:
        llm_result = _parse_json(llm_call(prompt), prompt)
        llm_warnings = [w for w in llm_result.get("warnings", []) if w not in det["warnings"]]
        # Only trust LLM's human_review flag if it also produced actual warnings
        llm_needs_review = llm_result.get("human_review_required", False) and bool(llm_warnings)
        return {
            "valid": det["valid"],
            "confidence": min(det["confidence"], llm_result.get("confidence", 1.0)),
            "issues": det["issues"],
            "warnings": det["warnings"] + llm_warnings,
            "human_review_required": det["human_review_required"] or llm_needs_review,
            "review_reason": det["review_reason"] or llm_result.get("review_reason"),
        }
    except Exception:
        return det


class ProcessResponse(BaseModel):
    job_id: str
    status: str
    llm_provider: str
    pipeline: dict
    processing_time_ms: int

@app.get("/")
def root():
    return {"service": "DocPipeline API", "llm": llm_name, "status": "running"}

@app.get("/health")
def health():
    return {"status": "ok", "llm_provider": llm_name}

def _extract_text(content: bytes, filename: str) -> str:
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            if text.strip():
                return text
        except Exception:
            pass
    if name.endswith(".docx"):
        try:
            import docx
            doc = docx.Document(io.BytesIO(content))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception:
            pass
    if name.endswith(".csv"):
        try:
            import csv
            decoded = content.decode("utf-8", errors="replace")
            rows = list(csv.reader(io.StringIO(decoded)))
            return "\n".join(", ".join(row) for row in rows)
        except Exception:
            pass
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("latin-1")

@app.post("/process", response_model=ProcessResponse)
async def process_document(file: UploadFile):
    start = time.time()
    content = await file.read()
    text = _extract_text(content, file.filename or "")
    if len(text.strip()) < 10:
        raise HTTPException(status_code=400, detail="Document too short or unreadable")
    try:
        c = agent_classify(text)
        e = agent_extract(text, c.get("doc_type", "unknown"))
        v = agent_validate(e, c.get("doc_type", "unknown"))
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {ex}")
    return ProcessResponse(job_id=str(uuid.uuid4())[:8], status="complete", llm_provider=llm_name,
        pipeline={"agent1_classification": c, "agent2_extraction": e, "agent3_validation": v},
        processing_time_ms=int((time.time() - start) * 1000))

@app.post("/process-text")
async def process_text(payload: dict):
    text = payload.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="No text provided")
    start = time.time()
    c = agent_classify(text)
    e = agent_extract(text, c.get("doc_type", "unknown"))
    v = agent_validate(e, c.get("doc_type", "unknown"))
    return {"job_id": str(uuid.uuid4())[:8], "status": "complete", "llm_provider": llm_name,
        "pipeline": {"agent1_classification": c, "agent2_extraction": e, "agent3_validation": v},
        "processing_time_ms": int((time.time() - start) * 1000)}