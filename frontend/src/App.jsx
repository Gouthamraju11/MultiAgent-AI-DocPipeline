import { useEffect, useMemo, useRef, useState } from 'react'
import './App.css'
import { processInBrowser } from './browserPipeline.js'

const API_BASE = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '')
const MAX_FILE_BYTES = 10 * 1024 * 1024
const SUPPORTED_EXTENSIONS = ['.txt', '.md', '.json', '.csv', '.pdf', '.docx']

const EXAMPLES = {
  invoice: `INVOICE\nVendor: Northstar Cloud Systems\nInvoice Number: NS-2048\nInvoice Date: 2026-09-18\nDue Date: 2026-10-18\n\nPlatform subscription  $750.00\nSupport package        $125.00\nTax: $70.00\nTotal Due: $945.00\nPayment Terms: Net 30`,
  contract: `SERVICE AGREEMENT\nParty A: Northstar Cloud Systems\nParty B: Meridian Labs\nEffective Date: September 18, 2026\nExpiration Date: September 18, 2027\nGoverning Law: California\n\nNorthstar shall provide managed infrastructure services. Meridian Labs agrees to pay all invoices within 30 days.\nTermination: Either party may terminate with 30 days written notice.`,
  resume: `Maya Chen\nSan Francisco, CA\nmaya.chen@example.com | +1 (415) 555-0182\n\nSUMMARY\nSoftware engineer focused on reliable AI platforms and developer infrastructure.\n\nSKILLS\nPython, FastAPI, React, PostgreSQL, AWS\n\nEXPERIENCE\nSenior Software Engineer, Northstar Labs — 2023–2026\nBuilt document intelligence systems and production APIs.\n\nEDUCATION\nB.S. Computer Science, State University — 2022`,
  report: `Q3 PLATFORM RELIABILITY REPORT\nAuthor: Site Reliability Team\nDate: 2026-09-20\n\nExecutive Summary\nAvailability improved while deployment lead time fell across all production services.\n\nKey Findings\n- API availability reached 99.98%\n- Median deployment time fell by 31%\n\nRecommendations\n- Expand automated rollback coverage\n- Add regional failure drills`,
}

const STAGES = [
  { number: '01', name: 'Classify', detail: 'Detect document type' },
  { number: '02', name: 'Extract', detail: 'Build structured data' },
  { number: '03', name: 'Validate', detail: 'Check quality & risk' },
]

function Icon({ name, size = 20 }) {
  const paths = {
    upload: <><path d="M12 16V4"/><path d="m7 9 5-5 5 5"/><path d="M20 15v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-4"/></>,
    file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M8 13h8M8 17h5"/></>,
    spark: <><path d="m12 3-1.6 4.4L6 9l4.4 1.6L12 15l1.6-4.4L18 9l-4.4-1.6L12 3Z"/><path d="m5 16-.8 2.2L2 19l2.2.8L5 22l.8-2.2L8 19l-2.2-.8L5 16ZM19 13l-.6 1.4L17 15l1.4.6L19 17l.6-1.4L21 15l-1.4-.6L19 13Z"/></>,
    check: <path d="m5 12 4 4L19 6"/>,
    alert: <><circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16h.01"/></>,
    download: <><path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/></>,
    close: <><path d="m6 6 12 12M18 6 6 18"/></>,
    github: <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3.3-.4 6.8-1.6 6.8-7.4A5.8 5.8 0 0 0 19.3 3 5.4 5.4 0 0 0 19.1 0S17.9-.4 15 1.5a13.4 13.4 0 0 0-7 0C5.1-.4 3.9 0 3.9 0a5.4 5.4 0 0 0-.2 3A5.8 5.8 0 0 0 2.2 7.1c0 5.8 3.5 7 6.8 7.4A4.8 4.8 0 0 0 8 18v4"/>,
    arrow: <><path d="M5 12h14M13 6l6 6-6 6"/></>,
  }
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>
}

function formatLabel(value) {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function formatValue(value) {
  if (value === null || value === undefined || value === '') return <span className="empty-value">Not detected</span>
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (Array.isArray(value)) {
    if (!value.length) return <span className="empty-value">None detected</span>
    return (
      <ul className="value-list">
        {value.map((item, index) => (
          <li key={`${JSON.stringify(item)}-${index}`}>{typeof item === 'object' ? Object.entries(item).map(([key, val]) => `${formatLabel(key)}: ${val}`).join(' · ') : String(item)}</li>
        ))}
      </ul>
    )
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value)
    if (!entries.length) return <span className="empty-value">None detected</span>
    return <div className="nested-value">{entries.map(([key, val]) => <span key={key}><strong>{formatLabel(key)}</strong>{String(val)}</span>)}</div>
  }
  return String(value)
}

async function apiRequest(path, options = {}) {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 90_000)
  try {
    const response = await fetch(`${API_BASE}${path}`, { ...options, signal: controller.signal })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(payload.detail || `Request failed with status ${response.status}`)
    return payload
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('The request timed out. Check the AI provider and try again.')
    throw error
  } finally {
    window.clearTimeout(timeout)
  }
}

function App() {
  const [mode, setMode] = useState('upload')
  const [file, setFile] = useState(null)
  const [text, setText] = useState('')
  const [dragging, setDragging] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [health, setHealth] = useState(null)
  const fileInput = useRef(null)

  useEffect(() => {
    apiRequest('/health').then(setHealth).catch(() => setHealth({ status: 'ok', mode: 'demo', llm_provider: 'Browser demo (zero cost)', browser: true }))
  }, [])

  const canProcess = mode === 'upload' ? Boolean(file) : text.trim().length >= 10
  const classification = result?.pipeline.agent1_classification
  const extracted = result?.pipeline.agent2_extraction
  const validation = result?.pipeline.agent3_validation
  const fieldCount = useMemo(() => extracted ? Object.values(extracted).filter((value) => value !== null && value !== '' && (!Array.isArray(value) || value.length) && (typeof value !== 'object' || Array.isArray(value) || Object.keys(value).length)).length : 0, [extracted])

  function acceptFile(candidate) {
    setError('')
    setResult(null)
    if (!candidate) return
    const extension = `.${candidate.name.split('.').pop()?.toLowerCase()}`
    if (!SUPPORTED_EXTENSIONS.includes(extension)) {
      setFile(null)
      setError(`Unsupported file type. Choose ${SUPPORTED_EXTENSIONS.join(', ')}.`)
      return
    }
    if (candidate.size > MAX_FILE_BYTES) {
      setFile(null)
      setError('That file is larger than the 10 MB upload limit.')
      return
    }
    setFile(candidate)
  }

  async function processDocument() {
    if (!canProcess || processing) return
    setProcessing(true)
    setError('')
    setResult(null)
    try {
      if (health?.browser) {
        let source = text
        if (mode === 'upload') {
          const extension = `.${file.name.split('.').pop()?.toLowerCase()}`
          if (!['.txt', '.md', '.json', '.csv'].includes(extension)) throw new Error('The free browser demo accepts TXT, MD, JSON, and CSV uploads. Run the local API for PDF or DOCX files.')
          source = await file.text()
        }
        if (source.trim().length < 10) throw new Error('Document must contain at least 10 readable characters.')
        setResult(processInBrowser(source))
      } else if (mode === 'upload') {
        const form = new FormData()
        form.append('file', file)
        setResult(await apiRequest('/process', { method: 'POST', body: form }))
      } else {
        setResult(await apiRequest('/process-text', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text }),
        }))
      }
    } catch (requestError) {
      setError(requestError.message || 'Something went wrong while processing the document.')
    } finally {
      setProcessing(false)
    }
  }

  function exportResult() {
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `docpipeline-${result.job_id}.json`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  function reset() {
    setFile(null)
    setText('')
    setResult(null)
    setError('')
    if (fileInput.current) fileInput.current.value = ''
  }

  return (
    <div className="app-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <nav className="topbar" aria-label="Main navigation">
        <a className="brand" href="#top" aria-label="DocPipeline home">
          <span className="brand-mark"><Icon name="spark" size={19} /></span>
          <span>Doc<span>Pipeline</span></span>
        </a>
        <div className="nav-meta">
          <span className={`status-dot ${health?.status === 'ok' ? 'online' : ''}`} />
          <span className="provider-name">{health ? health.llm_provider : 'Connecting…'}</span>
          <a className="github-link" href="https://github.com/Gouthamraju11/MultiAgent-AI-DocPipeline" target="_blank" rel="noreferrer" aria-label="View source on GitHub"><Icon name="github" size={18} /></a>
        </div>
      </nav>

      <main id="top">
        <section className="hero">
          <div className="eyebrow"><span>◆</span> Production-grade document intelligence</div>
          <h1>Raw documents in.<br /><em>Trusted data out.</em></h1>
          <p>A resilient three-stage pipeline that classifies documents, extracts structured fields, and validates every result before it reaches your systems.</p>
          <div className="hero-stats" aria-label="Product capabilities">
            <div><strong>7</strong><span>Document types</span></div>
            <div><strong>3</strong><span>Pipeline stages</span></div>
            <div><strong>6</strong><span>File formats</span></div>
          </div>
        </section>

        <section className="pipeline-map" aria-label="Processing pipeline">
          {STAGES.map((stage, index) => (
            <div className={`stage ${processing ? 'active' : result ? 'complete' : ''}`} key={stage.number}>
              <span className="stage-number">{result ? <Icon name="check" size={17} /> : stage.number}</span>
              <div><strong>{stage.name}</strong><span>{stage.detail}</span></div>
              {index < STAGES.length - 1 && <span className="stage-arrow"><Icon name="arrow" size={17} /></span>}
            </div>
          ))}
        </section>

        <section className="workspace-card">
          <div className="mode-switch" role="tablist" aria-label="Document input method">
            <button role="tab" aria-selected={mode === 'upload'} className={mode === 'upload' ? 'selected' : ''} onClick={() => { setMode('upload'); setError(''); setResult(null) }}><Icon name="upload" size={17} /> Upload file</button>
            <button role="tab" aria-selected={mode === 'text'} className={mode === 'text' ? 'selected' : ''} onClick={() => { setMode('text'); setError(''); setResult(null) }}><Icon name="file" size={17} /> Paste text</button>
          </div>

          {mode === 'upload' ? (
            <div
              className={`dropzone ${dragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`}
              onDragEnter={(event) => { event.preventDefault(); setDragging(true) }}
              onDragOver={(event) => event.preventDefault()}
              onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setDragging(false) }}
              onDrop={(event) => { event.preventDefault(); setDragging(false); acceptFile(event.dataTransfer.files[0]) }}
            >
              <input ref={fileInput} id="document-upload" type="file" accept={SUPPORTED_EXTENSIONS.join(',')} onChange={(event) => acceptFile(event.target.files[0])} />
              {file ? (
                <div className="selected-file">
                  <span className="file-icon"><Icon name="file" size={23} /></span>
                  <div><strong>{file.name}</strong><span>{(file.size / 1024).toFixed(1)} KB · Ready to process</span></div>
                  <button onClick={(event) => { event.preventDefault(); setFile(null); fileInput.current.value = '' }} aria-label="Remove file"><Icon name="close" size={18} /></button>
                </div>
              ) : (
                <label htmlFor="document-upload">
                  <span className="upload-icon"><Icon name="upload" size={27} /></span>
                  <strong>Drop a document here</strong>
                  <span>or click to browse your files</span>
                  <small>PDF, DOCX, TXT, MD, JSON, CSV · up to 10 MB</small>
                </label>
              )}
            </div>
          ) : (
            <div className="text-input-wrap">
              <textarea value={text} onChange={(event) => { setText(event.target.value); setResult(null); setError('') }} placeholder="Paste an invoice, contract, receipt, form, report, letter, or résumé…" aria-label="Document text" maxLength={200000} />
              <div className="text-footer">
                <div className="samples"><span>Try a sample:</span>{Object.keys(EXAMPLES).map((type) => <button key={type} onClick={() => setText(EXAMPLES[type])}>{type}</button>)}</div>
                <span>{text.length.toLocaleString()} / 200,000</span>
              </div>
            </div>
          )}

          {error && <div className="error-banner" role="alert"><Icon name="alert" size={18} /><span>{error}</span></div>}

          <button className="process-button" disabled={!canProcess || processing} onClick={processDocument}>
            {processing ? <><span className="spinner" /> Running intelligence pipeline…</> : <><Icon name="spark" size={19} /> Process document <Icon name="arrow" size={18} /></>}
          </button>
          {health?.mode === 'demo' && <p className="demo-note">Running in deterministic demo mode — no document content leaves your device and no paid API is used.</p>}
        </section>

        {result && (
          <section className="results" aria-live="polite">
            <div className="results-heading">
              <div><span className="section-kicker">Pipeline complete</span><h2>Structured result</h2></div>
              <div className="result-actions"><button onClick={reset}>New document</button><button className="export" onClick={exportResult}><Icon name="download" size={17} /> Export JSON</button></div>
            </div>

            <div className="result-summary">
              <div className="document-type"><span>Detected type</span><strong>{formatLabel(classification.doc_type)}</strong><small>{Math.round(classification.confidence * 100)}% confidence</small></div>
              <div className={`validation-state ${validation.valid ? 'valid' : 'invalid'}`}><span className="validation-icon"><Icon name={validation.valid ? 'check' : 'alert'} size={23} /></span><div><span>Validation</span><strong>{validation.valid ? 'Passed' : 'Needs attention'}</strong><small>{validation.human_review_required ? 'Human review recommended' : 'Ready for downstream use'}</small></div></div>
              <div className="summary-metric"><span>Fields captured</span><strong>{fieldCount}</strong><small>of {Object.keys(extracted).length} schema fields</small></div>
              <div className="summary-metric"><span>Processing time</span><strong>{result.processing_time_ms}<i>ms</i></strong><small>Job {result.job_id}</small></div>
            </div>

            <div className="result-grid">
              <article className="result-panel extracted-panel">
                <div className="panel-title"><div><span className="panel-index">02</span><div><h3>Extracted data</h3><p>Normalized fields ready for your application</p></div></div><span className="field-badge">{fieldCount} populated</span></div>
                <dl className="fields-grid">
                  {Object.entries(extracted).map(([key, value]) => <div className="field-row" key={key}><dt>{formatLabel(key)}</dt><dd>{formatValue(value)}</dd></div>)}
                </dl>
              </article>

              <div className="side-results">
                <article className="result-panel">
                  <div className="panel-title"><div><span className="panel-index">01</span><div><h3>Classification</h3><p>Why the pipeline chose this type</p></div></div></div>
                  <p className="reasoning">{classification.reasoning}</p>
                  <div className="confidence-track"><span style={{ width: `${classification.confidence * 100}%` }} /></div>
                </article>
                <article className="result-panel">
                  <div className="panel-title"><div><span className="panel-index">03</span><div><h3>Quality checks</h3><p>Deterministic and semantic validation</p></div></div></div>
                  {!validation.issues.length && !validation.warnings.length ? <div className="all-clear"><Icon name="check" size={18} /> All required checks passed</div> : (
                    <div className="issues-list">
                      {validation.issues.map((issue) => <div className="issue error" key={issue}><Icon name="alert" size={16} />{issue}</div>)}
                      {validation.warnings.map((warning) => <div className="issue warning" key={warning}><Icon name="alert" size={16} />{warning}</div>)}
                    </div>
                  )}
                </article>
              </div>
            </div>

            <details className="raw-result"><summary>Inspect raw API response <span>JSON</span></summary><pre>{JSON.stringify(result, null, 2)}</pre></details>
          </section>
        )}
      </main>

      <footer><span>DocPipeline v2.0</span><span>Built for reliable document automation</span>{health?.browser ? <a href="https://github.com/Gouthamraju11/MultiAgent-AI-DocPipeline" target="_blank" rel="noreferrer">View source <Icon name="arrow" size={14} /></a> : <a href={`${API_BASE}/docs`} target="_blank" rel="noreferrer">API docs <Icon name="arrow" size={14} /></a>}</footer>
    </div>
  )
}

export default App
