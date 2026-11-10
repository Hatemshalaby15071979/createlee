"""Createlee — small, dependable call-centre document generator.

Run:  python3.11 app.py   (then open http://127.0.0.1:7860)

Flow: upload -> analyse -> generate (STAGED ONLY) -> human reviews every
      document -> explicit approval -> save and/or email.

Nothing is written to outputs/ and nothing is emailed before approval.
"""
from __future__ import annotations

import csv
import json
import re
import secrets
import shutil
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

import config
import core
import constitution
import evidence
import handoff
import library
import agent
import llm
import mailer
import websearch

app = Flask(__name__, template_folder=str(config.TEMPLATE_DIR),
            static_folder=str(config.STATIC_DIR))
app.secret_key = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_MB * 1024 * 1024

SID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
STATE: dict[str, dict] = {}


# --------------------------------------------------------------------------- #
# Session persistence
# --------------------------------------------------------------------------- #
def sdir(sid: str) -> Path:
    return config.SESSION_DIR / sid


def state_path(sid: str) -> Path:
    return sdir(sid) / "state.json"


def new_state(sid: str) -> dict:
    return {
        "sid": sid,
        "created_at_iso8601": core.iso_now(),
        "uploads": [],
        "history": [],
        "staged": [],
        "outputs": [],
        "references": None,
        "options": {"include_timestamp": True},
        "email_prefill": {"to": config.DEFAULT_EMAIL_TO, "subject": "", "body": ""},
    }


def save_state(state: dict) -> None:
    p = state_path(state["sid"])
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, default=str), encoding="utf-8")
    tmp.replace(p)


def get_state(sid: str | None) -> dict:
    if sid and SID_RE.match(sid):
        if sid in STATE:
            return STATE[sid]
        p = state_path(sid)
        if p.is_file():
            try:
                STATE[sid] = json.loads(p.read_text(encoding="utf-8"))
                _repair_upload_paths(STATE[sid])
                return STATE[sid]
            except Exception:  # noqa: BLE001
                pass
    sid = "s" + secrets.token_hex(8)
    st = new_state(sid)
    (sdir(sid) / "uploads").mkdir(parents=True, exist_ok=True)
    STATE[sid] = st
    seed_samples(st)
    save_state(st)
    return st


def seed_samples(state: dict) -> None:
    """Bundle the two canonical CSVs + sample data so the platform works at once.
    Uploading a file with the same name replaces the bundled copy."""
    for p in sorted(config.SAMPLES_DIR.glob("*.csv")):
        add_upload(state, p, is_sample=True)


def add_upload(state: dict, src: Path, filename: str | None = None,
               is_sample: bool = False) -> dict:
    name = secure_filename(filename or src.name)
    dest = sdir(state["sid"]) / "uploads" / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    analysis = core.analyze_file(dest)
    entry = {"filename": name, "path": str(dest), "size_bytes": dest.stat().st_size,
             "is_sample": is_sample, "uploaded_at_iso8601": core.iso_now(),
             "analysis": analysis}
    state["uploads"] = [u for u in state["uploads"] if u["filename"] != name]
    state["uploads"].append(entry)
    return entry


def _repair_upload_paths(state: dict) -> bool:
    """Re-point upload paths that no longer exist (e.g. the project folder moved).

    state.json stores ABSOLUTE paths. When CreateLee was moved from
    Career/CreateLee/... into Career/cloned_repos/CreateLee/..., every existing
    session kept the old prefix and every read failed with FileNotFoundError —
    which the assistant then reported as "questions.csv is missing".
    Resolution is by filename inside the session's own uploads/ folder.
    """
    base = sdir(state["sid"]) / "uploads"
    changed = False
    for u in state.get("uploads", []):
        path = Path(u.get("path") or "")
        if path.is_file():
            continue
        candidate = base / u.get("filename", "")
        if candidate.is_file():
            u["path"] = str(candidate)
            try:
                u["size_bytes"] = candidate.stat().st_size
            except OSError:
                pass
            changed = True
    if changed:
        save_state(state)
    return changed


# --------------------------------------------------------------------------- #
# Constitution + local-model initialization (binding rules on every load)
# --------------------------------------------------------------------------- #
def initialize_constitution() -> dict:
    """Run once at app load.

    1. Loads CREATELEE_CONSTITUTION.md (binding rules).
    2. Probes the local Ollama server and binds the first available free model.
    3. Records the sign-in must-do entry: what changed + timestamp + which model.
    Never raises.
    """
    _ = constitution.load_constitution()  # raises nothing; absence is logged by constitution.py
    probe = llm.probe_ollama()
    result = llm.bind_model(source="startup")
    return {
        "constitution": str(constitution.CONSTITUTION_PATH),
        "constitution_loaded": constitution.CONSTITUTION_PATH.is_file(),
        "ollama": probe,
        "bound_model": result,
        "sign_in": constitution.last_sign_in(),
    }


def build_context(state: dict):
    ups = state["uploads"]
    qp = next((Path(u["path"]) for u in ups if u["filename"].lower() == "questions.csv"), None)
    mp = next((Path(u["path"]) for u in ups
               if u["filename"].lower() in ("mapping-table.template.csv", "mapping-table.csv")), None)
    if not qp or not mp:
        raise core.SchemaError(
            "Missing schema files. Upload questions.csv (canonical 11-column OR a "
            "Ref/Question/Yes/Partly/No checklist) and mapping-table.template.csv "
            "(source_field + target_field minimum), or use the bundled samples.")
    questions = core.load_questions(qp)
    mappings = core.load_mapping(mp)
    analyses = [u["analysis"] for u in ups]
    datasets = core.load_datasets([Path(u["path"]) for u in ups], analyses)
    return questions, mappings, datasets, analyses


def public_state(state: dict) -> dict:
    return {
        "sid": state["sid"],
        "created_at_iso8601": state["created_at_iso8601"],
        "uploads": [{
            "filename": u["filename"], "size_bytes": u["size_bytes"],
            "is_sample": u["is_sample"], "uploaded_at_iso8601": u["uploaded_at_iso8601"],
            "kind": u["analysis"].get("kind"), "rows": u["analysis"].get("rows", 0),
            "columns": u["analysis"].get("columns", []),
            "formats": {c["column"]: c["detected_format"]
                        for c in u["analysis"].get("column_report", [])},
            "error": u["analysis"].get("error"),
        } for u in state["uploads"]],
        "staged": [{
            "index": i, "domain": s["domain"], "document_type": s["document_type"],
            "title": s["title"], "formats": s["formats"],
            "document_id": s["doc"]["meta"]["document_id"],
            "generated_at_iso8601": s["doc"]["meta"]["generated_at_iso8601"],
            "review_status": s["doc"]["meta"]["review_status"],
            "preview": s["preview"],
        } for i, s in enumerate(state["staged"])],
        "outputs": state["outputs"][-60:],
        "history": state["history"][-80:],
        "email_prefill": state["email_prefill"],
        "references": ({"query": state["references"]["query"],
                        "count": state["references"]["count"]}
                       if state["references"] else None),
        "options": state["options"],
    }


def reply(state: dict, text: str, **extra) -> dict:
    msg = {"role": "engeznee", "text": text, "at_iso8601": core.iso_now(),
           "source": extra.get("agent_source"),
           "trace": extra.get("trace") or []}
    state["history"].append(msg)
    save_state(state)
    return {"ok": True, "reply": text, "at_iso8601": msg["at_iso8601"],
            "state": public_state(state), **extra}


# --------------------------------------------------------------------------- #
# Command parsing (deterministic — the LLM never owns this)
# --------------------------------------------------------------------------- #
DOMAIN_ALIASES = {
    "qa": "QA", "quality": "QA", "quality assurance": "QA", "scorecard": "QA",
    "wfm": "WFM", "workforce": "WFM", "schedule": "WFM", "roster": "WFM",
    "incident": "INCIDENT", "incidents": "INCIDENT", "outage": "INCIDENT", "pir": "INCIDENT",
    "training": "TRAINING", "course": "TRAINING", "learning": "TRAINING",
    "ai": "AI_INVENTORY", "inventory": "AI_INVENTORY", "ai inventory": "AI_INVENTORY",
    "sop": "SOP", "procedure": "SOP", "standard operating": "SOP",
    "kb": "KNOWLEDGE_BASE", "knowledge": "KNOWLEDGE_BASE", "article": "KNOWLEDGE_BASE",
}
FORMAT_ALIASES = {"csv": "csv", "pdf": "pdf", "txt": "txt", "text": "txt",
                  "json": "json", "docx": "docx", "doc": "docx", "word": "docx"}


def parse_generate(message: str, available: list[dict]) -> dict:
    low = " " + message.lower() + " "
    domains, formats, doc_types = [], [], []

    for alias, dom in DOMAIN_ALIASES.items():
        if re.search(r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])", low) and dom not in domains:
            domains.append(dom)
    for alias, fmt in FORMAT_ALIASES.items():
        if re.search(r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])", low) and fmt not in formats:
            formats.append(fmt)
    for d in available:
        if d["document_type"].lower() in low or d["document_type"].replace("_", " ") in low:
            if (d["domain"], d["document_type"]) not in doc_types:
                doc_types.append((d["domain"], d["document_type"]))

    if re.search(r"\b(all|everything|full pack|full set|each domain)\b", low) and not domains:
        domains = list(dict.fromkeys(d["domain"] for d in available))
    if not domains:
        domains = list(dict.fromkeys(d["domain"] for d in available))
    if not formats:
        formats = ["pdf", "csv"]
    if not doc_types:
        # Document types are defined by questions.csv. Mapping-only entries from a
        # previous schema are listed but not generated by default.
        with_criteria = [d for d in available
                         if d["domain"] in domains and d.get("criteria_count", 0) > 0]
        pool = with_criteria or [d for d in available if d["domain"] in domains]
        chosen = {(d["domain"], d["document_type"]) for d in pool}
    else:
        chosen = set(doc_types)
    include_ts = not bool(re.search(r"\b(no timestamp|without timestamp|no stamp|unstamped)\b", low))
    return {"domains": domains, "formats": formats,
            "doc_types": sorted(chosen), "include_timestamp": include_ts,
            "with_web": bool(re.search(r"\b(web|online|live data|real.?time sources?)\b", low))}


HELP_TEXT = """Engeznee — available commands

  analyze                     Analyse all uploaded files (rows, columns, number formats, ISO-8601/E.164 detection)
  list                        List every document type defined by your two CSV schemas
  status                      Show Ollama / cloud-model / email / web integration status
  web: <query>                Attach live public-web references (with URLs + ISO-8601 retrieval time)
  generate all                Stage every document type from the CSV schemas
  generate QA, WFM as pdf,csv Stage selected domains in selected formats
  generate qa_scorecard as json     Stage one specific document type
  generate incident_report as pdf no timestamp   Omit ISO-8601 from the filename
  preview                     Re-show the staged document previews
  clear                       Discard staged drafts (nothing is deleted from outputs/)
  save / email to x@y.com     Handled in the Review & Approve panel below
  evidence                    Build the 8-file Signoff evidence pack + validation report
  evidence --as-of 2026-11-06      Re-measure the 90-day window ending on that date
  evidence --as-of 2026-11-06 validate only   Validate YOUR real exports (read-only)
  library                     Build the reusable system-file library + validation report
  library --as-of 2026-11-06  Re-measure the library against a specific as-of date
  handoff                     Build ONE ready-to-send folder per production-NOT-ready project
  handoff --as-of 2026-11-06  Re-measure the hand-off packs against a specific as-of date

Formats: csv, txt, json, pdf, docx.   Domains: QA, WFM, INCIDENT, TRAINING, AI_INVENTORY, SOP, KNOWLEDGE_BASE, EVIDENCE, LIBRARY, HANDOFF.

The library task ingests your 6 real signoff files, writes a procedure corpus
(>=20 SOPs), expected-outcome labels (>=50 tickets), a system_a/system_b pair
reconciled by the id key, and a compact systems/ library for future requests.
It uses real published standards fetched from the web as reference grounding.

CONVERSATION
  Anything that is not one of the commands above goes to Engeznee as an
  executive-assistant agent. It keeps the conversation context, reasons over a
  goal, and calls tools: platform_status, list_documents, analyze_uploads,
  generate_documents, build_evidence, build_library, build_handoff,
  project_readiness, web_research, select_model, start_ollama.
  Pick the local Ollama model in the Settings panel; if Ollama is not running
  the app starts it for you. With no model reachable, Engeznee still answers
  from live platform state and labels the reply "offline".

The evidence task writes 8 exact-named CSVs (qa_reviews.csv, ai_audit_log.csv,
ai_approvals.csv, escalations.csv, role_spec.csv, ai_inventory.csv, ai_training.csv,
incident_notifications.csv) plus a validation report in all 5 formats. Required
columns are checked, column aliases and Excel-saved-as-.csv are auto-detected, and
gaps are preserved as honest findings — no row is ever deleted. No external
organisational approval is needed to produce the internal exports; the AI-authored
report is still staged for your own review before save/email.

questions.csv accepts EITHER the canonical 11-column schema OR a plain checklist
(Ref, Question, Yes, Partly, No). Checklist mode is auto-detected and produces a
fillable audit checklist. Optional extra columns: Domain, Document_Type, Section,
Weight, Owner, Evidence, Notes. Header names are case/space/underscore tolerant.

IMPORTANT: generation only STAGES drafts. Nothing is saved or emailed until you tick
"I have reviewed these documents" and press Approve & Execute."""


def stage_documents(state: dict, domains: list[str] | None, formats: list[str] | None,
                    doc_types: list[tuple] | None, include_timestamp: bool = True,
                    with_web: bool = False) -> tuple[bool, str, int]:
    """Stage document drafts. Shared by the command parser and the agent tools.

    Returns (ok, text, staged_count). Never saves to outputs/ and never emails.
    """
    questions, mappings, datasets, analyses = build_context(state)
    available = core.available_documents(questions, mappings)
    valid = {(d["domain"], d["document_type"]) for d in available}

    if doc_types:
        targets = [t for t in doc_types if t in valid]
    else:
        doms = {d for d in (domains or []) if d}
        targets = [(d["domain"], d["document_type"]) for d in available
                   if not doms or d["domain"] in doms]
    if not targets:
        return False, ("No matching document types for that request. "
                       "Type 'list' to see what your CSV schemas define."), 0

    formats = formats or ["pdf", "csv"]
    bad = [f for f in formats if f not in core.FORMATS]
    if bad:
        return False, (f"Unsupported format(s): {', '.join(bad)}. "
                       f"Allowed: {', '.join(core.FORMATS)}."), 0

    refs = None
    if with_web:
        default_query = ("telecom call centre operations standards ISO 8601 ITU-T E.164 "
                         + " ".join(sorted({d for d, _ in targets})[:2]))
        refs = websearch.reference_pack(
            state["references"]["query"] if state["references"] else default_query)
        state["references"] = refs

    state["options"]["include_timestamp"] = include_timestamp
    state["staged"] = []
    llm_note = ""
    for domain, doc_type in targets:
        doc = core.build_document(domain, doc_type, questions, mappings, datasets,
                                  analyses,
                                  options={"include_timestamp": include_timestamp},
                                  references=refs)
        if doc["sections"] and llm.status()["active"] != "none" and domain in ("SOP", "KNOWLEDGE_BASE"):
            original = doc["sections"][0].get("paragraphs", [])
            if original:
                polished, source = llm.polish(original[0], "Tighten this operational note for clarity.")
                if polished != original[0]:
                    doc["sections"][0]["paragraphs"][0] = polished
                    llm_note = f"Prose polishing: {source}"
        state["staged"].append({
            "domain": domain, "document_type": doc_type,
            "title": core.document_title(doc_type), "formats": formats,
            "doc": doc, "preview": core.render_preview(doc),
        })

    save_state(state)
    lines = [f"STAGED {len(state['staged'])} draft document(s) — NOTHING saved or emailed yet.",
             f"Staged at {core.iso_now()} (ISO-8601 UTC).",
             f"Requested formats: {', '.join(formats)}  |  "
             f"ISO-8601 in filename: {'yes' if include_timestamp else 'no'}", ""]
    for i, s in enumerate(state["staged"]):
        lines.append(f"  {i+1}. [{s['domain']}] {s['title']}  "
                     f"id={s['doc']['meta']['document_id']}  "
                     f"criteria/mappings={len(s['doc']['records'])} data row(s)")
    if refs:
        lines.append(f"\nLive web references attached: {refs['count']} (supplementary; verify before use).")
    if llm_note:
        lines.append(llm_note)
    lines += ["", "Next: open each preview in the Review & Approve panel, then tick "
              "'I have reviewed these documents' and choose Save / Email / Both."]
    return True, "\n".join(lines), len(state["staged"])


def analysis_text(state: dict) -> str:
    if not state["uploads"]:
        return "No files uploaded yet. Upload questions.csv, mapping-table.template.csv and your data files."
    lines = [f"Analysed {len(state['uploads'])} file(s) at {core.iso_now()} (ISO-8601 UTC):", ""]
    total_rows = 0
    for u in state["uploads"]:
        a = u["analysis"]
        rows = a.get("rows", 0)
        total_rows += rows if isinstance(rows, int) else 0
        lines.append(f"• {u['filename']}  [{a.get('kind')}]  {u['size_bytes']:,} B")
        if a.get("error"):
            lines.append(f"    ERROR: {a['error']}")
            continue
        lines.append(f"    rows={rows}  columns={len(a.get('columns', []))}")
        for c in a.get("column_report", [])[:12]:
            n = c.get("numeric")
            extra = (f"  numeric N={n['count']} sum={n['sum']} mean={n['mean']} "
                     f"min={n['min']} max={n['max']}") if n else ""
            lines.append(f"      - {c['column']}: {c['detected_format']}, "
                         f"non-empty={c['non_empty']}, distinct={c['distinct']}{extra}")
        if a.get("note"):
            lines.append(f"    note: {a['note']}")
        lines.append("")
    lines.append(f"Total tabular rows: {total_rows}")
    lines.append("Authoritative inputs are your uploaded CSVs. Web references, if used, are supplementary only.")
    return "\n".join(lines)


def status_text() -> str:
    s = llm.status()
    m = mailer.status()
    o = s["ollama"]
    lines = [
        f"Createlee {config.SCHEMA_VERSION} / Engeznee  |  server time {core.iso_now()}",
        "",
        f"Ollama (local): {'AVAILABLE' if o.get('available') else 'not reachable in this runtime'}",
    ]
    if o.get("available"):
        lines.append(f"  host={o['host']}  selected={o['selected']}  models={', '.join(o['models'][:8])}")
    else:
        lines.append(f"  host={o.get('host')}  reason={o.get('reason', 'no endpoint')}")
        lines.append("  -> Run Createlee on the machine where Ollama is installed; it is auto-detected at localhost:11434.")
    lines += [
        f"Cloud model:      {s['cloud']['model']} ({'configured' if s['cloud']['available'] else 'not configured'})",
        f"Active LLM:       {s['active']}   (LLM is optional; core generation is deterministic)",
        f"Email:            {m['mode']}  from={m['from']}  host={m['host']}:{m['port']}",
        f"                  -> No SMTP credentials = portable .eml draft, never a silent send.",
        f"Web enrichment:   {'enabled' if config.WEB_ENRICH else 'disabled'} (free DuckDuckGo Instant Answer + direct URL fetch)",
        f"Formats:          {', '.join(core.FORMATS)}",
        f"Time standard:    ISO-8601 / UTC",
    ]
    return "\n".join(lines)


def run_evidence(state: dict, as_of: str | None = None,
                 generate_examples: bool = True) -> dict:
    """Engeznee's 'evidence' task: build the 8-file Signoff pack + validation report.

    The 8 CSVs are internal operational exports (no external organisational
    approval needed to produce them). The AI-authored validation REPORT is still
    staged as a draft and goes through Createlee's own operator review gate
    before it can be saved/emailed.
    """
    as_of = as_of or evidence.default_as_of()
    # Fail early on a malformed date rather than deep inside the builder.
    import datetime as _dt
    _dt.date.fromisoformat(as_of)

    result = evidence.build_pack(config.EVIDENCE_DIR, as_of,
                                 generate_examples=generate_examples)
    report, doc = result["report"], result["report_doc"]
    s = report["summary"]

    # Stage ONLY the authored report for human review; the 8 CSV exports are
    # data dumps already written to the evidence folder.
    state["staged"] = [{
        "domain": "EVIDENCE", "document_type": "evidence_validation_report",
        "title": doc["meta"]["title"], "formats": list(evidence.REPORT_FORMATS),
        "doc": doc, "preview": core.render_preview(doc),
    }]
    state["options"]["include_timestamp"] = True
    save_state(state)

    lines = [
        f"EVIDENCE PACK built at {core.iso_now()} (ISO-8601 UTC).",
        f"As-of (--as-of): {report['as_of']}  |  90-day window: {report['window_start']} .. {report['window_end']}",
        f"Files found: {s['files_found']}/{s['files_expected']}  |  "
        f"PASS={s['passed']}  PASS_WITH_FINDINGS={s['passed_with_findings']}  FAIL={s['failed']}",
        f"Rows preserved: {s['total_rows_preserved']}  |  Gaps reported: {s['total_gaps_reported']}  |  "
        f"Rows deleted: {s['rows_deleted']} (never delete rows to look clean)",
        f"Folder: {result['out_dir']}", "",
        "Per-file status:",
    ]
    for f in report["files"]:
        lines.append(f"  #{f['n']} {(f['filename'] or f['expected_filename']):<30} {f['status']:<20} "
                     f"rows={f['total_rows']:>3} in-window={f['in_window_rows']:>3} "
                     f"out={f['out_of_window_rows']} cov={f['coverage_pct']}% findings={len(f['gaps'])}")
        lines.append(f"      required columns: {', '.join(f['required_columns'])}")
    lines += [
        "",
        "Required columns are checked; column aliases and Excel-saved-as-.csv "
        "(BOM / UTF-16 / ';' / TAB) are auto-detected. Gaps are preserved as honest findings.",
        "",
        "Approvals: no external organisational approval is required for these internal "
        "operational exports. Createlee's own operator review gate still applies to the "
        "AI-authored report -> it is STAGED as a draft in the Review & Approve panel. "
        "Nothing has been emailed.",
        "",
        "Say 'evidence --as-of YYYY-MM-DD' to re-measure, or "
        "'evidence --as-of YYYY-MM-DD validate only' to check your real exports without rewriting them.",
        "",
        "HONESTY: these 8 CSVs are SYNTHETIC format/coverage fixtures generated from "
        "Createlee's bundled sample data, NOT real compliance evidence. Replace them with "
        "genuine QA / WFM / incident / training / AI-inventory exports before any real signoff.",
    ]
    return {"ok": True, "result": result, "text": "\n".join(lines)}


def run_library(state: dict, as_of: str | None = None) -> dict:
    """Engeznee's 'library' task: build the reusable system-file library.

    Generates the procedure corpus, expected-outcome labels, the system_a /
    system_b reconciliation pair, the broad systems/ library, ingests the 6 real
    uploaded signoff files and copies the 8 evidence CSVs. The AI-authored build
    report is STAGED as a draft for the operator review gate; nothing is emailed.
    """
    import datetime as _dt
    as_of = as_of or evidence.default_as_of()
    _dt.date.fromisoformat(as_of)  # fail early on a malformed date

    result = library.build_library(config.LIBRARY_DIR, as_of)
    doc, m = result["report_doc"], result["manifest"]
    rc, rec = result["row_counts"], result["reconciliation"]

    state["staged"] = [{
        "domain": "LIBRARY", "document_type": "build_report",
        "title": doc["meta"]["title"], "formats": ["csv", "txt", "json", "pdf", "docx"],
        "doc": doc, "preview": core.render_preview(doc, max_table_rows=40),
    }]
    state["options"]["include_timestamp"] = True
    save_state(state)

    lines = [
        f"SYSTEM LIBRARY built at {core.iso_now()} (ISO-8601 UTC).",
        f"As-of (--as-of): {result['as_of']}  |  Files written: {m['file_count']}",
        f"Folder: {result['out_dir']}", "",
        "Requirement coverage:",
    ]
    for i, c in enumerate(result["coverage_rows"], 1):
        lines.append(f"  {i:>2}. [{c[4]}] {c[1]} -> {c[3]}")
    lines += [
        "",
        f"Corpus: {rc['corpus']} procedures ({rc['corpus_published_active']} published/active, "
        f"{rc['corpus_draft_or_retired']} draft/retired)  |  Labels: {rc['labels']} tickets "
        f"({rc['labels_answer']} answer / {rc['labels_escalate']} escalate)",
        f"Reconciliation: {rec['fully_reconciled']}/{rec['keys_total']} keys fully reconciled; "
        f"A-only={rec['a_only']} B-only={rec['b_only']} field-mismatches={rec['field_mismatches']}; "
        f"rows deleted={rec['rows_deleted']}",
        f"Web references: {len(m['web_references'])} real published standards with ISO-8601 retrieval time.",
        f"Honest findings preserved: {len(result['findings'])} (see report / README).", "",
        "Folders: uploaded/ (6 REAL files, XLSX-as-.csv decoded, rows preserved), evidence/ "
        "(8 exact-named Signoff CSVs), systems/ (compact reusable library) + root deliverables.", "",
        "Approvals: no external organisational approval needed for these internal exports; "
        "Createlee's own operator review gate still applies to the AI-authored report, which is "
        "STAGED as a draft. Nothing has been emailed.", "",
        "HONESTY: web sources are real public standards used as reference grounding, NOT customer "
        "data. All operational rows are simulated; replace them with genuine exports before any "
        "real signoff. The 6 uploaded/ files are your actual records, preserved row-for-row.", "",
        "Say 'library --as-of YYYY-MM-DD' to re-measure, or type 'help' for all commands.",
    ]
    return {"ok": True, "result": result, "text": "\n".join(lines)}


def run_handoff(state: dict, as_of: str | None = None) -> dict:
    """Engeznee's 'handoff' task: build one ready-to-send folder per project.

    Produces the exact file set each production-NOT-ready project needs, with a
    REQUEST_LIST.md, CLIENT-INSTRUCTIONS.md and request_manifest.json per
    project. The client replaces only the data rows; the header, column order
    and value conventions stay byte-identical so Signoff can consume the
    returned files without reformatting.

    The generated files are SIMULATED. The manifest names, per project, what
    Createlee cannot generate (org-only evidence) so those gates stay honestly
    open. Nothing is emailed here.
    """
    import datetime as _dt
    as_of = as_of or evidence.default_as_of()
    _dt.date.fromisoformat(as_of)  # fail early on a malformed date

    result = handoff.build_all(config.HANDOFF_DIR, as_of)
    save_state(state)

    lines = [
        f"HAND-OFF PACKS built at {core.iso_now()} (ISO-8601 UTC).",
        f"As-of (--as-of): {result['as_of']}  |  Files written: {result['files_written']}",
        f"Folder: {result['out_dir']}", "",
        "One folder per project — send the folder, get the rows back, run Signoff:",
    ]
    for m in result["projects"]:
        gen = sum(1 for f in m["files"] if f.get("client_action", "").startswith("replace")
                  or f.get("client_action") == "owner_completes_and_signs")
        lines.append(f"  • {m['project']:<24} {len(m['files'])} file(s), {gen} client-fillable, "
                     f"{len(m.get('cannot_generate', []))} org-only item(s)")
    lines += [
        "",
        "Each project folder contains REQUEST_LIST.md, CLIENT-INSTRUCTIONS.md and",
        "request_manifest.json. The cross-project list is REQUESTED-FILES-BY-PROJECT.md.",
        "",
        "Client rule: replace ONLY the data rows. Keep the header, column order, exact",
        "filename and lowercase yes/no. Never delete a row to hide a gap.",
        "",
        "Approvals: nothing is emailed. The generated files are SIMULATED and the",
        "manifest names what cannot be generated (certification, external audit,",
        "architecture/DR/security/legal review, hosted CI, TLS, anchor receipts).",
    ]
    return {"ok": True, "result": result, "text": "\n".join(lines)}


# --------------------------------------------------------------------------- #
# Client package — the FULL simulated-inputs set for the third party
# --------------------------------------------------------------------------- #
def _collect_handoff_files() -> list[dict]:
    """List every file under the hand-off dir, with rel path and size."""
    hd = config.HANDOFF_DIR
    files = []
    if not hd.is_dir():
        return files
    for p in sorted(hd.rglob("*")):
        if not p.is_file():
            continue
        files.append({
            "name": p.name,
            "rel": p.relative_to(hd).as_posix(),
            "path": str(p),
            "size_bytes": p.stat().st_size,
        })
    return files


def build_client_package(st: dict, as_of: str | None = None) -> dict:
    """Build (or rebuild) the full per-project simulated-inputs package into the
    hand-off dir and store it in the session so it can be emailed in full.

    Covers all four projects: signoff (8 evidence CSVs), helix-codex (9 gate
    templates + 2 ownership CSVs), live-support-assistant (corpus + labels) and
    compliproof (2 reconciled exports + P0 checklist), plus the step-by-step
    CLIENT-INSTRUCTIONS.md and REQUESTED-FILES-BY-PROJECT.md cover letters.
    """
    h = run_handoff(st, as_of)
    files = _collect_handoff_files()
    cover = config.HANDOFF_DIR / "CLIENT-INSTRUCTIONS.md"
    overview = config.HANDOFF_DIR / "REQUESTED-FILES-BY-PROJECT.md"
    pkg = {
        "as_of": h["result"]["as_of"],
        "built_at_iso8601": core.iso_now(),
        "files": files,
        "cover_md": str(cover) if cover.is_file() else None,
        "overview": str(overview) if overview.is_file() else None,
        "files_written": h["result"]["files_written"],
        "projects": h["result"]["projects"],
    }
    st["client_package"] = pkg
    save_state(st)
    return {"ok": True, "client_package": pkg, "handoff": h["text"]}


def client_package_email_body(pkg: dict) -> str:
    """Step-by-step cover letter + instructions + attachment list for the third
    party. They read the MD, open file by file, replace only their rows, send back."""
    lines = [
        "Createlee / Engeznee — simulated inputs for your modifications",
        "================================================================",
        "",
        "Hello,",
        "",
        "Attached is the complete set of simulated, format-exact input files Createlee "
        "generated for your four projects (Signoff, Helix-Codex, live-support-assistant, "
        "CompliProof).",
        "",
        "WHAT YOU NEED TO DO — step by step",
        "------------------------------------",
        "1. Read the attached CLIENT-INSTRUCTIONS.md first. It applies to every file.",
        "2. Open each attached CSV / JSON file and replace ONLY the data rows with your "
        "own real rows.",
        "3. Keep every header, column order, filename and value convention byte-for-byte "
        "identical. Do not add, remove or rename columns or files.",
        "4. Use lowercase yes / no for booleans and ISO-8601 timestamps with timezone.",
        "5. Do not delete rows to hide a gap — gaps are reported honestly.",
        "6. When every file is filled, email the files back to us.",
        "7. We will run Signoff against the returned files and unblock production "
        "readiness for Helix-Codex, live-support-assistant and CompliProof.",
        "",
        "Some gates are organisational (external audit, certification, security review, "
        "legal/privacy review) and cannot be closed by CSV files alone; those are listed "
        "per project and will stay open until the signed document exists.",
        "",
        "FILES ATTACHED",
        "----------------",
    ]
    for f in (pkg.get("files") or []):
        lines.append(f"  • {f['rel']}  ({f['size_bytes']:,} bytes)")
    lines += [
        "",
        f"Total attachments: {len(pkg.get('files') or [])}",
        f"Package built (ISO-8601 UTC): {pkg.get('built_at_iso8601')}   as-of: {pkg.get('as_of')}",
        "",
        "Full per-project detail: see REQUESTED-FILES-BY-PROJECT.md (attached).",
        "Step-by-step rules: see CLIENT-INSTRUCTIONS.md (attached).",
        "",
        "Generated by Createlee / Engeznee — simulated template data, not real evidence.",
        "Replace the simulated rows with your real exports before Signoff.",
    ]
    cover = pkg.get("cover_md")
    if cover and Path(cover).is_file():
        lines += ["", "=" * 60, "ATTACHED: CLIENT-INSTRUCTIONS.md (full rules)", "=" * 60, ""]
        lines.append(Path(cover).read_text(encoding="utf-8"))
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Agent tools — the executive assistant's hands
# --------------------------------------------------------------------------- #
def _project_readiness_text() -> str:
    """Honest readiness of the four projects, with live hand-off counts."""
    lines = ["Production readiness — four projects", ""]
    lines.append("• Signoff (the gate): locally shipment-ready. It turns the client's 8 CSVs "
                 "into a verdict pack. Open: no real client data yet, and Signoff does not "
                 "authenticate source records.")
    lines.append("• Helix-Codex: 9 production gates. 6 need signed organisational evidence — "
                 "isolation certification, external audit, architecture review, DR test, "
                 "security review and legal/privacy review. All 6 stay OPEN.")
    lines.append("• live-support-assistant: corpus + labels are supplied (24 procedures, 64 "
                 "labels). Open: tenant isolation, authenticated transport, hosted telemetry, "
                 "external audit, billing.")
    lines.append("• CompliProof: 7 open P0 gates, 0 closed. None closable by CSV — needs hosted "
                 "CI, clean-install matrix, Docker, vulnerability scan, external anchor receipt "
                 "and an independent key lifecycle.")
    mf = config.HANDOFF_DIR / "handoff_manifest.json"
    if mf.is_file():
        try:
            m = json.loads(mf.read_text(encoding="utf-8"))
            lines += ["", f"Hand-off packs were built at {m.get('generated_at_iso8601', '?')} "
                          f"({m.get('files_written', '?')} files). Send them to the client; "
                          "they replace only the data rows."]
        except Exception:  # noqa: BLE001
            pass
    else:
        lines += ["", "Hand-off packs are not built yet. Say 'build the hand-off packs'."]
    return "\n".join(lines)


def _handoff_summary_text() -> str:
    mf = config.HANDOFF_DIR / "handoff_manifest.json"
    if not mf.is_file():
        return ("Hand-off packs are not built yet. Say 'build the hand-off packs' and I will "
                "generate one folder per project.")
    try:
        m = json.loads(mf.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return "The hand-off manifest is unreadable. Rebuild the packs."
    lines = [f"Hand-off packs — {m.get('files_written', '?')} files, as-of {m.get('as_of', '?')}."]
    for p in m.get("projects", []):
        gen = sum(1 for f in p.get("files", [])
                  if str(f.get("client_action", "")).startswith("replace"))
        lines.append(f"• {p['project']}: {len(p.get('files', []))} files, {gen} client-fillable, "
                     f"{len(p.get('cannot_generate', []))} org-only")
    lines += ["", f"Open {m.get('overview', 'REQUESTED-FILES-BY-PROJECT.md')} for the full list."]
    return "\n".join(lines)


def _evidence_summary_text() -> str:
    sp = config.EVIDENCE_DIR / "VALIDATION_STRICT.json"
    if not sp.is_file():
        return "The evidence pack has not been built yet. Say 'build the evidence pack'."
    try:
        s = json.loads(sp.read_text(encoding="utf-8"))["summary"]
    except Exception:  # noqa: BLE001
        return "The evidence validation report is unreadable. Rebuild the pack."
    return (f"Signoff evidence pack: {s['files_found']}/8 files, strict verdict "
            f"{s['verdict']} ({s['failed']} failures, {s['passed']} PASS, "
            f"{s['passed_with_findings']} with findings, {s['total_rows_preserved']} rows). "
            f"Folder: {config.EVIDENCE_DIR}")


def _model_summary_text() -> str:
    st = llm.status()
    o = st["ollama"]
    if o["available"]:
        return (f"Local model: {o['selected']}. Ollama is up at {o['host']} with "
                f"{len(o['models'])} model(s): {', '.join(o['models'])}.")
    detail = o.get("last_start", {}).get("detail", "")
    return ("No local model is reachable. Ollama binary: "
            f"{o.get('binary') or 'not found'}. Last start: {detail or 'not attempted'}. "
            "Use Settings → Start Ollama, or pick a model once it is up.")


def _uploads_context(state: dict) -> str:
    """Authoritative presence of the files the platform needs.

    The agent once told the operator questions.csv was missing while it sat in
    the session folder — it guessed instead of checking. This string is injected
    into the system prompt and exposed as the list_uploads tool so a missing-file
    claim can only come from a real measurement.
    """
    req = ("questions.csv", "mapping-table.template.csv")
    ups = {u["filename"]: u for u in state.get("uploads", [])}
    missing = [n for n in req if n not in ups]
    lines = [f"Session uploads ({len(ups)} file(s)):"]
    for name in sorted(ups):
        u = ups[name]
        rows = (u.get("analysis") or {}).get("rows", "?")
        lines.append(f"  • {name} — {u.get('size_bytes', '?')} bytes, {rows} rows")
    if missing:
        lines.append("MISSING REQUIRED FILE(S): " + ", ".join(missing))
    else:
        lines.append("Required files PRESENT: questions.csv = yes, "
                     "mapping-table.template.csv = yes.")
    return "\n".join(lines)


def _runtime_context_text(state: dict) -> str:
    """Authoritative facts injected into the agent's system prompt.

    Without this the model answers from stale memory — it once claimed to be
    running 'llama3.1:8b' while qwen3:8b was loaded, and described CompliProof's
    hosted-CI gate as a signature problem. Grounding removes that class of error.
    """
    st = llm.status()
    o = st["ollama"]
    lines = [
        f"Local model in use: {o['selected'] or 'none'} "
        f"(ollama available={o['available']}, host={o['host']})",
        f"Installed models: {', '.join(o['models']) or 'none'}",
        f"Email: configured={mailer.status()['configured']} "
        f"mode={mailer.status()['mode']} from={config.SMTP_FROM or '(unset)'} "
        f"host={config.SMTP_HOST or '(unset)'}:{config.SMTP_PORT} security={config.SMTP_SECURITY}",
        "Real email settings are exactly: CREATELEE_SMTP_HOST, CREATELEE_SMTP_PORT, "
        "CREATELEE_SMTP_SECURITY, CREATELEE_SMTP_USER, CREATELEE_SMTP_PASSWORD, "
        "CREATELEE_SMTP_FROM. There is NO CREATELEE_EMAIL variable. Gmail needs an App "
        "Password (16 chars) with 2-Step Verification on; a normal account password "
        "always fails with 535 5.7.8. If sending is not configured or a send failed, say "
        "so plainly and point to .env — never invent setting names.",
        f"Staged drafts: {len(state['staged'])}",
        "",
        "UPLOADS (authoritative — never claim a file is missing unless this says so):",
        _uploads_context(state),
        "",
        "Project facts (authoritative — do not contradict these):",
        "• Signoff: the gate. Consumes the client's 8 CSV exports and produces a "
        "verdict pack. Status: no real client data received yet.",
        "• Helix-Codex: 9 production gates. 6 need signed organisational evidence "
        "(isolation certification, external audit, architecture review, DR test, "
        "security review, legal/privacy review). 3 can use client data: the signed "
        "evidence pack, operational ownership, incident/on-call ownership.",
        "• live-support-assistant: needs a procedure corpus >=20 and labels >=50 "
        "(Createlee supplies 24 and 64). Still open: tenant isolation, authenticated "
        "transport, hosted telemetry, external audit, billing, threshold calibration.",
        "• CompliProof: 7 P0 gates open, 0 closed. None is closable by CSV. "
        "P0-1 packaging/deployment needs a hosted CI run, a clean-install matrix and "
        "a Docker build (this is a CI artifact, NOT a signature). P0-2 needs an "
        "independent signature/key lifecycle. P0-3 needs an external timestamp "
        "anchor receipt. P0-4 needs served-report artifacts and report audit events. "
        "P0-5 needs authenticated routes and a security scan. P0-6 needs auth "
        "hardening (Argon2id/bcrypt, sessions, RBAC, MFA, lockout). P0-7 needs "
        "browser acceptance and a login surface.",
    ]
    mf = config.HANDOFF_DIR / "handoff_manifest.json"
    if mf.is_file():
        try:
            m = json.loads(mf.read_text(encoding="utf-8"))
            lines.append(f"Hand-off packs: built {m.get('generated_at_iso8601', '?')} "
                         f"({m.get('files_written', '?')} files) in {config.HANDOFF_DIR}.")
        except Exception:  # noqa: BLE001
            lines.append("Hand-off packs: manifest unreadable.")
    else:
        lines.append("Hand-off packs: NOT built yet.")
    return "\n".join(lines)


def agent_ops(state: dict) -> dict:
    """The tool implementations the agent can call. Read-mostly by design."""

    def platform_status():
        return {"ok": True, "summary": status_text()}

    def list_documents():
        q, m, _ds, _an = build_context(state)
        docs = core.available_documents(q, m)
        lines = [f"{len(docs)} document type(s) defined:"]
        for d in docs:
            lines.append(f"• [{d['domain']}] {d['document_type']} — {core.document_title(d['document_type'])} "
                         f"({d['criteria_count']} criteria)")
        return {"ok": True, "summary": "\n".join(lines), "documents": docs}

    def analyze_uploads():
        return {"ok": True, "summary": analysis_text(state)}

    def list_uploads():
        return {"ok": True, "summary": _uploads_context(state)}

    def generate_documents(domains=None, formats=None, document_types=None):
        q, m, _ds, _an = build_context(state)
        docs = core.available_documents(q, m)
        types = []
        if document_types:
            wanted = {str(x).lower() for x in document_types}
            types = [(d["domain"], d["document_type"]) for d in docs
                     if d["document_type"].lower() in wanted]
        ok, text, count = stage_documents(state, domains, formats, types or None)
        return {"ok": ok, "summary": text, "staged": count}

    def build_evidence(as_of=None):
        r = run_evidence(state, as_of)
        return {"ok": True, "summary": r["text"]}

    def build_library(as_of=None):
        r = run_library(state, as_of)
        return {"ok": True, "summary": r["text"]}

    def build_handoff(as_of=None):
        r = run_handoff(state, as_of)
        return {"ok": True, "summary": r["text"]}

    def project_readiness():
        return {"ok": True, "summary": _project_readiness_text()}

    def web_research(query=""):
        pack = websearch.reference_pack(str(query or "operations standards"))
        state["references"] = pack
        lines = [f"{pack['count']} reference(s) for {query!r} (retrieved {pack['retrieved_at_iso8601']}):"]
        for ref in pack["references"][:6]:
            lines.append(f"• {ref.get('title', '')[:90]} — {ref.get('url', '')}")
        return {"ok": True, "summary": "\n".join(lines), "count": pack["count"]}

    def select_model(model=""):
        model = str(model or "").strip()
        models = llm.available_models()
        if model and models and model not in models:
            return {"ok": False, "summary": f"'{model}' is not installed. Available: {', '.join(models)}"}
        llm.save_settings({"model": model})
        return {"ok": True, "summary": f"Model set to {model or '(auto)'}."}

    def start_ollama():
        r = llm.ensure_ollama(force=True)
        return {"ok": bool(r["ok"]), "summary": f"Ollama: {r['detail']} ({r['host']})"}

    def email_client_package(to="", as_of=None, approved=False):
        to = str(to or "").strip()
        if not to:
            return {"ok": False, "summary": "No recipient address. Provide an email, e.g. [REDACTED_EMAIL]."}
        if not approved:
            return {"ok": False, "summary": "Explicit approval required. Pass approved=true to send."}
        if "@" not in to:
            return {"ok": False, "summary": f"'{to}' is not a valid email address."}
        pkg = state.get("client_package")
        if not pkg:
            try:
                res = build_client_package(state, as_of or None)
                pkg = res["client_package"]
            except ValueError as exc:
                return {"ok": False, "summary": f"Invalid --as-of date: {exc}. Use YYYY-MM-DD."}
        subject = "full simulated inputs for your modifications attach files"
        body_text = client_package_email_body(pkg)
        attach = [Path(f["path"]) for f in (pkg.get("files") or []) if Path(f["path"]).is_file()]
        for special in (pkg.get("cover_md"), pkg.get("overview")):
            if special and Path(special).is_file() and special not in [str(a) for a in attach]:
                attach.append(Path(special))
        email_result = mailer.deliver(to, subject, body_text, attach, approved=True)
        try:
            audit = config.OUTPUT_DIR / "createlee_client_package_email_log.jsonl"
            audit.parent.mkdir(parents=True, exist_ok=True)
            with audit.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "event": "client_package_emailed", "sent_at_iso8601": core.iso_now(),
                    "session_id": state["sid"], "to": to, "subject": subject,
                    "attachments": [str(a) for a in attach],
                    "attachment_count": len(attach),
                    "as_of": pkg.get("as_of"),
                    "mode": (email_result or {}).get("mode"),
                    "reviewer": "operator (explicit approval via agent tool)",
                }, ensure_ascii=False) + "\n")
        except OSError:  # noqa: BLE001
            pass
        return {"ok": bool(email_result.get("ok")),
                "summary": email_result.get("message", ""),
                "to": to, "subject": subject,
                "attachments": [a.name for a in attach],
                "attachment_count": len(attach),
                "mode": email_result.get("mode")}

    return {
        "platform_status": platform_status,
        "list_documents": list_documents,
        "analyze_uploads": analyze_uploads,
        "list_uploads": list_uploads,
        "generate_documents": generate_documents,
        "build_evidence": build_evidence,
        "build_library": build_library,
        "build_handoff": build_handoff,
        "project_readiness": project_readiness,
        "web_research": web_research,
        "select_model": select_model,
        "start_ollama": start_ollama,
        # used by the deterministic fallback
        "handoff_summary": lambda: {"ok": True, "summary": _handoff_summary_text()},
        "evidence_summary": lambda: {"ok": True, "summary": _evidence_summary_text()},
        "model_summary": lambda: {"ok": True, "summary": _model_summary_text()},
        "email_client_package": email_client_package,
        # injected into the agent's system prompt as authoritative grounding
        "runtime_context": lambda: {"ok": True, "summary": _runtime_context_text(state)},
    }


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route("/")
def index():
    return render_template("index.html", platform=config.PLATFORM_NAME,
                           agent=config.AGENT_NAME, version=config.SCHEMA_VERSION)


@app.route("/api/status")
def api_status():
    return jsonify({
        "platform": config.PLATFORM_NAME, "agent": config.AGENT_NAME,
        "version": config.SCHEMA_VERSION, "server_time_iso8601": core.iso_now(),
        "formats": list(core.FORMATS), "domains": core.DOMAIN_LABELS,
        "ollama": llm.status(), "email": mailer.status(),
        "web_enabled": config.WEB_ENRICH,
        "sample_files": [p.name for p in sorted(config.SAMPLES_DIR.glob("*.csv"))],
        "max_upload_mb": config.MAX_UPLOAD_MB,
        "allowed_ext": sorted(config.ALLOWED_EXT),
    })


# --------------------------------------------------------------------------- #
# Settings + local model management
# --------------------------------------------------------------------------- #
@app.route("/api/settings")
def api_settings():
    """Everything the Settings panel needs in one call."""
    models = llm.available_models()
    o = llm.ollama_status()
    return jsonify({
        "ok": True,
        "settings": llm.load_settings(),
        "models": models,
        "selected": llm.selected_model(models),
        "ollama": o,
        "llm": llm.status(),
        "tools": agent.TOOL_NAMES,
        "server_time_iso8601": core.iso_now(),
    })


@app.route("/api/settings", methods=["POST"])
def api_settings_save():
    body = request.get_json(silent=True) or {}
    patch = {}
    if "model" in body:
        patch["model"] = str(body.get("model") or "").strip()
    if "autostart" in body:
        patch["autostart"] = bool(body.get("autostart"))
    if "temperature" in body:
        try:
            patch["temperature"] = max(0.0, min(1.5, float(body.get("temperature"))))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "temperature must be a number"}), 400
    if "max_steps" in body:
        try:
            patch["max_steps"] = max(1, min(12, int(body.get("max_steps"))))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "max_steps must be an integer"}), 400
    if "num_predict" in body:
        try:
            patch["num_predict"] = max(128, min(4096, int(body.get("num_predict"))))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "num_predict must be an integer"}), 400

    settings = llm.save_settings(patch)
    models = llm.available_models()
    return jsonify({"ok": True, "settings": settings, "models": models,
                    "selected": llm.selected_model(models),
                    "ollama": llm.ollama_status()})


@app.route("/api/models")
def api_models():
    models = llm.available_models()
    return jsonify({"ok": True, "models": models,
                    "selected": llm.selected_model(models),
                    "available": bool(models),
                    "ollama": llm.ollama_status(),
                    "last_load": dict(llm._LAST_LOAD)})


@app.route("/api/constitution", methods=["GET"])
def api_constitution():
    """Constitution text + the most recent sign-in must-do entry."""
    return jsonify({
        "ok": True,
        "path": str(constitution.CONSTITUTION_PATH),
        "loaded": constitution.CONSTITUTION_PATH.is_file(),
        "text": constitution.load_constitution(),
        "last_sign_in": constitution.last_sign_in(),
        "server_time_iso8601": core.iso_now(),
    })


@app.route("/api/scan", methods=["GET"])
def api_scan():
    """Dynamic output scan — real, actual current status of the platform.

    Reports what exists, what is staged, what is approved, what is missing, and
    whether the strict Signoff contract passes. Honest findings only.
    """
    sid = (request.args.get("sid") or "").strip()
    st = get_state(sid) if sid else None

    scan = {
        "server_time_iso8601": core.iso_now(),
        "platform": config.PLATFORM_NAME,
        "agent": config.AGENT_NAME,
        "version": config.SCHEMA_VERSION,
        "ollama": llm.status(),
        "email": mailer.status(),
        "web_enabled": config.WEB_ENRICH,
    }

    if st is None:
        scan["session"] = None
        scan["finding"] = "No session id supplied. Open /api/session first or pass ?sid=<sid>."
    else:
        out_dir = config.OUTPUT_DIR
        files = []
        try:
            for p in sorted(out_dir.glob("*"), key=lambda x: x.stat().st_mtime,
                            reverse=True):
                if p.is_file() and p.suffix.lower() != ".jsonl":
                    files.append({
                        "filename": p.name, "format": p.suffix.lower().lstrip("."),
                        "size_bytes": p.stat().st_size,
                        "modified_at_iso8601": core.iso_now(),
                    })
        except OSError:  # noqa: BLE001
            files = []
        scan["session"] = {
            "sid": st["sid"],
            "uploads": len(st.get("uploads", [])),
            "staged_drafts": len(st.get("staged", [])),
            "approved_outputs": len(st.get("outputs", [])),
            "history_turns": len(st.get("history", [])),
            "references": bool(st.get("references")),
        }
        scan["outputs"] = files[:120]
        scan["output_count"] = len(files)
        scan["missing_required_uploads"] = [
            n for n in ("questions.csv", "mapping-table.template.csv")
            if n not in {u.get("filename") for u in st.get("uploads", [])}
        ]
        scan["finding"] = (
            "Staged drafts are not saved or emailed until the operator approves."
            if st.get("staged") else "No staged drafts."
        )

    # Strict Signoff contract status on the evidence pack (read-only).
    try:
        from evidence import validate_strict
        ev_dir = config.EVIDENCE_DIR
        strict = validate_strict(ev_dir) if ev_dir.is_dir() else None
    except Exception:  # noqa: BLE001
        strict = None
    scan["signoff_strict_contract"] = (strict["summary"] if strict
                                       else {"verdict": "no evidence pack built yet"})
    return jsonify({"ok": True, "scan": scan})


def _load_raw_state(sid: str) -> dict | None:
    """Read state.json without mutating or repairing (used for dry-run GET)."""
    p = state_path(sid)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


@app.route("/api/repair-state", methods=["GET", "POST"])
def api_repair_state():
    """Expose the state.json path repair helper.

    GET  -> report which session paths would be repaired (dry run, no mutation).
    POST -> perform the repair via get_state() and save state.json.
    """
    body = request.get_json(silent=True) or {}
    sid = (body.get("sid") or request.args.get("sid") or "").strip()
    if not sid or not SID_RE.match(sid):
        return jsonify({"ok": False, "error": "provide a valid sid"}), 400
    base = sdir(sid) / "uploads"
    raw = _load_raw_state(sid)
    if raw is None:
        return jsonify({"ok": False, "error": "no state.json for that sid",
                        "sid": sid}), 404
    candidates = []
    for u in raw.get("uploads", []):
        path = Path(u.get("path") or "")
        if path.is_file():
            continue
        cand = base / u.get("filename", "")
        candidates.append({
            "filename": u.get("filename"),
            "stored_path": str(path) if path else "",
            "exists_now": cand.is_file(),
            "repaired_to": str(cand) if cand.is_file() else None,
        })
    would_repair = any(c["repaired_to"] for c in candidates)
    if request.method == "POST" and would_repair:
        st = get_state(sid)  # this runs _repair_upload_paths and saves
        return jsonify({
            "ok": True, "sid": st["sid"], "session_dir": str(sdir(sid)),
            "uploads_dir": str(base), "candidates": candidates,
            "repaired": True, "dry_run": False,
        })
    return jsonify({
        "ok": True, "sid": sid, "session_dir": str(sdir(sid)),
        "uploads_dir": str(base), "candidates": candidates,
        "repaired": would_repair, "dry_run": request.method == "GET",
    })


@app.route("/api/ollama/start", methods=["POST"])
def api_ollama_start():
    r = llm.ensure_ollama(force=True)
    models = llm.available_models()
    return jsonify({"ok": bool(r["ok"]), **r, "models": models,
                    "selected": llm.selected_model(models),
                    "ollama": llm.ollama_status()}), (200 if r["ok"] else 503)


@app.route("/api/email/test", methods=["POST"])
def api_email_test():
    """Send one plain test message to verify the SMTP configuration.

    Only callable explicitly by the operator. With no password configured it
    returns the .eml-draft mode and says nothing was sent.
    """
    body = request.get_json(silent=True) or {}
    to = (body.get("to") or config.DEFAULT_EMAIL_TO or config.SMTP_FROM).strip()
    if not to:
        return jsonify({"ok": False, "mailer": mailer.status(),
                        "error": "No recipient. Set CREATELEE_DEFAULT_EMAIL_TO in .env "
                                 "or pass {\"to\": \"you@example.com\"}."}), 400
    res = mailer.deliver(
        to,
        "Createlee SMTP test",
        "This is a test message from Createlee / Engeznee.\n"
        "If you received it, real SMTP sending is enabled.\n",
        [], approved=True)
    # For a *test* the only success is a real send; a draft means SMTP is not ready.
    sent = res.get("mode") == "smtp-send"
    return jsonify({"ok": sent, "mailer": mailer.status(), "result": res,
                    "hint": ("" if sent else
                             "No SMTP send happened. Put a Gmail App Password in "
                             "CREATELEE_SMTP_PASSWORD in .env, then restart the app.")}), \
        (200 if sent else 400)


@app.route("/api/session", methods=["POST"])
def api_session():
    body = request.get_json(silent=True) or {}
    sid = body.get("sid")
    if body.get("new") or not sid:
        sid = "s" + secrets.token_hex(8)
        st = new_state(sid)
        (sdir(sid) / "uploads").mkdir(parents=True, exist_ok=True)
        STATE[sid] = st
        seed_samples(st)
        save_state(st)
    else:
        st = get_state(sid)
    return jsonify({"ok": True, "sid": st["sid"], "state": public_state(st),
                    "status": status_text()})


@app.route("/api/state/<sid>")
def api_state(sid):
    if not SID_RE.match(sid):
        return jsonify({"ok": False, "error": "invalid session id"}), 400
    return jsonify({"ok": True, "state": public_state(get_state(sid))})


@app.route("/api/upload", methods=["POST"])
def api_upload():
    sid = (request.form.get("sid") or "").strip()
    st = get_state(sid)
    files = request.files.getlist("files")
    if not files:
        return jsonify({"ok": False, "error": "No files received"}), 400
    added, rejected = [], []
    for f in files:
        name = secure_filename(f.filename or "")
        if not name:
            continue
        ext = Path(name).suffix.lower()
        if ext not in config.ALLOWED_EXT:
            rejected.append(f"{name} (unsupported extension)")
            continue
        tmp = sdir(st["sid"]) / "uploads" / (".tmp_" + secrets.token_hex(4) + "_" + name)
        tmp.parent.mkdir(parents=True, exist_ok=True)
        f.save(str(tmp))
        added.append(add_upload(st, tmp, filename=name))
        tmp.unlink(missing_ok=True)
    st["staged"] = []          # uploads changed -> drafts are stale
    save_state(st)
    text = (f"Uploaded {len(added)} file(s) at {core.iso_now()}.\n"
            + "\n".join(f"  • {e['filename']}: {e['analysis'].get('kind')}, "
                        f"{e['analysis'].get('rows', 0)} rows, "
                        f"{len(e['analysis'].get('columns', []))} columns"
                        for e in added))
    if rejected:
        text += "\nRejected: " + "; ".join(rejected)
    text += "\n\nStaged drafts were cleared because the input set changed. Say 'analyze' or 'generate ...'."
    return reply(st, text)


@app.route("/api/clear-uploads", methods=["POST"])
def api_clear_uploads():
    body = request.get_json(silent=True) or {}
    st = get_state(body.get("sid"))
    st["uploads"] = []
    st["staged"] = []
    shutil.rmtree(sdir(st["sid"]) / "uploads", ignore_errors=True)
    (sdir(st["sid"]) / "uploads").mkdir(parents=True, exist_ok=True)
    save_state(st)
    return reply(st, "All uploads and staged drafts cleared. Upload questions.csv, "
                     "mapping-table.template.csv and your data files to continue.")


@app.route("/api/load-samples", methods=["POST"])
def api_load_samples():
    body = request.get_json(silent=True) or {}
    st = get_state(body.get("sid"))
    seed_samples(st)
    st["staged"] = []
    save_state(st)
    return reply(st, "Bundled sample pack loaded (both canonical CSVs + 5 data files). "
                     "Replace any file by uploading one with the same name.")


@app.route("/api/template/<path:filename>")
def api_template(filename):
    name = secure_filename(filename)
    p = config.SAMPLES_DIR / name
    if not p.is_file() or p.suffix.lower() != ".csv":
        return "Not found", 404
    return send_from_directory(str(config.SAMPLES_DIR), name, as_attachment=True)


@app.route("/download/<path:filename>")
def download(filename):
    name = secure_filename(filename)
    p = config.OUTPUT_DIR / name
    if not p.is_file():
        return "Not found", 404
    return send_from_directory(str(config.OUTPUT_DIR), name, as_attachment=True)


@app.route("/api/files")
def api_files():
    out = []
    for p in sorted(config.OUTPUT_DIR.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.is_file() and p.suffix.lower() != ".jsonl":
            out.append({"filename": p.name, "size_bytes": p.stat().st_size,
                        "format": p.suffix.lower().lstrip("."),
                        "modified_at_iso8601": core.iso_now(),
                        "url": "/download/" + p.name})
    return jsonify({"ok": True, "files": out[:120], "count": len(out)})


@app.route("/api/preview/<sid>/<int:index>")
def api_preview(sid, index):
    if not SID_RE.match(sid):
        return jsonify({"ok": False, "error": "invalid session id"}), 400
    st = get_state(sid)
    if index < 0 or index >= len(st["staged"]):
        return jsonify({"ok": False, "error": "no such staged document"}), 404
    return jsonify({"ok": True, "text": st["staged"][index]["preview"],
                    "title": st["staged"][index]["title"]})


@app.route("/api/evidence", methods=["POST"])
def api_evidence():
    """Programmatic evidence pack endpoint. Returns the full validation report JSON."""
    body = request.get_json(silent=True) or {}
    st = get_state(body.get("sid"))
    try:
        ev = run_evidence(st, body.get("as_of") or None,
                          generate_examples=body.get("validate_only") is not True)
    except ValueError as exc:
        return jsonify({"ok": False, "error": f"Invalid as_of date: {exc}. Use YYYY-MM-DD."}), 400
    return jsonify({"ok": True, "text": ev["text"], "report": ev["result"]["report"],
                    "files": ev["result"]["report_exports"],
                    "state": public_state(st)})


@app.route("/api/library", methods=["POST"])
def api_library():
    """Programmatic system-library endpoint. Returns the full build manifest."""
    body = request.get_json(silent=True) or {}
    st = get_state(body.get("sid"))
    try:
        lib = run_library(st, body.get("as_of") or None)
    except ValueError as exc:
        return jsonify({"ok": False, "error": f"Invalid as_of date: {exc}. Use YYYY-MM-DD."}), 400
    return jsonify({"ok": True, "text": lib["text"], "manifest": lib["result"]["manifest"],
                    "row_counts": lib["result"]["row_counts"],
                    "reconciliation": lib["result"]["reconciliation"],
                    "findings": lib["result"]["findings"],
                    "files": lib["result"]["report_exports"],
                    "state": public_state(st)})


@app.route("/api/handoff", methods=["POST"])
def api_handoff():
    """Programmatic per-project hand-off pack endpoint. Returns every manifest."""
    body = request.get_json(silent=True) or {}
    st = get_state(body.get("sid"))
    try:
        h = run_handoff(st, body.get("as_of") or None)
    except ValueError as exc:
        return jsonify({"ok": False, "error": f"Invalid as_of date: {exc}. Use YYYY-MM-DD."}), 400
    return jsonify({"ok": True, "text": h["text"],
                    "projects": h["result"]["projects"],
                    "overview": h["result"]["overview"],
                    "files_written": h["result"]["files_written"],
                    "state": public_state(st)})


@app.route("/api/client-package", methods=["POST"])
def api_client_package():
    """Build the full per-project simulated-inputs package (all 4 projects) and
    stage it in the session so it can be emailed in full."""
    body = request.get_json(silent=True) or {}
    st = get_state(body.get("sid"))
    try:
        res = build_client_package(st, body.get("as_of") or None)
    except ValueError as exc:
        return jsonify({"ok": False, "error": f"Invalid as_of date: {exc}. Use YYYY-MM-DD."}), 400
    return jsonify({"ok": True, "client_package": res["client_package"],
                    "text": res["handoff"], "state": public_state(st)})


@app.route("/api/email-client-package", methods=["POST"])
def api_email_client_package():
    """Email the FULL simulated-inputs package to the third party.

    Requires explicit approved=true + a recipient. Attaches EVERY file in the
    hand-off package plus the step-by-step CLIENT-INSTRUCTIONS.md cover letter.
    Never sends without explicit approval. Nothing already built is removed.
    """
    body = request.get_json(silent=True) or {}
    if body.get("approved") is not True:
        return jsonify({"ok": False, "error": "Explicit approval required. Set approved=true. Nothing was sent."}), 403
    to = (body.get("to") or config.DEFAULT_EMAIL_TO or "").strip()
    if "@" not in to:
        return jsonify({"ok": False, "error": "A valid recipient address is required."}), 400
    st = get_state(body.get("sid"))
    pkg = st.get("client_package")
    if not pkg:
        try:
            res = build_client_package(st, body.get("as_of") or None)
            pkg = res["client_package"]
        except ValueError as exc:
            return jsonify({"ok": False, "error": f"Invalid as_of date: {exc}. Use YYYY-MM-DD."}), 400
    subject = (body.get("subject") or
               "full simulated inputs for your modifications attach files").strip()
    body_text = client_package_email_body(pkg)
    attach = [Path(f["path"]) for f in (pkg.get("files") or []) if Path(f["path"]).is_file()]
    # Always attach the cover letter + overview even if the glob missed them.
    for special in (pkg.get("cover_md"), pkg.get("overview")):
        if special and Path(special).is_file() and special not in [str(a) for a in attach]:
            attach.append(Path(special))
    email_result = mailer.deliver(to, subject, body_text, attach, approved=True)
    # Audit log of the client-package send.
    audit = config.OUTPUT_DIR / "createlee_client_package_email_log.jsonl"
    try:
        audit.parent.mkdir(parents=True, exist_ok=True)
        with audit.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "event": "client_package_emailed", "sent_at_iso8601": core.iso_now(),
                "session_id": st["sid"], "to": to, "subject": subject,
                "attachments": [str(a) for a in attach],
                "attachment_count": len(attach),
                "as_of": pkg.get("as_of"),
                "mode": (email_result or {}).get("mode"),
                "reviewer": "operator (explicit approval)",
            }, ensure_ascii=False) + "\n")
    except OSError:  # noqa: BLE001
        pass
    return jsonify({"ok": bool(email_result.get("ok")),
                    "email": email_result, "to": to, "subject": subject,
                    "attachments": [a.name for a in attach],
                    "attachment_count": len(attach),
                    "state": public_state(st)})


# --------------------------------------------------------------------------- #
# System-library browser (read-only)
# --------------------------------------------------------------------------- #
def _library_group(rel: str) -> str:
    """Human label for a library file's top-level group."""
    if "/" not in rel:
        return "Root (corpus, labels, reconciliation)"
    top = rel.split("/", 1)[0]
    return {
        "uploaded": "uploaded/ — your 6 REAL signoff files",
        "evidence": "evidence/ — 8 Signoff evidence CSVs",
        "systems": "systems/ — compact system library",
    }.get(top, top + "/")


@app.route("/api/library/status")
def api_library_status():
    lib = config.LIBRARY_DIR
    mp = lib / "LIBRARY_MANIFEST.json"
    if not mp.is_file():
        return jsonify({"ok": True, "built": False, "dir": str(lib),
                        "message": "System library not built yet. Click 'Build library'."})
    try:
        m = json.loads(mp.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "error": f"manifest unreadable: {exc}"}), 500
    return jsonify({
        "ok": True, "built": True, "dir": str(lib),
        "as_of": m.get("as_of"), "generated_at_iso8601": m.get("generated_at_iso8601"),
        "file_count": m.get("file_count"), "row_counts": m.get("row_counts"),
        "reconciliation": m.get("reconciliation"), "findings": m.get("findings"),
        "limitations": m.get("limitations"),
        "web_reference_count": len(m.get("web_references", [])),
        "report_exports": m.get("report_exports"),
    })


@app.route("/api/library/files")
def api_library_files():
    lib = config.LIBRARY_DIR
    if not lib.is_dir():
        return jsonify({"ok": True, "built": False, "groups": []})
    files = []
    for p in sorted(lib.rglob("*"), key=lambda x: str(x).lower()):
        if not p.is_file() or p.name == "INDEX.csv":
            continue
        rel = str(p.relative_to(lib))
        ext = p.suffix.lower().lstrip(".")
        rows = cols = ""
        if ext == "csv":
            try:
                with p.open(encoding="utf-8", errors="replace") as f:
                    rd = list(csv.reader(f))
                if rd:
                    cols, rows = len(rd[0]), len(rd) - 1
            except Exception:  # noqa: BLE001
                pass
        files.append({
            "path": rel, "name": p.name, "group": _library_group(rel),
            "format": ext, "size_bytes": p.stat().st_size, "rows": rows, "columns": cols,
        })
    # stable, human-friendly group order
    order = ["Root (corpus, labels, reconciliation)", "uploaded/ — your 6 REAL signoff files",
             "evidence/ — 8 Signoff evidence CSVs", "systems/ — compact system library"]
    groups = []
    for label in order:
        items = [f for f in files if f["group"] == label]
        if items:
            groups.append({"label": label, "files": items})
    extra = [f for f in files if f["group"] not in order]
    if extra:
        groups.append({"label": "other", "files": extra})
    return jsonify({"ok": True, "built": True, "dir": str(lib), "groups": groups})


@app.route("/api/library/file/<path:relpath>")
def api_library_file(relpath):
    lib = config.LIBRARY_DIR.resolve()
    p = (lib / relpath).resolve()
    if not str(p).startswith(str(lib) + "/") and p != lib:
        return jsonify({"ok": False, "error": "invalid path"}), 400
    if not p.is_file():
        return jsonify({"ok": False, "error": "file not found"}), 404
    ext = p.suffix.lower()
    if ext == ".csv":
        header, rows = [], []
        try:
            with p.open(encoding="utf-8", errors="replace") as f:
                rd = list(csv.reader(f))
            if rd:
                header = rd[0]
                rows = rd[1:]
        except Exception as exc:  # noqa: BLE001
            return jsonify({"ok": False, "error": f"unreadable: {exc}"}), 500
        total = len(rows)
        return jsonify({"ok": True, "path": relpath, "name": p.name, "format": "csv",
                        "header": header, "rows": rows[:1000], "row_count": total,
                        "truncated": total > 1000})
    if ext in (".txt", ".json", ".md", ".log", ".jsonl"):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            return jsonify({"ok": False, "error": f"unreadable: {exc}"}), 500
        return jsonify({"ok": True, "path": relpath, "name": p.name,
                        "format": ext.lstrip("."), "text": text[:200000]})
    return jsonify({"ok": True, "path": relpath, "name": p.name, "format": ext.lstrip("."),
                    "binary": True, "download_url": "/api/library/download/" + relpath})


@app.route("/api/library/download/<path:relpath>")
def api_library_download(relpath):
    lib = config.LIBRARY_DIR.resolve()
    p = (lib / relpath).resolve()
    if not str(p).startswith(str(lib) + "/") and p != lib:
        return "invalid path", 400
    if not p.is_file():
        return "Not found", 404
    return send_from_directory(str(p.parent), p.name, as_attachment=True)


@app.route("/api/chat", methods=["POST"])
def api_chat():
    body = request.get_json(silent=True) or {}
    st = get_state(body.get("sid"))
    message = (body.get("message") or "").strip()
    if not message:
        return jsonify({"ok": False, "error": "empty message"}), 400
    st["history"].append({"role": "user", "text": message, "at_iso8601": core.iso_now()})
    low = message.lower().strip()

    try:
        # ---- help / status / analyze / list / preview / clear --------------
        if low in ("help", "?", "commands", "start"):
            return jsonify(reply(st, HELP_TEXT))
        # ---- per-project hand-off packs (what to send, per project) ---------
        is_handoff = bool(re.search(
            r"\b(handoff|hand-off|hand off|request list|requested files|"
            r"client files|send to client|per project|unblock)\b", low))
        if is_handoff:
            m_date = re.search(r"as[- ]?of[ =:]*(\d{4}-\d{2}-\d{2})", message, re.I) or \
                     re.search(r"(\d{4}-\d{2}-\d{2})", message)
            as_of = m_date.group(1) if m_date else None
            try:
                h = run_handoff(st, as_of)
            except ValueError as exc:
                return jsonify(reply(st, f"Invalid --as-of date ({exc}). Use YYYY-MM-DD, e.g. 2026-11-06."))
            return jsonify(reply(st, h["text"]))
        # ---- system library (procedure corpus + labels + reconciliation) ----
        is_library = bool(re.search(r"\b(library|system files|procedure corpus|"
                                    r"expected.outcome labels|reconciliation)\b", low))
        if is_library:
            m_date = re.search(r"as[- ]?of[ =:]*(\d{4}-\d{2}-\d{2})", message, re.I) or \
                     re.search(r"(\d{4}-\d{2}-\d{2})", message)
            as_of = m_date.group(1) if m_date else None
            try:
                lib = run_library(st, as_of)
            except ValueError as exc:
                return jsonify(reply(st, f"Invalid --as-of date ({exc}). Use YYYY-MM-DD, e.g. 2026-11-06."))
            return jsonify(reply(st, lib["text"], staged_count=len(st["staged"])))
        # ---- evidence / signoff pack (the 8-file operational export task) ----
        is_evidence = bool(re.search(r"\b(evidence|signoff)\b", low)) or \
                      bool(re.search(r"8\s+specific\s+csv", low))
        if is_evidence:
            m_date = re.search(r"as[- ]?of[ =:]*(\d{4}-\d{2}-\d{2})", message, re.I) or \
                     re.search(r"(\d{4}-\d{2}-\d{2})", message)
            as_of = m_date.group(1) if m_date else None
            validate_only = bool(re.search(r"validate[- ]?only|--validate-only|real exports", low))
            try:
                ev = run_evidence(st, as_of, generate_examples=not validate_only)
            except ValueError as exc:
                return jsonify(reply(st, f"Invalid --as-of date ({exc}). Use YYYY-MM-DD, e.g. 2026-11-06."))
            return jsonify(reply(st, ev["text"], staged_count=len(st["staged"])))
        if low in ("status", "health", "integrations"):
            return jsonify(reply(st, status_text()))
        if re.match(r"^(analyze|analyse|inspect|scan)\b", low):
            return jsonify(reply(st, analysis_text(st)))
        if low in ("list", "documents", "templates", "what can you generate", "ls"):
            q, m, _ds, _an = build_context(st)
            docs = core.available_documents(q, m)
            mode = ("checklist (Ref / Question / Yes / Partly / No)"
                    if any(x.get("_checklist") for x in q) else "canonical 11-column schema")
            lines = [f"Documents defined by your CSV schemas ({len(docs)}):",
                     f"questions.csv detected as: {mode}",
                     f"mapping-table.template.csv: {len(m)} mapping row(s)", ""]
            for d in docs:
                active = "" if d["criteria_count"] else "  [mapping-only — not generated by default]"
                lines.append(f"  • [{d['domain']}] {d['document_type']} — {core.document_title(d['document_type'])} "
                             f"({d['criteria_count']} criteria / {d['mapping_count']} mapped fields){active}")
            lines.append("\nSay: generate all   |   generate QA, WFM as pdf,csv,json")
            return jsonify(reply(st, "\n".join(lines)))
        if low in ("preview", "show", "drafts", "review"):
            if not st["staged"]:
                return jsonify(reply(st, "There are no staged drafts. Say 'generate all' first."))
            return jsonify(reply(st, f"{len(st['staged'])} draft(s) staged and awaiting your approval. "
                                     "Open each one in the Review & Approve panel."))
        if low in ("clear", "discard", "reset drafts"):
            st["staged"] = []
            save_state(st)
            return jsonify(reply(st, "Staged drafts discarded. Nothing was saved or emailed."))

        # ---- web references ------------------------------------------------
        if low.startswith(("web:", "search ", "references ")) or low.startswith("web "):
            query = re.sub(r"^(web:|web |search |references )", "", message, flags=re.I).strip()
            if not query:
                return jsonify(reply(st, "Usage: web: <topic>, e.g. web: ISO 8601 timestamp standard"))
            pack = websearch.reference_pack(query)
            st["references"] = pack
            save_state(st)
            lines = [f"Live web references for: {query}", f"Retrieved: {pack['retrieved_at_iso8601']}",
                     f"Sources found: {pack['count']}", ""]
            for r in pack["references"]:
                lines.append(f"  • {r.get('title', '')[:90]}\n    {r.get('url', '')}\n    {r.get('snippet', '')[:160]}")
            lines += ["", pack["notice"]]
            return jsonify(reply(st, "\n".join(lines)))

        # ---- email prefill --------------------------------------------------
        m_to = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", message)
        if m_to and re.search(r"\b(email|send|mail)\b", low):
            st["email_prefill"]["to"] = m_to.group(0)
            st["email_prefill"]["subject"] = st["email_prefill"]["subject"] or "Createlee / Engeznee — generated operations documents"
            save_state(st)
            return jsonify(reply(st, f"Recipient pre-filled: {m_to.group(0)}.\n"
                                     "Generation is staged only. After you review every document in the "
                                     "Review & Approve panel, choose 'Save & Email' and press Approve & Execute."))

        # ---- generate (explicit command) ------------------------------------
        is_generate = bool(re.search(r"\b(generate|create|make|build|produce|draft)\b", low))
        if is_generate:
            cmd = parse_generate(message, core.available_documents(*build_context(st)[:2]))
            if not cmd:
                return jsonify(reply(st, "I didn't recognise that command. Type 'help' for the full list, "
                                         "or try: analyze / list / generate all / web: ISO 8601"))
            ok, text, count = stage_documents(
                st, cmd["domains"], cmd["formats"], cmd["doc_types"],
                include_timestamp=cmd["include_timestamp"], with_web=cmd.get("with_web"))
            return jsonify(reply(st, text, staged_count=count if ok else None))

        # ---- client package: build the FULL simulated-inputs set -----------
        is_cp_build = bool(re.search(
            r"\b(client.?package|full package|simulated inputs|all hand.?off packs)\b", low)) and \
            bool(re.search(r"\b(build|create|make|generate|refresh|rebuild)\b", low))
        if is_cp_build:
            m_date = re.search(r"as[- ]?of[ =:]*(\d{4}-\d{2}-\d{2})", message, re.I) or \
                     re.search(r"(\d{4}-\d{2}-\d{2})", message)
            as_of = m_date.group(1) if m_date else None
            try:
                res = build_client_package(st, as_of)
            except ValueError as exc:
                return jsonify(reply(st, f"Invalid --as-of date ({exc}). Use YYYY-MM-DD."))
            pkg = res["client_package"]
            lines = [f"CLIENT PACKAGE built at {pkg['built_at_iso8601']} (ISO-8601 UTC).",
                     f"as-of: {pkg['as_of']}   files: {pkg['files_written']}",
                     f"Folder: {config.HANDOFF_DIR}", "",
                     "Every file below is ready to attach and send to the third party:",
                     ""]
            for f in pkg["files"][:60]:
                lines.append(f"  • {f['rel']}  ({f['size_bytes']:,} bytes)")
            if len(pkg["files"]) > 60:
                lines.append(f"  ... and {len(pkg['files']) - 60} more file(s)")
            lines += ["", "To email the FULL package with step-by-step MD instructions, say:",
                      "  'send client package to [REDACTED_EMAIL] approved'",
                      "  (explicit approval is required before anything is sent.)"]
            return jsonify(reply(st, "\n".join(lines)))

        # ---- client package: email the FULL set to the third party ---------
        is_cp_email = bool(re.search(r"\b(send|email|mail|resend)\b", low)) and \
            bool(re.search(r"\b(client.?package|full package|simulated inputs|all hand.?off)\b", low))
        if is_cp_email:
            m_to = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", message)
            if not m_to:
                return jsonify(reply(st, "I need a recipient address. Say: "
                                         "'send client package to [REDACTED_EMAIL] approved'"))
            if "approved" not in low:
                return jsonify(reply(st, f"Found recipient {m_to.group(0)}. I need your explicit "
                                         "approval to send. Say: 'send client package to "
                                         + m_to.group(0) + " approved'"))
            pkg = st.get("client_package")
            if not pkg:
                try:
                    res = build_client_package(st, None)
                    pkg = res["client_package"]
                except ValueError as exc:
                    return jsonify(reply(st, f"Invalid package build: {exc}"))
            subject = "full simulated inputs for your modifications attach files"
            body_text = client_package_email_body(pkg)
            attach = [Path(f["path"]) for f in (pkg.get("files") or []) if Path(f["path"]).is_file()]
            for special in (pkg.get("cover_md"), pkg.get("overview")):
                if special and Path(special).is_file() and special not in [str(a) for a in attach]:
                    attach.append(Path(special))
            email_result = mailer.deliver(m_to.group(0), subject, body_text, attach, approved=True)
            try:
                audit = config.OUTPUT_DIR / "createlee_client_package_email_log.jsonl"
                audit.parent.mkdir(parents=True, exist_ok=True)
                with audit.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps({
                        "event": "client_package_emailed", "sent_at_iso8601": core.iso_now(),
                        "session_id": st["sid"], "to": m_to.group(0), "subject": subject,
                        "attachments": [str(a) for a in attach],
                        "attachment_count": len(attach),
                        "as_of": pkg.get("as_of"),
                        "mode": (email_result or {}).get("mode"),
                        "reviewer": "operator (explicit approval via chat)",
                    }, ensure_ascii=False) + "\n")
            except OSError:  # noqa: BLE001
                pass
            return jsonify(reply(st, f"EMAILED the full client package to {m_to.group(0)}.\n"
                                     f"Subject: {subject}\n"
                                     f"Attachments: {len(attach)} file(s) — every simulated-input "
                                     f"file plus the CLIENT-INSTRUCTIONS.md step-by-step rules.\n"
                                     f"Mode: {email_result.get('mode')}\n"
                                     f"{email_result.get('message', '')}"))

        # ---- everything else: the executive-assistant agent -----------------
        res = agent.chat(st, message, agent_ops(st))
        return jsonify(reply(st, res["text"], agent_source=res["source"],
                             trace=res["trace"], tools_used=res["tools_used"]))

    except core.SchemaError as exc:
        return jsonify(reply(st, f"Schema problem: {exc}\n\nDownload the two canonical templates from the "
                                 "left panel, fill them in, and upload them."))
    except Exception as exc:  # noqa: BLE001 - keep the chat alive on any error
        return jsonify(reply(st, f"Error: {type(exc).__name__}: {exc}\n"
                                 "Nothing was saved or emailed. Type 'status' or 'analyze' to investigate."))


@app.route("/api/approve", methods=["POST"])
def api_approve():
    """THE GATE. Requires explicit approved=true + selected document indices."""
    body = request.get_json(silent=True) or {}
    st = get_state(body.get("sid"))
    if body.get("approved") is not True:
        return jsonify({"ok": False, "error": "Explicit approval required. Nothing was saved or emailed."}), 403
    if not st["staged"]:
        return jsonify({"ok": False, "error": "There are no staged drafts to approve."}), 400
    indices = body.get("selected", [])
    if not isinstance(indices, list) or not indices:
        return jsonify({"ok": False, "error": "Select at least one document."}), 400
    indices = sorted({int(i) for i in indices if isinstance(i, (int, float))
                      and 0 <= int(i) < len(st["staged"])})
    if not indices:
        return jsonify({"ok": False, "error": "Invalid document selection."}), 400

    action = (body.get("action") or "save").lower()
    if action not in ("save", "email", "both"):
        return jsonify({"ok": False, "error": "action must be save, email or both"}), 400

    created: list[dict] = []
    approved_at = core.iso_now()
    for i in indices:
        item = st["staged"][i]
        doc = item["doc"]
        doc["meta"]["review_status"] = "APPROVED"
        doc["meta"]["approved_at_iso8601"] = approved_at
        for sec in doc["sections"]:
            for f in sec.get("fields", []):
                if f["label"] == "Review status":
                    f["value"] = "APPROVED"
        for fmt in item["formats"]:
            p = core.export_document(doc, fmt, config.OUTPUT_DIR,
                                     include_timestamp=doc["meta"]["include_timestamp"])
            rec = {"filename": p.name, "size_bytes": p.stat().st_size, "format": fmt,
                   "url": "/download/" + p.name, "domain": item["domain"],
                   "document_type": item["document_type"],
                   "approved_at_iso8601": approved_at, "document_id": doc["meta"]["document_id"]}
            created.append(rec)
            st["outputs"].append(rec)

    email_result = None
    if action in ("email", "both"):
        to = (body.get("email_to") or "").strip()
        subject = (body.get("email_subject") or
                   "Createlee / Engeznee — generated operations documents").strip()
        email_body = (body.get("email_body") or
                      "Attached are the operations documents generated by Createlee and approved for release.\n"
                      f"Approved at {approved_at} (ISO-8601 UTC).\n\nGenerated by Createlee / Engeznee.").strip()
        st["email_prefill"] = {"to": to, "subject": subject, "body": email_body}
        attach = [config.OUTPUT_DIR / c["filename"] for c in created]
        email_result = mailer.deliver(to, subject, email_body, attach, approved=True)
        if email_result.get("filename"):
            st["outputs"].append({"filename": email_result["filename"],
                                 "size_bytes": (config.OUTPUT_DIR / email_result["filename"]).stat().st_size,
                                 "format": "eml", "url": "/download/" + email_result["filename"],
                                 "domain": "DELIVERY", "document_type": "email_draft",
                                 "approved_at_iso8601": approved_at})

    # audit trail
    audit = config.OUTPUT_DIR / "createlee_approval_log.jsonl"
    with audit.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "event": "documents_approved", "approved_at_iso8601": approved_at,
            "session_id": st["sid"], "action": action,
            "documents": [st["staged"][i]["doc"]["meta"]["document_id"] for i in indices],
            "files": [c["filename"] for c in created],
            "email_mode": (email_result or {}).get("mode"),
            "email_to": (body.get("email_to") or "").strip() or None,
            "reviewer": "operator (explicit approval)",
        }, ensure_ascii=False) + "\n")

    st["staged"] = [s for i, s in enumerate(st["staged"]) if i not in indices]
    text = (f"APPROVED at {approved_at}.\n"
            f"Created {len(created)} file(s) in outputs/ — all listed under 'Generated files' for download.")
    if email_result:
        text += f"\nEmail: {email_result['message']}"
    text += "\nNothing else was sent. Remaining drafts (if any) are still staged."
    save_state(st)
    return jsonify(reply(st, text, created=created, email=email_result))


@app.errorhandler(413)
def too_large(_e):
    return jsonify({"ok": False, "error": f"Upload exceeds {config.MAX_UPLOAD_MB} MB limit."}), 413


if __name__ == "__main__":
    import os
    port = int(os.environ.get("CREATELEE_PORT", "7860"))

    # Bring the local model up without waiting for the operator. Non-blocking:
    # the first request is served immediately; the Settings badge updates when
    # the server answers.
    if os.environ.get("CREATELEE_AUTOSTART_OLLAMA", "1") != "0":
        llm.start_ollama_background()

    # Binding rules on every load: read the constitution, probe the local
    # Ollama free model, bind it, and record what changed + timestamp + model.
    init = initialize_constitution()
    bm = init["bound_model"]
    print(f"\n  {config.PLATFORM_NAME} / {config.AGENT_NAME}  ->  http://127.0.0.1:{port}")
    print(f"  constitution: {init['constitution']} (loaded={init['constitution_loaded']})")
    print(f"  ollama      : available={init['ollama']['available']} "
          f"models={', '.join(init['ollama']['models']) or '(none)'}")
    print(f"  bound model : {bm['model'] or '(none — offline fallback)'}  "
          f"({bm['detail']})")
    print(f"  outputs     : {config.OUTPUT_DIR}")
    print(f"  evidence    : {config.EVIDENCE_DIR}")
    print(f"  ollama active: {llm.status()['active']}   email: {mailer.status()['mode']}\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
