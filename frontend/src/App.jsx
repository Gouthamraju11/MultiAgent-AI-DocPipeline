import { useState, useRef, useCallback } from 'react'

const API = 'http://localhost:8000'

const DOC_ICONS = {
  invoice: '🧾', contract: '📋', receipt: '🏷️',
  form: '📝', report: '📊', letter: '✉️', unknown: '📄'
}

const STATUS_COLOR = {
  idle: '#4a5568',
  uploading: '#d4a017',
  processing: '#d4a017',
  complete: '#2d6a4f',
  error: '#c0392b'
}

function AgentStep({ number, name, status, data, isActive }) {
  const [open, setOpen] = useState(false)
  const done = status === 'done'
  const running = status === 'running'

  return (
    <div style={{
      border: `1px solid ${done ? '#2d6a4f' : running ? '#d4a017' : '#2a2a2a'}`,
      borderRadius: 2,
      marginBottom: 8,
      transition: 'border-color 0.4s',
      background: done ? 'rgba(45,106,79,0.04)' : 'transparent'
    }}>
      <div
        onClick={() => done && setOpen(o => !o)}
        style={{
          display: 'flex', alignItems: 'center', gap: 12,
          padding: '12px 16px', cursor: done ? 'pointer' : 'default',
          userSelect: 'none'
        }}
      >
        <div style={{
          width: 28, height: 28, borderRadius: '50%',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 11, fontFamily: 'DM Mono, monospace', fontWeight: 500,
          background: done ? '#2d6a4f' : running ? '#d4a017' : '#1a1a1a',
          color: done || running ? '#fff' : '#555',
          border: `1px solid ${done ? '#2d6a4f' : running ? '#d4a017' : '#333'}`,
          transition: 'all 0.4s',
          flexShrink: 0
        }}>
          {done ? '✓' : running ? '⟳' : number}
        </div>
        <div style={{ flex: 1 }}>
          <div style={{
            fontSize: 11, letterSpacing: '0.12em', textTransform: 'uppercase',
            color: done ? '#2d6a4f' : running ? '#d4a017' : '#555',
            fontFamily: 'DM Mono, monospace', fontWeight: 500
          }}>
            Agent {number}
          </div>
          <div style={{ fontSize: 14, color: done ? '#e8e8e8' : '#666', fontFamily: 'Syne, sans-serif', fontWeight: 600 }}>
            {name}
          </div>
        </div>
        {done && (
          <div style={{ fontSize: 11, color: '#555', fontFamily: 'DM Mono, monospace' }}>
            {open ? '▲ hide' : '▼ show'}
          </div>
        )}
        {running && (
          <div style={{ fontSize: 11, color: '#d4a017', fontFamily: 'DM Mono, monospace', animation: 'pulse 1s infinite' }}>
            running...
          </div>
        )}
      </div>

      {open && done && data && (
        <div style={{
          borderTop: '1px solid #2a2a2a',
          padding: '12px 16px',
          background: '#0d0d0d'
        }}>
          <pre style={{
            margin: 0, fontSize: 11, lineHeight: 1.7,
            color: '#a8c5a0', fontFamily: 'DM Mono, monospace',
            overflow: 'auto', maxHeight: 300,
            whiteSpace: 'pre-wrap', wordBreak: 'break-word'
          }}>
            {JSON.stringify(data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}

function ValidationBadge({ validation }) {
  if (!validation) return null
  const { valid, human_review_required, issues, warnings, confidence } = validation
  return (
    <div style={{
      padding: '14px 18px',
      background: human_review_required ? 'rgba(192,57,43,0.08)' : valid ? 'rgba(45,106,79,0.08)' : 'rgba(192,57,43,0.08)',
      border: `1px solid ${human_review_required ? '#c0392b' : valid ? '#2d6a4f' : '#c0392b'}`,
      borderRadius: 2, marginTop: 16
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: issues?.length || warnings?.length ? 10 : 0 }}>
        <span style={{ fontSize: 18 }}>{human_review_required ? '⚠️' : valid ? '✅' : '❌'}</span>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, fontFamily: 'Syne, sans-serif', color: '#e8e8e8' }}>
            {human_review_required ? 'Human Review Required' : valid ? 'Validation Passed' : 'Validation Failed'}
          </div>
          <div style={{ fontSize: 11, color: '#888', fontFamily: 'DM Mono, monospace' }}>
            confidence: {(confidence * 100).toFixed(0)}%
          </div>
        </div>
      </div>
      {issues?.length > 0 && (
        <div style={{ marginTop: 8 }}>
          {issues.map((issue, i) => (
            <div key={i} style={{ fontSize: 11, color: '#e57373', fontFamily: 'DM Mono, monospace', marginBottom: 3 }}>
              ✗ {issue}
            </div>
          ))}
        </div>
      )}
      {warnings?.length > 0 && (
        <div style={{ marginTop: 6 }}>
          {warnings.map((w, i) => (
            <div key={i} style={{ fontSize: 11, color: '#d4a017', fontFamily: 'DM Mono, monospace', marginBottom: 3 }}>
              ⚠ {w}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function SampleDocButton({ label, text, onSelect }) {
  return (
    <button
      onClick={() => onSelect(text)}
      style={{
        background: 'transparent', border: '1px solid #2a2a2a',
        color: '#888', fontFamily: 'DM Mono, monospace', fontSize: 10,
        letterSpacing: '0.08em', padding: '5px 10px', cursor: 'pointer',
        borderRadius: 2, textTransform: 'uppercase',
        transition: 'all 0.2s'
      }}
      onMouseEnter={e => { e.target.style.borderColor = '#d4a017'; e.target.style.color = '#d4a017' }}
      onMouseLeave={e => { e.target.style.borderColor = '#2a2a2a'; e.target.style.color = '#888' }}
    >
      {label}
    </button>
  )
}

const SAMPLES = {
  invoice: `INVOICE

Vendor: Acme Corp
Invoice Number: INV-2024-001
Invoice Date: January 15, 2024
Due Date: February 14, 2024

Bill To:
TechStartup Inc.
123 Silicon Valley Blvd
San Francisco, CA 94105

Line Items:
1. Software License (Annual)    Qty: 1    Unit Price: $1,000.00    Total: $1,000.00
2. Premium Support Package      Qty: 1    Unit Price: $250.00     Total: $250.00

Subtotal: $1,250.00
Tax (0%): $0.00
Total Due: $1,250.00

Payment Terms: Net 30
Wire Transfer to: Chase Bank, Acct #123456789`,

  contract: `SERVICE AGREEMENT

This Service Agreement ("Agreement") is entered into as of March 1, 2024, between:

Party A: BuildRight LLC, a Delaware corporation ("Service Provider")
Party B: Momentum Ventures, a California LLC ("Client")

1. SERVICES
Service Provider agrees to deliver custom software development services as described in Exhibit A.

2. TERM
This Agreement shall commence on March 1, 2024 and continue through February 28, 2025, unless terminated earlier in accordance with Section 7.

3. PAYMENT
Client shall pay $15,000 per month, due within 15 days of invoice receipt.

4. GOVERNING LAW
This Agreement shall be governed by the laws of the State of Delaware.

5. TERMINATION
Either party may terminate this Agreement with 30 days written notice.

IN WITNESS WHEREOF, the parties have executed this Agreement as of the date first written above.`,

  receipt: `RECEIPT

Merchant: Blue Bottle Coffee
Date: April 22, 2024 10:32 AM
Location: 315 Linden St, San Francisco, CA

Items:
- Ethiopia Single Origin (12oz bag)   $22.00
- Cortado                              $5.50
- Almond Croissant                     $4.75

Subtotal: $32.25
Tax (8.75%): $2.82
Total: $35.07

Payment: Visa ending in 4242
Auth Code: 789012

Thank you for your purchase!`
}

export default function App() {
  const [dragOver, setDragOver] = useState(false)
  const [file, setFile] = useState(null)
  const [textMode, setTextMode] = useState(false)
  const [rawText, setRawText] = useState('')
  const [status, setStatus] = useState('idle')
  const [agentStatus, setAgentStatus] = useState({ a1: 'idle', a2: 'idle', a3: 'idle' })
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [llmProvider, setLlmProvider] = useState(null)
  const fileRef = useRef()

  const reset = () => {
    setStatus('idle')
    setResult(null)
    setError(null)
    setFile(null)
    setRawText('')
    setAgentStatus({ a1: 'idle', a2: 'idle', a3: 'idle' })
  }

  const simulateAgentProgress = async () => {
    setAgentStatus({ a1: 'running', a2: 'idle', a3: 'idle' })
    await new Promise(r => setTimeout(r, 800))
    setAgentStatus({ a1: 'done', a2: 'running', a3: 'idle' })
    await new Promise(r => setTimeout(r, 900))
    setAgentStatus({ a1: 'done', a2: 'done', a3: 'running' })
    await new Promise(r => setTimeout(r, 700))
    setAgentStatus({ a1: 'done', a2: 'done', a3: 'done' })
  }

  const runPipeline = useCallback(async () => {
    setStatus('processing')
    setError(null)
    setResult(null)

    const progressPromise = simulateAgentProgress()

    try {
      let resp
      if (textMode) {
        resp = await fetch(`${API}/process-text`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: rawText })
        })
      } else {
        const fd = new FormData()
        fd.append('file', file)
        resp = await fetch(`${API}/process`, { method: 'POST', body: fd })
      }

      await progressPromise

      if (!resp.ok) {
        const err = await resp.json()
        throw new Error(err.detail || 'Pipeline failed')
      }

      const data = await resp.json()
      setResult(data)
      setLlmProvider(data.llm_provider)
      setStatus('complete')
    } catch (e) {
      await progressPromise
      setError(e.message)
      setStatus('error')
    }
  }, [file, textMode, rawText])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files[0]
    if (f) { setFile(f); setTextMode(false); setResult(null); setError(null) }
  }, [])

  const classification = result?.pipeline?.agent1_classification
  const extraction = result?.pipeline?.agent2_extraction
  const validation = result?.pipeline?.agent3_validation

  const canRun = (textMode ? rawText.trim().length > 20 : !!file) && status !== 'processing'

  return (
    <div style={{
      minHeight: '100vh', background: '#0a0a0a', color: '#e8e8e8',
      fontFamily: 'Syne, sans-serif', padding: '40px 24px'
    }}>
      <style>{`
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
        @keyframes fadeIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: #111; }
        ::-webkit-scrollbar-thumb { background: #333; border-radius: 2px; }
      `}</style>

      <div style={{ maxWidth: 740, margin: '0 auto' }}>

        {/* Header */}
        <div style={{ marginBottom: 40 }}>
          <div style={{ fontSize: 10, letterSpacing: '0.2em', color: '#555', fontFamily: 'DM Mono, monospace', marginBottom: 8 }}>
            MULTI-AGENT AI SYSTEM
          </div>
          <h1 style={{ margin: 0, fontSize: 36, fontWeight: 800, letterSpacing: '-0.02em', lineHeight: 1.1 }}>
            Doc<span style={{ color: '#d4a017' }}>Pipeline</span>
          </h1>
          <p style={{ margin: '10px 0 0', color: '#666', fontSize: 13, fontFamily: 'DM Mono, monospace' }}>
            classify → extract → validate — three agents, one pipeline
          </p>
        </div>

        {/* LLM Badge */}
        {llmProvider && (
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            background: '#111', border: '1px solid #2a2a2a',
            borderRadius: 2, padding: '4px 10px', marginBottom: 20,
            fontSize: 10, fontFamily: 'DM Mono, monospace', color: '#888'
          }}>
            <span style={{ color: '#2d6a4f' }}>●</span> {llmProvider}
          </div>
        )}

        {/* Mode Toggle */}
        {status === 'idle' || status === 'error' ? (
          <>
            <div style={{ display: 'flex', gap: 0, marginBottom: 16 }}>
              {['Upload File', 'Paste Text'].map((label, i) => (
                <button key={i}
                  onClick={() => { setTextMode(i === 1); setFile(null); setRawText('') }}
                  style={{
                    flex: 1, padding: '9px 0', border: '1px solid #2a2a2a',
                    borderRight: i === 0 ? 'none' : '1px solid #2a2a2a',
                    background: (textMode ? i === 1 : i === 0) ? '#1a1a1a' : 'transparent',
                    color: (textMode ? i === 1 : i === 0) ? '#d4a017' : '#555',
                    fontFamily: 'DM Mono, monospace', fontSize: 11,
                    letterSpacing: '0.08em', textTransform: 'uppercase',
                    cursor: 'pointer', borderRadius: i === 0 ? '2px 0 0 2px' : '0 2px 2px 0',
                    transition: 'all 0.2s'
                  }}
                >
                  {label}
                </button>
              ))}
            </div>

            {!textMode ? (
              /* Drop Zone */
              <div
                onDragOver={e => { e.preventDefault(); setDragOver(true) }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileRef.current.click()}
                style={{
                  border: `1px dashed ${dragOver ? '#d4a017' : file ? '#2d6a4f' : '#333'}`,
                  borderRadius: 2, padding: '40px 24px', textAlign: 'center',
                  cursor: 'pointer', transition: 'all 0.25s', marginBottom: 16,
                  background: dragOver ? 'rgba(212,160,23,0.03)' : file ? 'rgba(45,106,79,0.04)' : 'transparent'
                }}
              >
                <input ref={fileRef} type="file" hidden accept=".txt,.pdf,.md,.csv,.json"
                  onChange={e => { const f = e.target.files[0]; if (f) { setFile(f); setResult(null); setError(null) } }} />
                <div style={{ fontSize: 28, marginBottom: 12 }}>
                  {file ? '📄' : '⬆'}
                </div>
                <div style={{ fontSize: 13, color: file ? '#e8e8e8' : '#666', marginBottom: 4, fontWeight: 600 }}>
                  {file ? file.name : 'Drop a document or click to upload'}
                </div>
                <div style={{ fontSize: 11, color: '#444', fontFamily: 'DM Mono, monospace' }}>
                  {file ? `${(file.size / 1024).toFixed(1)} KB` : '.txt · .pdf · .md · .csv · .json'}
                </div>
              </div>
            ) : (
              /* Text Input */
              <div style={{ marginBottom: 16 }}>
                <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 10, color: '#555', fontFamily: 'DM Mono, monospace', alignSelf: 'center', marginRight: 4 }}>
                    SAMPLES:
                  </span>
                  {Object.entries(SAMPLES).map(([type, text]) => (
                    <SampleDocButton key={type} label={type} text={text} onSelect={t => setRawText(t)} />
                  ))}
                </div>
                <textarea
                  value={rawText}
                  onChange={e => setRawText(e.target.value)}
                  placeholder="Paste document text here — invoice, contract, receipt, form, report, or letter..."
                  style={{
                    width: '100%', minHeight: 180, background: '#0d0d0d',
                    border: '1px solid #2a2a2a', borderRadius: 2,
                    color: '#e8e8e8', fontFamily: 'DM Mono, monospace', fontSize: 12,
                    lineHeight: 1.7, padding: '14px 16px', resize: 'vertical',
                    outline: 'none'
                  }}
                />
              </div>
            )}

            {error && (
              <div style={{
                padding: '12px 16px', background: 'rgba(192,57,43,0.08)',
                border: '1px solid #c0392b', borderRadius: 2, marginBottom: 16,
                fontSize: 12, color: '#e57373', fontFamily: 'DM Mono, monospace'
              }}>
                ✗ {error}
              </div>
            )}

            <button
              disabled={!canRun}
              onClick={runPipeline}
              style={{
                width: '100%', padding: '13px 0',
                background: canRun ? '#d4a017' : '#1a1a1a',
                border: `1px solid ${canRun ? '#d4a017' : '#2a2a2a'}`,
                color: canRun ? '#0a0a0a' : '#444',
                fontFamily: 'Syne, sans-serif', fontWeight: 700, fontSize: 13,
                letterSpacing: '0.08em', textTransform: 'uppercase',
                cursor: canRun ? 'pointer' : 'not-allowed', borderRadius: 2,
                transition: 'all 0.2s'
              }}
            >
              Run Pipeline →
            </button>
          </>
        ) : null}

        {/* Processing View */}
        {(status === 'processing' || status === 'complete') && (
          <div style={{ animation: 'fadeIn 0.3s ease' }}>

            {status === 'processing' && (
              <div style={{
                textAlign: 'center', padding: '24px 0 20px',
                fontSize: 11, letterSpacing: '0.15em', color: '#d4a017',
                fontFamily: 'DM Mono, monospace', textTransform: 'uppercase',
                animation: 'pulse 1.4s infinite'
              }}>
                ⟳  Processing document...
              </div>
            )}

            {/* Agent Steps */}
            <div style={{ marginBottom: 20 }}>
              <AgentStep number="01" name="Document Classifier"
                status={agentStatus.a1}
                data={result?.pipeline?.agent1_classification} />
              <AgentStep number="02" name="Field Extractor"
                status={agentStatus.a2}
                data={result?.pipeline?.agent2_extraction} />
              <AgentStep number="03" name="Business Rule Validator"
                status={agentStatus.a3}
                data={result?.pipeline?.agent3_validation} />
            </div>

            {/* Results */}
            {status === 'complete' && result && (
              <div style={{ animation: 'fadeIn 0.4s ease' }}>

                {/* Doc Type */}
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 14,
                  padding: '16px 20px',
                  background: '#0d0d0d', border: '1px solid #2a2a2a',
                  borderRadius: 2, marginBottom: 16
                }}>
                  <div style={{ fontSize: 32 }}>
                    {DOC_ICONS[classification?.doc_type] || '📄'}
                  </div>
                  <div>
                    <div style={{ fontSize: 10, letterSpacing: '0.15em', color: '#555', fontFamily: 'DM Mono, monospace', textTransform: 'uppercase' }}>
                      Document Type
                    </div>
                    <div style={{ fontSize: 20, fontWeight: 700, color: '#d4a017', letterSpacing: '-0.01em' }}>
                      {classification?.doc_type?.toUpperCase() || 'UNKNOWN'}
                    </div>
                    <div style={{ fontSize: 11, color: '#666', fontFamily: 'DM Mono, monospace' }}>
                      {(classification?.confidence * 100).toFixed(0)}% confidence · {result.processing_time_ms}ms
                    </div>
                  </div>
                </div>

                {/* Reasoning */}
                {classification?.reasoning && (
                  <div style={{
                    padding: '10px 14px', background: '#0d0d0d',
                    border: '1px solid #2a2a2a', borderRadius: 2,
                    fontSize: 11, color: '#888', fontFamily: 'DM Mono, monospace',
                    lineHeight: 1.6, marginBottom: 8
                  }}>
                    💬 {classification.reasoning}
                  </div>
                )}

                {/* Validation result */}
                <ValidationBadge validation={validation} />

                {/* Extracted Fields Summary */}
                {extraction && (
                  <div style={{ marginTop: 16 }}>
                    <div style={{
                      fontSize: 10, letterSpacing: '0.15em', color: '#555',
                      fontFamily: 'DM Mono, monospace', textTransform: 'uppercase',
                      marginBottom: 8
                    }}>
                      Extracted Fields
                    </div>
                    <div style={{
                      background: '#0d0d0d', border: '1px solid #2a2a2a',
                      borderRadius: 2, overflow: 'hidden'
                    }}>
                      {Object.entries(extraction).slice(0, 10).map(([k, v], i) => (
                        <div key={k} style={{
                          display: 'flex', gap: 12, padding: '9px 14px',
                          borderBottom: i < Object.entries(extraction).length - 1 ? '1px solid #1a1a1a' : 'none'
                        }}>
                          <div style={{
                            minWidth: 140, fontSize: 11, color: '#555',
                            fontFamily: 'DM Mono, monospace', flexShrink: 0
                          }}>
                            {k}
                          </div>
                          <div style={{
                            fontSize: 11, color: v ? '#c8e6c9' : '#444',
                            fontFamily: 'DM Mono, monospace', wordBreak: 'break-word'
                          }}>
                            {v === null ? 'null' : Array.isArray(v) ? `[${v.length} items]` : typeof v === 'object' ? JSON.stringify(v) : String(v)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div style={{ display: 'flex', gap: 8, marginTop: 20 }}>
                  <button
                    onClick={reset}
                    style={{
                      flex: 1, padding: '10px 0', background: 'transparent',
                      border: '1px solid #2a2a2a', color: '#888',
                      fontFamily: 'DM Mono, monospace', fontSize: 11,
                      letterSpacing: '0.08em', textTransform: 'uppercase',
                      cursor: 'pointer', borderRadius: 2, transition: 'all 0.2s'
                    }}
                    onMouseEnter={e => { e.target.style.borderColor = '#d4a017'; e.target.style.color = '#d4a017' }}
                    onMouseLeave={e => { e.target.style.borderColor = '#2a2a2a'; e.target.style.color = '#888' }}
                  >
                    ← New Document
                  </button>
                  <button
                    onClick={() => {
                      const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' })
                      const url = URL.createObjectURL(blob)
                      const a = document.createElement('a')
                      a.href = url; a.download = `pipeline-${result.job_id}.json`; a.click()
                    }}
                    style={{
                      flex: 1, padding: '10px 0', background: 'transparent',
                      border: '1px solid #2a2a2a', color: '#888',
                      fontFamily: 'DM Mono, monospace', fontSize: 11,
                      letterSpacing: '0.08em', textTransform: 'uppercase',
                      cursor: 'pointer', borderRadius: 2, transition: 'all 0.2s'
                    }}
                    onMouseEnter={e => { e.target.style.borderColor = '#2d6a4f'; e.target.style.color = '#2d6a4f' }}
                    onMouseLeave={e => { e.target.style.borderColor = '#2a2a2a'; e.target.style.color = '#888' }}
                  >
                    ↓ Export JSON
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Footer */}
        <div style={{
          marginTop: 48, paddingTop: 20, borderTop: '1px solid #1a1a1a',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center'
        }}>
          <div style={{ fontSize: 10, color: '#333', fontFamily: 'DM Mono, monospace' }}>
            AWS BEDROCK · LANGCHAIN · FASTAPI · REACT
          </div>
          <div style={{ fontSize: 10, color: '#333', fontFamily: 'DM Mono, monospace' }}>
            3-AGENT PIPELINE
          </div>
        </div>
      </div>
    </div>
  )
}
