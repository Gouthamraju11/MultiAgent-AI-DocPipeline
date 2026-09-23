const TYPES = {
  invoice: ['invoice', 'invoice number', 'total due', 'payment terms'],
  contract: ['agreement', 'party a', 'party b', 'governing law', 'termination'],
  receipt: ['receipt', 'merchant', 'subtotal', 'payment:'],
  form: ['form title', 'submission date', 'submitted by'],
  report: ['report', 'executive summary', 'key findings', 'recommendations'],
  letter: ['dear ', 'sincerely', 'subject:'],
  resume: ['resume', 'skills', 'experience', 'education'],
}

const SCHEMAS = {
  invoice: { vendor: null, invoice_number: null, date: null, due_date: null, total_amount: null, line_items: [], tax: null, payment_terms: null },
  contract: { parties: [], effective_date: null, expiration_date: null, governing_law: null, key_obligations: [], termination_clause: null },
  receipt: { merchant: null, date: null, items: [], subtotal: null, tax: null, total: null, payment_method: null },
  form: { form_title: null, fields: {}, submission_date: null, submitted_by: null },
  report: { title: null, author: null, date: null, summary: null, key_findings: [], recommendations: [] },
  letter: { sender: null, recipient: null, date: null, subject: null, body_summary: null },
  resume: { name: null, email: null, phone: null, location: null, summary: null, skills: [], experience: [], education: [], certifications: [], languages: [] },
  unknown: { raw_content: null, detected_fields: {} },
}

const REQUIRED = {
  invoice: ['vendor', 'invoice_number', 'total_amount'], contract: ['parties', 'effective_date'], receipt: ['merchant', 'total'], form: ['form_title'], report: ['title', 'key_findings'], letter: ['sender', 'recipient'], resume: ['name'], unknown: [],
}

function value(text, expression) {
  return text.match(expression)?.[1]?.trim().replace(/^[-–—:|\s]+|[-–—:|\s]+$/g, '') || null
}

function section(text, heading, stops = []) {
  const stop = stops.length ? stops.join('|') : '$'
  const result = text.match(new RegExp(`(?:^|\\n)\\s*${heading}\\s*:?\\s*\\n([\\s\\S]*?)(?=\\n\\s*(?:${stop})\\s*:?\\s*(?:\\n|$)|$)`, 'i'))?.[1]
  return result?.trim() || null
}

function linesOf(text) {
  return text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean)
}

function classify(text) {
  const lowered = text.toLowerCase()
  const ranked = Object.entries(TYPES).map(([type, signals]) => [type, signals.filter((signal) => lowered.includes(signal)).length]).sort((a, b) => b[1] - a[1])
  let [docType, count] = ranked[0]
  if (/[\w.+-]+@[\w.-]+\.\w+/.test(text) && lowered.includes('experience')) { docType = 'resume'; count += 2 }
  if (count < 2) docType = 'unknown'
  return { doc_type: docType, confidence: docType === 'unknown' ? 0.35 : Math.min(0.96, 0.64 + count * 0.07), reasoning: docType === 'unknown' ? 'No document type had enough matching structural signals.' : `Matched ${count} structural signals associated with ${docType} documents.` }
}

function extract(text, type) {
  const data = structuredClone(SCHEMAS[type])
  const lines = linesOf(text)
  if (type === 'invoice') Object.assign(data, {
    vendor: value(text, /^\s*(?:vendor|from)\s*:\s*(.+)$/im), invoice_number: value(text, /^\s*invoice\s*(?:number|no\.?|#)\s*:?\s*([^\n]+)$/im), date: value(text, /^\s*invoice\s*date\s*:\s*(.+)$/im), due_date: value(text, /^\s*due\s*date\s*:\s*(.+)$/im), total_amount: value(text, /^\s*(?:total\s*due|grand\s*total|total)\s*:\s*(.+)$/im), tax: value(text, /^\s*tax(?:\s*\([^)]*\))?\s*:\s*(.+)$/im), payment_terms: value(text, /^\s*payment\s*terms\s*:\s*(.+)$/im), line_items: lineItems(lines),
  })
  else if (type === 'receipt') Object.assign(data, { merchant: value(text, /^\s*merchant\s*:\s*(.+)$/im) || lines[0], date: value(text, /^\s*date\s*:\s*(.+)$/im), subtotal: value(text, /^\s*subtotal\s*:\s*(.+)$/im), tax: value(text, /^\s*tax\s*:\s*(.+)$/im), total: value(text, /^\s*total\s*:\s*(.+)$/im), payment_method: value(text, /^\s*payment\s*:\s*(.+)$/im), items: lineItems(lines) })
  else if (type === 'contract') Object.assign(data, { parties: [value(text, /^\s*party\s*a\s*:\s*(.+)$/im), value(text, /^\s*party\s*b\s*:\s*(.+)$/im)].filter(Boolean), effective_date: value(text, /^\s*effective\s*date\s*:\s*(.+)$/im), expiration_date: value(text, /^\s*expiration\s*date\s*:\s*(.+)$/im), governing_law: value(text, /^\s*governing\s*law\s*:\s*(.+)$/im), termination_clause: value(text, /^\s*termination\s*:\s*(.+)$/im), key_obligations: lines.filter((line) => /\b(shall|agrees? to|must)\b/i.test(line)).slice(0, 8) })
  else if (type === 'resume') Object.assign(data, { name: lines[0] || null, email: value(text, /\b([\w.+-]+@[\w.-]+\.\w+)\b/i), phone: value(text, /((?:\+?\d[\d\s().-]{7,}\d))\b/), location: lines.slice(0, 5).find((line) => /,\s*[A-Z]{2}\b/.test(line)) || null, summary: section(text, 'summary', ['skills', 'experience', 'education']), skills: (section(text, 'skills', ['experience', 'education', 'certifications']) || '').split(/[,|•\n]/).map((item) => item.trim()).filter(Boolean), experience: section(text, 'experience', ['education', 'certifications']) ? [{ text: section(text, 'experience', ['education', 'certifications']) }] : [], education: section(text, 'education', ['certifications']) ? [{ text: section(text, 'education', ['certifications']) }] : [] })
  else if (type === 'report') Object.assign(data, { title: value(text, /^\s*title\s*:\s*(.+)$/im) || lines[0], author: value(text, /^\s*author\s*:\s*(.+)$/im), date: value(text, /^\s*date\s*:\s*(.+)$/im), summary: section(text, 'executive summary', ['key findings', 'recommendations']), key_findings: bullets(section(text, 'key findings', ['recommendations'])), recommendations: bullets(section(text, 'recommendations')) })
  else if (type === 'letter') Object.assign(data, { sender: value(text, /^\s*from\s*:\s*(.+)$/im), recipient: value(text, /^\s*to\s*:\s*(.+)$/im) || value(text, /^\s*dear\s+([^,]+)/im), date: value(text, /^\s*date\s*:\s*(.+)$/im), subject: value(text, /^\s*subject\s*:\s*(.+)$/im), body_summary: lines.filter((line) => line.split(/\s+/).length >= 6).slice(0, 2).join(' ') || null })
  else if (type === 'form') {
    Object.assign(data, { form_title: value(text, /^\s*form\s*title\s*:\s*(.+)$/im) || lines[0], submission_date: value(text, /^\s*submission\s*date\s*:\s*(.+)$/im), submitted_by: value(text, /^\s*submitted\s*by\s*:\s*(.+)$/im) })
    for (const line of lines) { const [key, ...rest] = line.split(':'); if (rest.length && !/^(form title|submission date|submitted by)$/i.test(key)) data.fields[key.trim()] = rest.join(':').trim() }
  } else data.raw_content = text.slice(0, 4000)
  return data
}

function lineItems(lines) {
  return lines.flatMap((line) => { const match = line.match(/(\$\s*[\d,]+(?:\.\d{2})?)\s*$/); if (!match || /^(subtotal|total|tax|payment)/i.test(line)) return []; return [{ description: line.slice(0, match.index).replace(/^[-•\d.\s]+/, '').trim(), amount: match[1].replace(/\s/g, '') }] }).filter((item) => item.description).slice(0, 50)
}

function bullets(text) { return text ? text.split(/\n/).map((item) => item.replace(/^[-•]\s*/, '').trim()).filter(Boolean) : [] }

export function processInBrowser(text) {
  const started = performance.now()
  const classification = classify(text)
  const extracted = extract(text, classification.doc_type)
  const missing = REQUIRED[classification.doc_type].filter((key) => extracted[key] == null || extracted[key] === '' || (Array.isArray(extracted[key]) && !extracted[key].length) || (typeof extracted[key] === 'object' && !Array.isArray(extracted[key]) && !Object.keys(extracted[key]).length))
  const issues = missing.map((key) => `Required field is missing: ${key.replaceAll('_', ' ')}`)
  const unknown = classification.doc_type === 'unknown'
  return {
    job_id: crypto.randomUUID().replaceAll('-', '').slice(0, 12), status: 'complete', llm_provider: 'Browser demo (zero cost)',
    pipeline: { agent1_classification: classification, agent2_extraction: extracted, agent3_validation: { valid: !issues.length && !unknown, confidence: issues.length || unknown ? 0.35 : 0.9, issues, warnings: unknown ? ['Unknown document type; extracted content requires human review'] : [], human_review_required: Boolean(issues.length || unknown), review_reason: issues[0] || (unknown ? 'Unknown document type' : null) } },
    processing_time_ms: Math.max(1, Math.round(performance.now() - started)),
  }
}
