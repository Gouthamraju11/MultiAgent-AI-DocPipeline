# Multi-Agent Document Processing Pipeline

> FastAPI · LangChain · AWS Bedrock · React

A three-stage AI pipeline that classifies, extracts, and validates any document.

```
[Upload] → Agent 1: Classify → Agent 2: Extract → Agent 3: Validate → [Results]
```

---

## Stack

| Layer | Tech |
|---|---|
| Agents / LLM | AWS Bedrock (Claude 3 Sonnet) → falls back to Anthropic API → Demo mode |
| Backend | FastAPI + Python 3.11 |
| Orchestration | LangChain (prompt engineering + retries) |
| Frontend | React + Vite |

---

## Quick Start

### 1. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API runs at http://localhost:8000
Swagger docs at http://localhost:8000/docs

**LLM auto-detection order:**
1. AWS Bedrock (if `~/.aws/credentials` configured)
2. Anthropic API (if `ANTHROPIC_API_KEY` env var set)
3. Mock LLM (demo mode — no keys needed)

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

UI runs at http://localhost:5173

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check + LLM provider |
| POST | `/process` | Upload a file (multipart/form-data) |
| POST | `/process-text` | Send raw text JSON `{"text": "..."}` |

### Example curl

```bash
# Upload a file
curl -X POST http://localhost:8000/process \
  -F "file=@invoice.txt"

# Send raw text
curl -X POST http://localhost:8000/process-text \
  -H "Content-Type: application/json" \
  -d '{"text": "Invoice #INV-001 from Acme Corp. Total: $1,250.00"}'
```

---

## Pipeline Architecture

### Agent 1 — Classifier
- Reads raw document text
- Outputs: `doc_type`, `confidence`, `reasoning`
- Supported types: `invoice`, `contract`, `receipt`, `form`, `report`, `letter`, `unknown`

### Agent 2 — Extractor
- Receives doc_type from Agent 1
- Uses type-specific JSON schema for structured extraction
- Handles JSON parse failures with automatic retry

### Agent 3 — Validator
- Checks extracted data against business rules per doc type
- Flags documents for human review if rules fail
- Returns: `valid`, `issues`, `warnings`, `human_review_required`

---

## Environment Variables

```bash
# Option A: Anthropic API
ANTHROPIC_API_KEY=sk-ant-...

# Option B: AWS Bedrock (also requires ~/.aws/credentials)
AWS_DEFAULT_REGION=us-east-1
```

---

## Project Structure

```
docpipeline/
├── backend/
│   ├── main.py          # FastAPI app + all three agents
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   └── App.jsx      # React UI
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
└── README.md
```
