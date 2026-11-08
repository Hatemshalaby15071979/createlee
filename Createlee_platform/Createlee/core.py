"""Createlee core engine.

Deterministic, CSV-schema-driven document generation for a telecom call-centre
operations team. No LLM is involved in structuring data: everything comes from
questions.csv, mapping-table.template.csv and the uploaded data files.

Supported output formats : csv, txt, json, pdf, docx
Supported domains        : QA, WFM, INCIDENT, TRAINING, AI_INVENTORY, SOP,
                           KNOWLEDGE_BASE (extensible purely by editing the CSVs)
Time standard            : ISO-8601 / UTC (e.g. 2026-11-06T05:50:23Z)
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import re
import statistics
import subprocess
from collections import OrderedDict
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

import config

# --------------------------------------------------------------------------- #
# Time
# --------------------------------------------------------------------------- #
def iso_now() -> str:
    """Full ISO-8601 UTC, second precision, Z suffix."""
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def compact_stamp() -> str:
    """ISO-8601 basic UTC for filenames: 20261106T055023Z."""
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def safe_name(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(text)).strip("_")[:80] or "document"


# --------------------------------------------------------------------------- #
# CSV schema
# --------------------------------------------------------------------------- #
QUESTIONS_COLUMNS = ["question_id", "domain", "document_type", "section", "prompt",
                     "answer_type", "required", "weight", "options", "default_value", "tags"]
MAPPING_COLUMNS = ["mapping_id", "domain", "document_type", "source_file", "source_field",
                   "target_field", "data_type", "transform", "format", "required",
                   "default_value", "validation", "notes"]

DOMAIN_LABELS = {
    "QA": "Quality Assurance",
    "WFM": "Workforce Management",
    "INCIDENT": "Incident Management",
    "TRAINING": "Training & Enablement",
    "AI_INVENTORY": "AI Systems Inventory",
    "SOP": "Standard Operating Procedure",
    "KNOWLEDGE_BASE": "Knowledge Base",
}

DEFAULT_SECTIONS = {
    "QA": ["Identification", "Compliance & Security", "Customer Experience",
           "Resolution & Closing", "Scoring Summary"],
    "WFM": ["Forecast Summary", "Staffing Requirement", "Shift Roster",
            "Adherence & Shrinkage", "Approval"],
    "INCIDENT": ["Incident Identification", "Impact Assessment", "Timeline (ISO-8601)",
                 "Root Cause", "Containment & Resolution", "Post-Incident Actions"],
    "TRAINING": ["Course Overview", "Learning Objectives", "Module Content",
                 "Assessment", "Attendance & Sign-off"],
    "AI_INVENTORY": ["Register Overview", "System Details", "Data & Model",
                     "Risk Classification", "Human Oversight", "Compliance & Review"],
    "SOP": ["Purpose & Scope", "Roles & Responsibilities", "Procedure",
            "Escalation Matrix", "Exceptions", "Revision History"],
    "KNOWLEDGE_BASE": ["Article Metadata", "Summary", "Symptoms", "Diagnosis",
                       "Resolution Steps", "Related Articles", "Review Cycle"],
}

FORMATS = ("csv", "txt", "json", "pdf", "docx")

TITLE_OVERRIDES = {
    "qa_scorecard": "Quality Assurance Scorecard",
    "qa_calibration_sheet": "QA Calibration Sheet",
    "wfm_schedule": "Workforce Management Schedule & Adherence",
    "incident_report": "Telecom Incident Report",
    "incident_log": "Incident Log Register",
    "training_material": "Training Material & Assessment Record",
    "ai_inventory_register": "AI Systems Inventory Register",
    "ai_governance_checklist": "AI Governance & Human Oversight Checklist",
    "sop_document": "Standard Operating Procedure",
    "kb_article": "Knowledge Base Article Record",
}


def document_title(doc_type: str) -> str:
    return TITLE_OVERRIDES.get(doc_type, doc_type.replace("_", " ").title())


class SchemaError(Exception):
    pass


def _read_csv(path: Path) -> list[dict]:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", errors="replace")
    sample = text[:4096]
    try:
        delim = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        delim = ","
    return [dict(r) for r in csv.DictReader(text.splitlines(), delimiter=delim)]


def _norm(key: str) -> str:
    """Normalise a CSV header so 'Source Field', 'source_field', 'SOURCE-FIELD' match."""
    return re.sub(r"[^a-z0-9]+", "", str(key or "").lower())


# Columns that are answer/checkbox cells in a checklist CSV (never aliases).
RESPONSE_TOKENS = {"yes", "partly", "no", "na", "n/a", "notapplicable", "pass", "fail",
                   "partial", "y", "n", "true", "false", "compliant", "noncompliant"}

Q_ALIASES = {_norm(c): c for c in QUESTIONS_COLUMNS}
Q_ALIASES.update({
    "ref": "question_id", "id": "question_id", "qid": "question_id",
    "controlid": "question_id", "controlref": "question_id", "itemid": "question_id",
    "question": "prompt", "questiontext": "prompt", "criteria": "prompt",
    "criterion": "prompt", "item": "prompt", "check": "prompt", "control": "prompt",
    "area": "domain", "category": "domain",
    "document": "document_type", "targetdocument": "document_type",
    "doc": "document_type", "form": "document_type", "template": "document_type",
    "subsection": "section", "group": "section", "grouping": "section",
    "controlfamily": "section", "family": "section",
    "type": "answer_type", "responsetype": "answer_type",
    "mandatory": "required", "score": "weight", "points": "weight",
    "choices": "options", "values": "options",
    "default": "default_value", "answer": "default_value",
    "labels": "tags",
})
Q_EXTRAS = {"owner", "evidence", "notes", "controlfamily", "reference", "sla", "category"}

M_ALIASES = {_norm(c): c for c in MAPPING_COLUMNS}
M_ALIASES.update({
    "id": "mapping_id", "ref": "mapping_id",
    "area": "domain", "category": "domain",
    "document": "document_type", "targetdocument": "document_type",
    "doc": "document_type", "form": "document_type", "template": "document_type",
    "source": "source_file", "file": "source_file", "inputfile": "source_file",
    "sourcecolumn": "source_field", "inputfield": "source_field", "from": "source_field",
    "targetcolumn": "target_field", "outputfield": "target_field", "to": "target_field",
    "type": "data_type", "conversion": "transform",
    "outputformat": "format", "mandatory": "required",
    "default": "default_value", "rule": "validation",
    "description": "notes", "comment": "notes",
})

CHECKLIST_DOMAIN = "AI_INVENTORY"
CHECKLIST_DOC_TYPE = "ai_governance_checklist"
CHECKLIST_SECTION = "AI Oversight Checklist Items"


def _canon(rows: list[dict], header: list[str], aliases: dict, columns: list[str]) -> list[dict]:
    out = []
    for r in rows:
        d = {c: "" for c in columns}
        for h in header:
            n = _norm(h)
            if n in RESPONSE_TOKENS:
                continue
            key = aliases.get(n)
            v = r.get(h)
            v = "" if v is None else str(v).strip()
            if key and key in d:
                d[key] = v
            elif n in Q_EXTRAS:
                d[n] = v
        out.append(d)
    return out


def load_questions(path: Path) -> list[dict]:
    """Accept BOTH the canonical 11-column schema and a plain checklist CSV
    (Ref | Question | Yes | Partly | No). Header names are alias-tolerant.
    """
    rows = _read_csv(Path(path))
    if not rows:
        raise SchemaError("questions.csv is empty")
    header = list(rows[0].keys())
    norms = [_norm(h) for h in header]
    responses = [h.strip() for h, n in zip(header, norms) if n in RESPONSE_TOKENS]
    checklist_mode = ("question" in norms or "questiontext" in norms) and "prompt" not in norms

    if checklist_mode:
        result = []
        for i, r in enumerate(rows):
            d = {c: "" for c in QUESTIONS_COLUMNS}
            for h in header:
                n = _norm(h)
                v = "" if r.get(h) is None else str(r.get(h)).strip()
                if n in RESPONSE_TOKENS:
                    continue
                key = Q_ALIASES.get(n)
                if key and key in d:
                    d[key] = v
                elif n in Q_EXTRAS:
                    d[n] = v
                elif n in ("ref", "id", "qid", "controlid", "controlref", "itemid") and not d["question_id"]:
                    d["question_id"] = v
                elif n in ("question", "questiontext") and not d["prompt"]:
                    d["prompt"] = v
            d["question_id"] = d["question_id"] or f"Q-{i+1:03d}"
            d["prompt"] = d["prompt"] or d["question_id"]
            d["domain"] = (d["domain"] or CHECKLIST_DOMAIN).upper()
            d["document_type"] = (d["document_type"] or CHECKLIST_DOC_TYPE).strip().lower().replace(" ", "_")
            d["section"] = d["section"] or CHECKLIST_SECTION
            d["answer_type"] = d["answer_type"] or "choice"
            d["options"] = d["options"] or "|".join(responses or ["Yes", "Partly", "No"])
            d["required"] = d["required"] or "true"
            d["tags"] = d["tags"] or "checklist;ai-governance"
            d["_response_columns"] = responses or ["Yes", "Partly", "No"]
            d["_checklist"] = True
            try:
                d["_weight"] = float(d["weight"] or 1)
            except ValueError:
                d["_weight"] = 1.0
            result.append(d)
        return [r for r in result if r["prompt"]]

    # canonical / alias-tolerant path
    result = _canon(rows, header, Q_ALIASES, QUESTIONS_COLUMNS)
    if not any(r.get("prompt") for r in result):
        raise SchemaError(
            "questions.csv has no question text column. Use either the canonical schema "
            "(question_id, domain, document_type, section, prompt, answer_type, required, "
            "weight, options, default_value, tags) or a checklist (Ref, Question, Yes, Partly, No).")
    for i, r in enumerate(result):
        r["question_id"] = r["question_id"] or f"Q-{i+1:03d}"
        r["domain"] = (r["domain"] or "GENERAL").upper()
        r["document_type"] = (r["document_type"] or "general_document").strip().lower().replace(" ", "_")
        r["section"] = r["section"] or "Details"
        r["answer_type"] = r["answer_type"] or "text"
        r["required"] = r["required"] or "true"
        r["_checklist"] = False
        r["_response_columns"] = []
        try:
            r["_weight"] = float(r["weight"] or 0)
        except ValueError:
            r["_weight"] = 0.0
    return [r for r in result if r["prompt"]]


def load_mapping(path: Path) -> list[dict]:
    """Only source_field + target_field are mandatory; all other columns are optional.
    Empty domain / document_type act as wildcards."""
    rows = _read_csv(Path(path))
    if not rows:
        raise SchemaError("mapping-table.template.csv is empty")
    header = list(rows[0].keys())
    result = _canon(rows, header, M_ALIASES, MAPPING_COLUMNS)
    if not any(r.get("source_field") and r.get("target_field") for r in result):
        raise SchemaError(
            "mapping-table.template.csv needs at least 'source_field' and 'target_field' columns.")
    for i, r in enumerate(result):
        r["mapping_id"] = r["mapping_id"] or f"M-{i+1:03d}"
        r["domain"] = (r["domain"] or "").upper()
        r["document_type"] = (r["document_type"] or "").strip().lower().replace(" ", "_")
        r["source_file"] = r["source_file"] or ""
        r["transform"] = r["transform"] or "none"
        r["format"] = r["format"] or ""
        r["required"] = r["required"] or "false"
    return [r for r in result if r["source_field"] and r["target_field"]]


# --------------------------------------------------------------------------- #
# Uploaded-file analysis
# --------------------------------------------------------------------------- #
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?$")
E164_RE = re.compile(r"^\+\d{7,15}$")


def _detect_format(values: list[str]) -> str:
    vals = [v for v in values if v not in ("", None)]
    if not vals:
        return "empty"
    if all(ISO_DATE_RE.match(v) for v in vals):
        return "ISO-8601 date/timestamp"
    if all(E164_RE.match(v) for v in vals):
        return "E.164 international number"
    if all(re.fullmatch(r"-?\d+", v) for v in vals):
        return "integer"
    if all(re.fullmatch(r"-?\d+\.\d+", v) for v in vals):
        return "decimal"
    if all(v.lower() in ("true", "false", "yes", "no", "1", "0") for v in vals):
        return "boolean"
    if all(v.endswith("%") for v in vals):
        return "percentage"
    return "text"


def _numeric_stats(values: list[str]) -> dict | None:
    nums = []
    for v in values:
        try:
            nums.append(float(str(v).replace(",", "").replace("%", "")))
        except (ValueError, TypeError):
            pass
    if len(nums) < max(1, len(values) // 2):
        return None
    return {"count": len(nums), "sum": round(sum(nums), 4), "min": min(nums),
            "max": max(nums), "mean": round(statistics.fmean(nums), 4)}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _tabular(name: str, columns: list[str], rows: list[list[str]], path: Path,
             extra: dict | None = None) -> dict:
    cols = [str(c).strip() for c in columns]
    norm = [[("" if v is None else str(v)) for v in r][:len(cols)] for r in rows]
    norm = [r + [""] * (len(cols) - len(r)) for r in norm]
    col_report = []
    for i, c in enumerate(cols):
        vals = [r[i] for r in norm]
        col_report.append({"column": c, "detected_format": _detect_format(vals),
                           "non_empty": sum(1 for v in vals if v.strip()),
                           "distinct": len(set(vals)), "numeric": _numeric_stats(vals)})
    out = {"filename": name, "extension": path.suffix.lower(), "size_bytes": path.stat().st_size,
           "sha256_16": _sha256(path), "kind": "tabular", "rows": len(norm), "columns": cols,
           "column_count": len(cols), "column_report": col_report,
           "sample_rows": norm[:5], "analyzed_at_iso8601": iso_now(), "records": []}
    for r in norm:
        out["records"].append(dict(zip(cols, r)))
    if extra:
        out.update(extra)
    return out


def analyze_file(path: Path) -> dict:
    """Analyse any supported upload. Never raises for a bad file."""
    path = Path(path)
    ext = path.suffix.lower()
    try:
        if ext in (".csv", ".tsv"):
            rows = _read_csv(path)
            cols = list(rows[0].keys()) if rows else []
            matrix = [[r.get(c, "") for c in cols] for r in rows]
            return _tabular(path.name, cols, matrix, path)

        if ext == ".xlsx":
            import openpyxl
            wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
            sheets = []
            for ws in wb.worksheets:
                vals = list(ws.values)
                if not vals:
                    continue
                cols = [str(c) if c is not None else f"col{i}" for i, c in enumerate(vals[0])]
                matrix = [["" if v is None else str(v) for v in row] for row in vals[1:]]
                rep = _tabular(path.name, cols, matrix, path, {"sheet": ws.title})
                sheets.append(rep)
            wb.close()
            base = sheets[0] if sheets else _tabular(path.name, [], [], path)
            base["sheets"] = [{"sheet": s.get("sheet"), "rows": s["rows"],
                               "columns": s["column_count"]} for s in sheets]
            return base

        if ext == ".json":
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            if isinstance(data, list) and data and all(isinstance(x, dict) for x in data):
                cols = list(data[0].keys())
                matrix = [[x.get(c, "") for c in cols] for x in data]
                return _tabular(path.name, cols, matrix, path, {"kind": "json-array"})
            if isinstance(data, dict):
                cols = list(data.keys())
                return _tabular(path.name, cols, [[data[c] for c in cols]], path,
                                {"kind": "json-object"})
            return {"filename": path.name, "extension": ext, "kind": "json-scalar",
                    "size_bytes": path.stat().st_size, "sha256_16": _sha256(path),
                    "rows": 0, "columns": [], "column_report": [], "sample_rows": [],
                    "records": [], "analyzed_at_iso8601": iso_now()}

        if ext == ".docx":
            from docx import Document as DocxDocument
            doc = DocxDocument(str(path))
            lines = [p.text for p in doc.paragraphs if p.text.strip()]
            tables = []
            for t in doc.tables:
                tables.append([[c.text for c in row.cells] for row in t.rows])
            return {"filename": path.name, "extension": ext, "kind": "document",
                    "size_bytes": path.stat().st_size, "sha256_16": _sha256(path),
                    "paragraphs": len(lines), "rows": len(lines), "tables": len(tables),
                    "columns": [], "column_report": [], "sample_rows": [lines[:5]],
                    "text_preview": "\n".join(lines)[:2000], "records": [],
                    "analyzed_at_iso8601": iso_now()}

        if ext == ".pdf":
            text = ""
            try:
                proc = subprocess.run(["pdftotext", "-layout", str(path), "-"],
                                      capture_output=True, timeout=30)
                text = proc.stdout.decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                text = ""
            lines = [l for l in text.splitlines() if l.strip()]
            return {"filename": path.name, "extension": ext, "kind": "document",
                    "size_bytes": path.stat().st_size, "sha256_16": _sha256(path),
                    "rows": len(lines), "paragraphs": len(lines), "characters": len(text),
                    "columns": [], "column_report": [], "sample_rows": [lines[:5]],
                    "text_preview": text[:2000], "records": [],
                    "analyzed_at_iso8601": iso_now(),
                    "note": "Text extracted with pdftotext; scanned/image PDFs yield no text."}

        # txt / md / log
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        return {"filename": path.name, "extension": ext, "kind": "text",
                "size_bytes": path.stat().st_size, "sha256_16": _sha256(path),
                "rows": len(lines), "characters": len(text), "words": len(text.split()),
                "columns": [], "column_report": [], "sample_rows": [lines[:5]],
                "text_preview": text[:2000], "records": [],
                "analyzed_at_iso8601": iso_now()}
    except Exception as exc:  # noqa: BLE001 - one bad upload must not break the batch
        return {"filename": path.name, "extension": ext, "kind": "unreadable",
                "error": f"{type(exc).__name__}: {exc}", "rows": 0, "columns": [],
                "column_report": [], "sample_rows": [], "records": [],
                "analyzed_at_iso8601": iso_now()}


def load_datasets(paths: list[Path], analyses: list[dict]) -> dict[str, dict]:
    """Map filename -> dataset with records. Reuses analysis results."""
    out: dict[str, dict] = {}
    for a in analyses:
        if a.get("records"):
            out[a["filename"]] = {"columns": a.get("columns", []),
                                  "records": a["records"], "rows": a.get("rows", 0),
                                  "analysis": a}
            key = a["filename"].lower()
            out.setdefault(key, out[a["filename"]])
    return out


# --------------------------------------------------------------------------- #
# Document building
# --------------------------------------------------------------------------- #
def available_documents(questions: list[dict], mappings: list[dict]) -> list[dict]:
    seen: OrderedDict[tuple[str, str], dict] = OrderedDict()
    for r in list(questions) + list(mappings):
        key = (r["domain"] or "GENERAL", (r.get("document_type") or "").strip() or "general_document")
        if key not in seen:
            seen[key] = {"domain": key[0], "document_type": key[1],
                         "label": DOMAIN_LABELS.get(key[0], key[0].title()),
                         "criteria_count": 0, "mapping_count": 0}
    for q in questions:
        k = (q["domain"] or "GENERAL", (q.get("document_type") or "").strip() or "general_document")
        if k in seen:
            seen[k]["criteria_count"] += 1
    for m in mappings:
        d = m["domain"] or "GENERAL"
        t = (m.get("document_type") or "").strip() or "general_document"
        if (d, t) in seen:
            seen[(d, t)]["mapping_count"] += 1
    return list(seen.values())


def is_wildcard(value: str) -> bool:
    return (value or "").strip().upper() in ("", "ALL", "*", "ANY")


def _apply_transform(value: str, transform: str, fmt: str, default: str) -> str:
    v = (value or "").strip()
    if not v:
        v = default or ""
    t = (transform or "none").lower()
    if t == "upper":
        v = v.upper()
    elif t == "lower":
        v = v.lower()
    elif t == "title":
        v = v.title()
    elif t == "trim":
        v = v.strip()
    elif t == "iso8601":
        v = iso_now() if not v else v
    elif t in ("percent", "decimal2"):
        try:
            v = f"{float(v):.2f}"
        except ValueError:
            pass
    elif t == "integer":
        try:
            v = str(int(float(v)))
        except ValueError:
            pass
    if fmt and fmt.lower() == "iso8601":
        v = iso_now() if not v else v
    return v


def _pick_dataset(mappings: list[dict], datasets: dict) -> tuple[str, list[dict]]:
    counts: dict[str, int] = {}
    for m in mappings:
        f = (m.get("source_file") or "").strip()
        if f and f.lower() in datasets:
            counts[f.lower()] = counts.get(f.lower(), 0) + 1
    if counts:
        key = max(counts, key=counts.get)
        return key, datasets[key]["records"]
    # fallback: first dataset with records, excluding the two schema files
    for key, ds in datasets.items():
        if ds["records"] and key.lower() not in ("questions.csv", "mapping-table.template.csv"):
            return key, ds["records"]
    return "", []


def build_document(domain: str, doc_type: str, questions: list[dict], mappings: list[dict],
                   datasets: dict, analyses: list[dict], options: dict | None = None,
                   references: dict | None = None, review_status: str = "PENDING_APPROVAL") -> dict:
    options = options or {}
    now = iso_now()
    qs = [q for q in questions if q["domain"] == domain and
          (q.get("document_type") or "").strip() == doc_type]
    ms = [m for m in mappings
          if (m["domain"] == domain or is_wildcard(m["domain"])) and
          ((m.get("document_type") or "").strip() == doc_type or
           is_wildcard(m.get("document_type") or ""))]

    checklist = bool(qs) and all(q.get("_checklist") for q in qs)
    sections: list[dict] = []
    section_names = list(OrderedDict.fromkeys(
        [(q.get("section") or "").strip() for q in qs if (q.get("section") or "").strip()]))
    if not section_names:
        section_names = DEFAULT_SECTIONS.get(domain, ["Details"])

    total_weight = sum(q["_weight"] for q in qs) or 0.0
    for sname in section_names:
        sq = [q for q in qs if (q.get("section") or "").strip() == sname]
        fields = []
        if not checklist:
            for q in sq:
                val = (q.get("default_value") or "").strip() or "— (to be completed at review)"
                fields.append({"label": q.get("prompt") or q.get("question_id"),
                               "value": val, "type": q.get("answer_type") or "text",
                               "required": q.get("required"), "weight": q["_weight"],
                               "question_id": q.get("question_id")})
        sections.append({"heading": sname, "fields": fields, "table": None, "paragraphs": []})

    # Table: mapping-driven, or auto-built checklist when no mapping matches.
    src_name, src_records = _pick_dataset(ms, datasets)
    table = None
    records: list[dict] = []
    if checklist and not ms:
        resp = [str(c) for c in (qs[0].get("_response_columns") or ["Yes", "Partly", "No"])]
        cols = ["Ref", "Question"] + resp + ["Evidence / Notes", "Owner"]
        rows = []
        for s in sections:
            sq = [q for q in qs if (q.get("section") or "").strip() == s["heading"]]
            if not sq:
                continue
            srows = [[q["question_id"], q["prompt"]] + ["[  ]"] * len(resp) +
                     [q.get("evidence", ""), q.get("owner", "")] for q in sq]
            s["table"] = {"columns": cols, "rows": srows,
                          "source_file": "questions.csv (checklist schema auto-detected)",
                          "row_count": len(srows)}
            rows.extend(srows)
        records = [dict(zip(cols, r)) for r in rows]
        sections.append({
            "heading": "Checklist Completion Summary",
            "fields": [
                {"label": "Total assessment items", "value": str(len(qs)), "type": "number"},
                {"label": "Response scale", "value": " | ".join(resp), "type": "text"},
                {"label": "Items answered", "value": "0 — all responses blank, to be completed at review", "type": "text"},
                {"label": "Completion rate", "value": "0%", "type": "text"},
                {"label": "Reviewer name / sign-off", "value": "— (to be completed at review)", "type": "text"},
                {"label": "Review date (ISO-8601 UTC)", "value": "— (to be completed at review)", "type": "timestamp"},
            ],
            "table": None, "paragraphs": [],
        })
    elif ms:
        cols = [(m.get("target_field") or m.get("source_field") or "field").strip() for m in ms]
        if src_records:
            rows = []
            for rec in src_records[:500]:
                row = []
                for m in ms:
                    raw = rec.get((m.get("source_field") or "").strip(), "")
                    val = _apply_transform(str(raw), m.get("transform", ""),
                                           m.get("format", ""), m.get("default_value", ""))
                    if not val and _norm(m.get("source_field", "")) in RESPONSE_TOKENS:
                        val = "[  ]"
                    row.append(val)
                rows.append(row)
                records.append(dict(zip(cols, row)))
        else:
            rows = [[_apply_transform("", m.get("transform", ""), m.get("format", ""),
                                      m.get("default_value", "")) for m in ms]]
            records.append(dict(zip(cols, rows[0])))
        table = {"columns": cols, "rows": rows, "source_file": src_name or "(no matching upload; defaults used)",
                 "row_count": len(rows)}
        target = next((s for s in sections if "detail" in s["heading"].lower()
                       or "overview" in s["heading"].lower()
                       or "identification" in s["heading"].lower()), None)
        if target is None:
            target = sections[0]
        target["table"] = table

    # Real numeric analysis of the uploaded files
    metrics = []
    for a in analyses:
        for c in a.get("column_report", []):
            n = c.get("numeric")
            if n:
                metrics.append([a["filename"], c["column"], c["detected_format"],
                                str(n["count"]), str(n["sum"]), str(n["mean"]),
                                str(n["min"]), str(n["max"])])
    sections.append({
        "heading": "Generation Metadata & Source Analysis",
        "fields": [
            {"label": "Generated at (ISO-8601 UTC)", "value": now, "type": "timestamp"},
            {"label": "Time standard", "value": "ISO-8601 / UTC (RFC 3339 profile)", "type": "text"},
            {"label": "Schema version", "value": config.SCHEMA_VERSION, "type": "text"},
            {"label": "Generator", "value": f"{config.PLATFORM_NAME} / {config.AGENT_NAME}", "type": "text"},
            {"label": "Review status", "value": review_status, "type": "text"},
            {"label": "Source files analysed", "value": ", ".join(a["filename"] for a in analyses) or "(none)", "type": "text"},
            {"label": "Criteria (questions.csv)", "value": f"{len(qs)} criteria for this document / {len(questions)} total", "type": "text"},
            {"label": "Mappings applied", "value": f"{len(ms)} field mappings / {len(mappings)} total", "type": "text"},
            {"label": "Total scoring weight", "value": str(total_weight) if total_weight else "n/a", "type": "number"},
        ],
        "table": {"columns": ["Source file", "Column", "Detected format", "N", "Sum", "Mean", "Min", "Max"],
                  "rows": metrics[:40], "source_file": "uploaded files", "row_count": len(metrics[:40])}
                  if metrics else None,
        "paragraphs": [],
    })

    if references and references.get("references"):
        ref_rows = [[r.get("title", ""), r.get("url", ""), r.get("source", ""),
                     r.get("retrieved_at_iso8601", "")] for r in references["references"]]
        sections.append({
            "heading": "Live Web References (supplementary — verify before use)",
            "fields": [{"label": "Query", "value": references.get("query", ""), "type": "text"},
                       {"label": "Retrieved at (ISO-8601 UTC)", "value": references.get("retrieved_at_iso8601", now), "type": "timestamp"}],
            "table": {"columns": ["Title", "URL", "Source", "Retrieved (ISO-8601)"],
                      "rows": ref_rows, "source_file": "public web", "row_count": len(ref_rows)},
            "paragraphs": [references.get("notice", "")],
        })

    dcode = re.sub(r"[^A-Z0-9]", "", domain.upper())[:4] or "GEN"
    doc_id = ("CL-" + compact_stamp() + "-" + dcode + "-" +
              hashlib.md5(f"{domain}|{doc_type}|{now}".encode()).hexdigest()[:4].upper())
    return {
        "document_id": doc_id,
        "meta": {
            "document_id": doc_id, "title": document_title(doc_type),
            "domain": domain, "domain_label": DOMAIN_LABELS.get(domain, domain),
            "document_type": doc_type, "generated_at_iso8601": now,
            "time_standard": "ISO-8601 / UTC", "schema_version": config.SCHEMA_VERSION,
            "generator": f"{config.PLATFORM_NAME} / {config.AGENT_NAME}",
            "review_status": review_status,
            "source_files": [a["filename"] for a in analyses],
            "source_file_count": len(analyses),
            "include_timestamp": bool(options.get("include_timestamp", True)),
        },
        "sections": sections,
        "records": records,
        "disclaimer": ("Generated deterministically from the uploaded CSV schemas and data. "
                       "Values shown as '— (to be completed at review)' require human input. "
                       "Live web references are supplementary leads, not verified ground truth; "
                       "no automated system can guarantee a 100% match with real-world data. "
                       "Operator review and explicit approval are required before use."),
    }


# --------------------------------------------------------------------------- #
# Exporters
# --------------------------------------------------------------------------- #
def render_preview(doc: dict, max_chars: int = 4000, max_table_rows: int = 12) -> str:
    lines = [f"# {doc['meta']['title']}",
             f"Domain: {doc['meta']['domain_label']} ({doc['meta']['domain']})",
             f"Document ID: {doc['meta']['document_id']}",
             f"Generated: {doc['meta']['generated_at_iso8601']} (ISO-8601 UTC)",
             f"Review status: {doc['meta']['review_status']}", ""]
    for s in doc["sections"]:
        lines.append(f"## {s['heading']}")
        for p in s.get("paragraphs", []):
            if p:
                lines.append(p)
        for f in s.get("fields", []):
            lines.append(f"  - {f['label']}: {f['value']}")
        t = s.get("table")
        if t and t["rows"]:
            lines.append("  | " + " | ".join(t["columns"]) + " |")
            for row in t["rows"][:max_table_rows]:
                lines.append("  | " + " | ".join(str(x)[:500] for x in row) + " |")
            if len(t["rows"]) > max_table_rows:
                lines.append(f"  ... {len(t['rows']) - max_table_rows} more row(s)")
        lines.append("")
    lines.append("NOTE: " + doc["disclaimer"])
    return "\n".join(lines)[:max_chars]


def to_json(doc: dict) -> bytes:
    return json.dumps(doc, indent=2, ensure_ascii=False, default=str).encode("utf-8")


def to_txt(doc: dict) -> bytes:
    # Full export: no truncation of tables (findings must not be silently lost).
    return render_preview(doc, max_chars=10_000_000,
                          max_table_rows=10_000_000).encode("utf-8")


def to_csv(doc: dict) -> bytes:
    meta = doc["meta"]
    prefix = OrderedDict([
        ("_document_id", meta["document_id"]),
        ("_generated_at_iso8601", meta["generated_at_iso8601"]),
        ("_time_standard", meta["time_standard"]),
        ("_domain", meta["domain"]),
        ("_document_type", meta["document_type"]),
        ("_review_status", meta["review_status"]),
        ("_source_files", ";".join(meta["source_files"])),
    ])
    rows = doc["records"]
    if not rows:
        flat = dict(prefix)
        for s in doc["sections"]:
            for f in s.get("fields", []):
                flat[f"{s['heading']} :: {f['label']}"] = f["value"]
        rows = [flat]
    cols = list(prefix.keys())
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for r in rows:
        out = dict(prefix)
        out.update(r)
        w.writerow(out)
    return buf.getvalue().encode("utf-8-sig")


def _pdf_header_footer(canvas, doc_):
    from reportlab.lib.pagesizes import A4
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillGray(0.4)
    w, _h = A4
    canvas.drawString(18, 12, f"Createlee / Engeznee  |  {config.SCHEMA_VERSION}  |  ISO-8601 UTC")
    canvas.drawRightString(w - 18, 12, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


def to_pdf(doc: dict, path: Path) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (HRFlowable, Paragraph, SimpleDocTemplate,
                                    Spacer, Table, TableStyle)

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("CLh1", parent=styles["Heading1"], fontSize=17, spaceAfter=4,
                        textColor=colors.HexColor("#12304a"))
    h2 = ParagraphStyle("CLh2", parent=styles["Heading2"], fontSize=11.5, spaceBefore=11,
                        spaceAfter=5, textColor=colors.HexColor("#1d5c8a"))
    small = ParagraphStyle("CLsmall", parent=styles["Normal"], fontSize=7.6,
                           leading=10, textColor=colors.HexColor("#444444"))
    cell = ParagraphStyle("CLcell", parent=styles["Normal"], fontSize=7.2, leading=9)
    cellb = ParagraphStyle("CLcellb", parent=cell, fontName="Helvetica-Bold",
                           textColor=colors.white)

    def P(t):
        return Paragraph(xml_escape(str(t)).replace("\n", "<br/>"), cell)

    story = []
    m = doc["meta"]
    story.append(Paragraph(xml_escape(m["title"]), h1))
    story.append(Paragraph(f"{xml_escape(m['domain_label'])} &nbsp;|&nbsp; {xml_escape(m['document_type'])}", small))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#1d5c8a"), thickness=1.1,
                            spaceBefore=5, spaceAfter=7))
    meta_rows = [
        ["Document ID", m["document_id"], "Generated (ISO-8601 UTC)", m["generated_at_iso8601"]],
        ["Time standard", m["time_standard"], "Review status", m["review_status"]],
        ["Schema", m["schema_version"], "Source files", str(m["source_file_count"])],
    ]
    mt = Table([[P(c) for c in row] for row in meta_rows], colWidths=[28*mm, 58*mm, 42*mm, 52*mm])
    mt.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9d6e0")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef3f7")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#eef3f7")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(mt)
    story.append(Spacer(1, 5))

    for s in doc["sections"]:
        story.append(Paragraph(xml_escape(s["heading"]), h2))
        for para in s.get("paragraphs", []):
            if para:
                story.append(Paragraph(xml_escape(para), small))
                story.append(Spacer(1, 3))
        fs = s.get("fields", [])
        if fs:
            data = [[Paragraph("Field", cellb), Paragraph("Value", cellb)]]
            for f in fs:
                data.append([P(f["label"]), P(f["value"])])
            ft = Table(data, colWidths=[72*mm, 108*mm], repeatRows=1)
            ft.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d5c8a")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#c9d6e0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f9fb")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ]))
            story.append(ft)
            story.append(Spacer(1, 4))
        t = s.get("table")
        if t and t["rows"]:
            ncol = len(t["columns"])
            width = 180*mm / max(1, ncol)
            data = [[Paragraph(xml_escape(str(c)[:90]), cellb) for c in t["columns"]]]
            for row in t["rows"][:200]:
                data.append([P(str(x)[:180]) for x in row])
            tt = Table(data, colWidths=[width]*ncol, repeatRows=1)
            tt.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#12304a")),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c9d6e0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f7fa")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]))
            story.append(tt)
            story.append(Paragraph(f"Source: {xml_escape(str(t.get('source_file','')))} | rows: {t['row_count']}", small))
            story.append(Spacer(1, 4))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#c9d6e0"), thickness=0.6))
    story.append(Paragraph(xml_escape(doc["disclaimer"]), small))

    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=15*mm, rightMargin=15*mm,
                      topMargin=14*mm, bottomMargin=18*mm,
                      title=m["title"], author="Createlee / Engeznee",
                      subject=f"{m['domain']} {m['document_type']}").build(
        story, onFirstPage=_pdf_header_footer, onLaterPages=_pdf_header_footer)


def to_docx(doc: dict, path: Path) -> None:
    from docx import Document as DocxDocument
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, RGBColor

    d = DocxDocument()
    st = d.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(9.5)

    m = doc["meta"]
    d.add_heading(m["title"], level=0)
    p = d.add_paragraph()
    p.add_run(f"{m['domain_label']}  |  {m['document_type']}").italic = True
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT

    meta = d.add_table(rows=0, cols=2)
    meta.style = "Light Grid Accent 1"
    for k, v in [("Document ID", m["document_id"]),
                 ("Generated (ISO-8601 UTC)", m["generated_at_iso8601"]),
                 ("Time standard", m["time_standard"]),
                 ("Review status", m["review_status"]),
                 ("Schema version", m["schema_version"]),
                 ("Source files", ", ".join(m["source_files"]) or "(none)"),
                 ("Generator", m["generator"])]:
        cells = meta.add_row().cells
        cells[0].text = k
        cells[1].text = str(v)
        for par in cells[0].paragraphs:
            for run in par.runs:
                run.bold = True

    for s in doc["sections"]:
        d.add_heading(s["heading"], level=1)
        for para in s.get("paragraphs", []):
            if para:
                d.add_paragraph(para)
        fs = s.get("fields", [])
        if fs:
            ft = d.add_table(rows=1, cols=2)
            ft.style = "Light Grid Accent 1"
            ft.rows[0].cells[0].text = "Field"
            ft.rows[0].cells[1].text = "Value"
            for f in fs:
                c = ft.add_row().cells
                c[0].text = str(f["label"])
                c[1].text = str(f["value"])
        t = s.get("table")
        if t and t["rows"]:
            tt = d.add_table(rows=1, cols=len(t["columns"]))
            tt.style = "Light Grid Accent 1"
            for i, cname in enumerate(t["columns"]):
                tt.rows[0].cells[i].text = str(cname)
            for row in t["rows"][:200]:
                cells = tt.add_row().cells
                for i, val in enumerate(row):
                    cells[i].text = str(val)[:250]
            d.add_paragraph(f"Source: {t.get('source_file','')} | rows: {t['row_count']}",
                            style="Caption")
    d.add_paragraph()
    note = d.add_paragraph()
    run = note.add_run(doc["disclaimer"])
    run.font.size = Pt(7.5)
    run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    d.core_properties.title = m["title"]
    d.core_properties.author = "Createlee / Engeznee"
    d.core_properties.created = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    d.save(str(path))


def export_document(doc: dict, fmt: str, out_dir: Path,
                    include_timestamp: bool = True) -> Path:
    fmt = fmt.lower().lstrip(".")
    if fmt not in FORMATS:
        raise ValueError(f"Unsupported format '{fmt}'. Allowed: {', '.join(FORMATS)}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dom = doc["meta"]["domain"].lower()
    dtype = doc["meta"]["document_type"].lower()
    if dtype.startswith(dom + "_"):
        dtype = dtype[len(dom) + 1:]
    base = f"{safe_name(dom)}_{safe_name(dtype)}"
    if include_timestamp:
        base += f"_{compact_stamp()}"
    # avoid collisions within the same second
    path = out_dir / f"{base}.{fmt}"
    i = 2
    while path.exists():
        path = out_dir / f"{base}_{i}.{fmt}"
        i += 1
    if fmt == "json":
        path.write_bytes(to_json(doc))
    elif fmt == "csv":
        path.write_bytes(to_csv(doc))
    elif fmt == "txt":
        path.write_bytes(to_txt(doc))
    elif fmt == "pdf":
        to_pdf(doc, path)
    elif fmt == "docx":
        to_docx(doc, path)
    return path
