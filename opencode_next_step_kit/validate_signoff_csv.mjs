#!/usr/bin/env node
// validate_signoff_csv.mjs — zero-dependency Node validator for the 8 Signoff CSVs.
//
// WHY THIS EXISTS
//   opencode reported a "JavaScript-only runtime which does not support Python
//   imports", so it could WRITE files but could not RUN Createlee's Python
//   validator. That is why it declared "Task complete" without verifying.
//   Run this instead, from the folder that holds the 8 CSVs.
//
// USAGE
//   node validate_signoff_csv.mjs <folder> [--json]
//   exit 0 = ACCEPTABLE (0 failures), exit 1 = NOT ACCEPTABLE
//
// IMPORTANT
//   This checks STRUCTURE + CONTROL CONTENT against the v2 prompt spec.
//   Passing does NOT make simulated data real compliance evidence.
//   It never prints "ready for distribution" — only machine-checkable facts.

import fs from 'node:fs';
import path from 'node:path';

const SPEC = [
  { file: 'qa_reviews.csv',             header: ['ts','ai_action','human_action','reviewer_id','agent_id'] },
  { file: 'ai_audit_log.csv',           header: ['ts','actor','event_type'] },
  { file: 'ai_approvals.csv',           header: ['ts','gate','decision','approver_id'] },
  { file: 'escalations.csv',            header: ['ts','escalated_by','supervisor_id','authorised'] },
  { file: 'role_spec.csv',              header: ['ts','role','assigned_to','is_authorised_supervisor','named_accountable'] },
  // Signoff's documented ingest schema (src/signoff/ingest/csv_normaliser.py).
  // The previous columns (reference, term_or_version, owner) were rejected by
  // that consumer as unknown, which made this pack unloadable downstream.
  { file: 'ai_inventory.csv',           header: ['ts','row_type','provider_name','model_name','clause','signed_by','registered_by','policy_rule'] },
  { file: 'ai_training.csv',            header: ['ts','staff_id','module_name','completed'] },
  { file: 'incident_notifications.csv', header: ['ts','incident_id','notified_within_sla','owner'] },
];

const ALLOWED_MODULES = new Set([
  'Responsible AI','Prompt Safety','Data Privacy','Bias Detection',
  'Model Governance','Incident Response','PII Handling','Access Control',
]);
const ISO = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$/;
const WINDOW_START = '2026-08-08', WINDOW_END = '2026-11-06';

function parseCSV(text) {
  const rows = [];
  let row = [], field = '', inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') { field += '"'; i++; } else inQuotes = false;
      } else field += c;
    } else if (c === '"') inQuotes = true;
    else if (c === ',') { row.push(field); field = ''; }
    else if (c === '\n') { row.push(field); rows.push(row); row = []; field = ''; }
    else if (c !== '\r') field += c;
  }
  if (field.length || row.length) { row.push(field); rows.push(row); }
  return rows;
}

function col(rows, name) {
  const i = rows[0]?.indexOf(name) ?? -1;
  return i < 0 ? null : rows.slice(1).map(r => r[i] ?? '');
}

function checkFile(dir, spec) {
  const p = path.join(dir, spec.file);
  const out = { file: spec.file, status: 'FAIL', failures: [], findings: [], rows: 0,
                header_cols: 0, expected_cols: spec.header.length, width_mismatch_lines: [] };
  if (!fs.existsSync(p)) { out.failures.push('file missing'); return out; }

  const raw = fs.readFileSync(p);
  const text = raw.toString('utf8').replace(/^\uFEFF/, '');
  if (text.includes('\\n')) out.failures.push("literal '\\n' found (newline collapsed into header)");
  if (raw[0] === 0x50 && raw[1] === 0x4b) out.failures.push('XLSX binary saved as .csv');

  const rows = parseCSV(text);
  if (!rows.length) { out.failures.push('empty file'); return out; }
  out.header_cols = rows[0].length;
  out.rows = rows.length - 1;

  // R1 fixed width
  rows.slice(1).forEach((r, i) => { if (r.length !== rows[0].length) out.width_mismatch_lines.push(i + 2); });
  if (out.width_mismatch_lines.length) out.failures.push(`row-width mismatch on line(s) ${out.width_mismatch_lines.join(',')}`);
  if (out.rows < 1) out.failures.push('header-only file (0 data rows)');

  // exact header (aliases are a READ-side convenience; generation must be exact)
  const missing = spec.header.filter(h => !rows[0].includes(h));
  const exact = rows[0].length === spec.header.length && spec.header.every((h, i) => rows[0][i] === h);
  if (!exact) out.failures.push(`header mismatch — expected: ${spec.header.join(',')} | got: ${rows[0].join(',')}`);
  if (missing.length) out.failures.push(`missing required columns: ${missing.join(', ')}`);

  // timestamps
  const tsc = col(rows, 'ts');
  if (tsc) {
    const bad = tsc.filter(v => v && !ISO.test(v));
    if (bad.length) out.failures.push(`${bad.length} invalid ISO-8601 timestamp(s): ${bad.slice(0,3).join(', ')}`);
    const inWin = tsc.filter(v => v && v.slice(0,10) >= WINDOW_START && v.slice(0,10) <= WINDOW_END).length;
    out.coverage = tsc.length ? Math.round(1000 * inWin / tsc.length) / 10 : 0;
  } else out.coverage = 0;

  // per-file control checks (only when the column exists)
  switch (spec.file) {
    case 'ai_audit_log.csv': {
      const e = col(rows, 'event_type');
      if (e) {
        const groups = [
          ['kill_switch/access_revoked', e.some(v => ['kill_switch','access_revoked'].includes(v))],
          ['access_review', e.includes('access_review')],
          ['retention_check/pii_log_check', e.some(v => ['retention_check','pii_log_check'].includes(v))],
        ];
        groups.forEach(([n, ok]) => { if (!ok) out.failures.push(`missing audit event group: ${n}`); });
      }
      break;
    }
    case 'ai_approvals.csv': {
      const d = col(rows, 'decision'), a = col(rows, 'approver_id');
      if (d) {
        const n = d.filter(v => v === 'ai_proposed').length;
        if (!n) out.failures.push('0 rows with decision=ai_proposed');
        if (a) d.forEach((v,i) => { if (v === 'ai_proposed' && !a[i]) out.failures.push(`ai_proposed row ${i+2} has empty approver_id`); });
      }
      break;
    }
    case 'escalations.csv': {
      const a = col(rows, 'authorised');
      if (a) {
        const no = a.filter(v => v === 'no').length;
        if (no) out.findings.push(`${no} row(s) with authorised=no — honest control exception, keep it`);
        const bad = a.filter(v => !['yes','no'].includes(v));
        if (bad.length) out.failures.push(`authorised must be lowercase yes/no, got: ${[...new Set(bad)].join(', ')}`);
      }
      break;
    }
    case 'role_spec.csv': {
      const n = col(rows, 'named_accountable');
      if (n) {
        const yes = n.filter(v => v === 'yes').length;
        if (yes !== 1) out.failures.push(`expected exactly 1 named_accountable=yes, found ${yes}`);
      }
      break;
    }
    case 'ai_inventory.csv': {
      const t = col(rows, 'row_type'), pn = col(rows, 'provider_name'),
            model = col(rows, 'model_name'), clause = col(rows, 'clause'),
            signed = col(rows, 'signed_by'), registered = col(rows, 'registered_by');
      if (t) {
        if (!t.includes('provider')) out.failures.push('0 row_type=provider');
        if (!t.includes('contract_term')) out.failures.push('0 row_type=contract_term');
        if (pn && model && clause) {
          const contracted = new Set();
          t.forEach((v,i) => {
            if (v === 'contract_term') {
              if (clause[i] !== 'no_training') out.failures.push(`contract_term row ${i+2}: clause must be no_training (got '${clause[i]}')`);
              contracted.add(`${pn[i]}|${model[i]}`);
            }
            if (v === 'provider' && registered && !registered[i]) out.failures.push(`provider row ${i+2}: registered_by is empty`);
            if (v === 'contract_term' && signed && !signed[i]) out.failures.push(`contract_term row ${i+2}: signed_by is empty`);
          });
          t.forEach((v,i) => { if (v === 'provider' && !contracted.has(`${pn[i]}|${model[i]}`)) out.findings.push(`provider ${pn[i]} has no matching no-training contract term`); });
        }
      }
      break;
    }
    case 'ai_training.csv': {
      const c = col(rows, 'completed'), m = col(rows, 'module_name');
      if (c) {
        const bad = c.filter(v => !['yes','no'].includes(v));
        if (bad.length) out.failures.push(`completed must be lowercase yes/no, got: ${[...new Set(bad)].join(', ')}`);
        if (!c.includes('yes')) out.failures.push('0 rows with completed=yes');
        const no = c.filter(v => v === 'no').length;
        if (no) out.findings.push(`${no} training row(s) not completed — honest finding, keep it`);
      }
      if (m) {
        const bad = m.filter(v => !ALLOWED_MODULES.has(v));
        if (bad.length) out.failures.push(`module_name not in allowed list: ${[...new Set(bad)].join(', ')}`);
      }
      break;
    }
    case 'incident_notifications.csv': {
      const s = col(rows, 'notified_within_sla'), o = col(rows, 'owner');
      if (s) { const bad = s.filter(v => !['yes','no'].includes(v)); if (bad.length) out.failures.push('notified_within_sla must be lowercase yes/no'); }
      if (o && o.some(v => !v)) out.failures.push('empty owner field(s)');
      break;
    }
  }

  out.status = out.failures.length ? 'FAIL' : (out.findings.length ? 'PASS_WITH_FINDINGS' : 'PASS');
  return out;
}

const dir = process.argv[2] || '.';
const asJson = process.argv.includes('--json');
const results = SPEC.map(s => checkFile(dir, s));
const summary = {
  files_expected: SPEC.length,
  files_found: results.filter(r => r.rows > 0 || fs.existsSync(path.join(dir, r.file))).length,
  passed: results.filter(r => r.status === 'PASS').length,
  passed_with_findings: results.filter(r => r.status === 'PASS_WITH_FINDINGS').length,
  failed: results.filter(r => r.status === 'FAIL').length,
  total_rows_preserved: results.reduce((a, r) => a + r.rows, 0),
  width_clean: results.every(r => !r.width_mismatch_lines.length),
  rows_deleted: 0,
  verdict: results.every(r => r.status !== 'FAIL') ? 'ACCEPTABLE' : 'NOT ACCEPTABLE',
  note: 'Simulated data only. Passing is not real compliance evidence.',
};

if (asJson) {
  console.log(JSON.stringify({ summary, files: results }, null, 2));
} else {
  console.log(`Signoff CSV structure check — as-of ${WINDOW_END} (window ${WINDOW_START} .. ${WINDOW_END})`);
  console.log(`folder: ${path.resolve(dir)}\n`);
  for (const r of results) {
    console.log(`${r.file.padEnd(30)} ${r.status.padEnd(20)} rows=${String(r.rows).padStart(3)} `
      + `header=${r.header_cols}/${r.expected_cols} cov=${r.coverage ?? 0}% width_bad=${r.width_mismatch_lines.length}`);
    r.failures.forEach(f => console.log(`   FAIL: ${f}`));
    r.findings.forEach(f => console.log(`   FINDING: ${f}`));
  }
  console.log(`\n${JSON.stringify(summary)}`);
  console.log('\nRun Createlee for the full 5-format report:');
  console.log('  python3.11 evidence.py --out <folder> --as-of 2026-11-06 --validate-only');
}
process.exit(summary.verdict === 'ACCEPTABLE' ? 0 : 1);
