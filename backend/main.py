"""
Multi-Agent Document Processing Pipeline
Agents: Classifier → Extractor → Validator
LLM priority: Ollama (free, local) → AWS Bedrock → Anthropic API → Mock
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import re
import time
import uuid
import urllib.request
import urllib.error
import os

app = FastAPI(title="DocPipeline API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

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
    def mock_llm(prompt: str) -> str:
        p = prompt.lower()
        if "validation agent" in p:
            return json.dumps({"valid": True, "issues": [], "warnings": [], "confidence": 0.95, "human_review_required": False, "review_reason": None})
        elif "classify" in p:
            return json.dumps({"doc_type": "invoice", "confidence": 0.91, "reasoning": "Contains line items, total amount, and vendor info"})
        elif "extraction agent" in p or "extract" in p:
            return json.dumps({"vendor": "Acme Corp", "invoice_number": "INV-2024-001", "date": "2024-01-15", "total_amount": "$1,250.00", "line_items": [], "tax": "$0.00", "payment_terms": "Net 30"})
        else:
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
    "unknown": '{"raw_content": "", "detected_fields": {}}',
}

BUSINESS_RULES = {
    "invoice": ["vendor must be present", "total_amount must be present", "invoice_number must be present"],
    "contract": ["parties list must have at least 2 entries", "effective_date must be present"],
    "receipt": ["merchant must be present", "total must be present"],
    "form": ["form_title must be present"],
    "report": ["title must be present", "key_findings must not be empty"],
    "letter": ["sender must be present", "recipient must be present"],
    "unknown": [],
}

def _parse_json(raw: str, fallback_prompt: str) -> dict:
    clean = re.sub(r"```json|```", "", raw).strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        retry = re.sub(r"```json|```", "", llm_call(fallback_prompt + "\n\nReturn ONLY the JSON object, no other text.")).strip()
        return json.loads(retry)

def agent_classify(text: str) -> dict:
    prompt = f"""You are a document classification agent. Analyze the document and classify it.
Return ONLY valid JSON in this exact format:
{{"doc_type": "<invoice|contract|receipt|form|report|letter|unknown>", "confidence": <0-1>, "reasoning": "<one sentence>"}}

DOCUMENT:
{text[:3000]}"""
    return _parse_json(llm_call(prompt), prompt)

def agent_extract(text: str, doc_type: str) -> dict:
    schema = EXTRACTION_SCHEMAS.get(doc_type, EXTRACTION_SCHEMAS["unknown"])
    prompt = f"""You are a data extraction agent for {doc_type} documents.
Extract fields from the document. Return ONLY valid JSON matching this schema:
{schema}
Use null for missing fields. Return ONLY JSON, no markdown.

DOCUMENT:
{text[:3000]}"""
    return _parse_json(llm_call(prompt), prompt)

def agent_validate(extracted: dict, doc_type: str) -> dict:
    rules = BUSINESS_RULES.get(doc_type, [])
    prompt = f"""You are a validation agent. Check extracted data against business rules.
DOCUMENT TYPE: {doc_type}
RULES: {json.dumps(rules)}
DATA: {json.dumps(extracted)}

Return ONLY valid JSON:
{{"valid": <true|false>, "confidence": <0-1>, "issues": [], "warnings": [], "human_review_required": <true|false>, "review_reason": <null|"reason">}}"""
    try:
        return _parse_json(llm_call(prompt), prompt)
    except Exception:
        return {"valid": False, "confidence": 0.0, "issues": ["Validation failed"], "warnings": [], "human_review_required": True, "review_reason": "Parse error"}


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

@app.post("/process", response_model=ProcessResponse)
async def process_document(file: UploadFile):
    start = time.time()
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")
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