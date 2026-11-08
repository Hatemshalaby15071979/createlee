"""Createlee Evidence Export (Signoff 90-day operational evidence pack).

Generates the 8 CSV exports with the exact filenames / required columns from the
spec, and validates them WITHOUT ever deleting or rewriting a row.

HONESTY NOTICE
--------------
The bundled generator produces SYNTHETIC example rows derived from Createlee's
bundled sample CSVs. It is a format + coverage fixture, NOT real compliance
evidence. Before any actual signoff, replace these files with genuine exports
from your QA / WFM / incident / training / AI-inventory systems. Every generated
document carries this notice and review_status = EXAMPLE_PREVIEW.

Gaps (blank reviewer, unauthorised escalation, missing contract term, SLA miss,
training not completed, out-of-window events) are deliberately PRESERVED and
reported as findings. Nothing is silently cleaned up.
"""
from __future__ import annotations

import csv
import datetime as dt
import glob
import re
from pathlib import Path

import config
import core

HONESTY = ("Synthetic example exports generated from Createlee bundled sample data. "
           "These are NOT real compliance evidence. Replace with genuine system exports "
           "before any actual signoff. Gaps are preserved and reported, never deleted.")

# --------------------------------------------------------------------------- #
# Spec (Section 2)
# --------------------------------------------------------------------------- #
SPECS = [
    {"n": 1, "filename": "qa_reviews.csv", "glob": "qa_review*.csv",
     "proves": "Every AI-proposed QA action reviewed by a named human",
     "columns": ["ts", "ai_action", "human_action", "reviewer_id", "agent_id"],
     "min_rows": 1},
    {"n": 2, "filename": "ai_audit_log.csv", "glob": "*audit*.csv",
     "proves": "Kill switch / access revocation / access review / retention / PII log checks",
     "columns": ["ts", "actor", "event_type"],
     "min_rows": 1,
     "event_requirements": [("kill_switch or access_revoked", {"kill_switch", "access_revoked"}),
                            ("access_review", {"access_review"}),
                            ("retention_check or pii_log_check", {"retention_check", "pii_log_check"})]},
    {"n": 3, "filename": "ai_approvals.csv", "glob": "*approval*.csv",
     "proves": "AI-proposed decisions named by approver",
     "columns": ["ts", "gate", "decision", "approver_id"],
     "min_rows": 1, "require_ai_proposed": True},
    {"n": 4, "filename": "escalations.csv", "glob": "*escalation*.csv",
     "proves": "Escalations go only to authorised supervisors",
     "columns": ["ts", "escalated_by", "supervisor_id", "authorised"],
     "min_rows": 1},
    {"n": 5, "filename": "role_spec.csv", "glob": "role*spec*.csv",
     "glob_alt": "role*export*.csv",
     "proves": "Named accountable person + least-privilege roster",
     "columns": ["ts", "role", "assigned_to", "is_authorised_supervisor"],
     "min_rows": 1, "require_named_accountable": True},
    {"n": 6, "filename": "ai_inventory.csv", "glob": "*ai*inventory*.csv",
     "proves": "AI provider inventory + signed no-training contract term",
     "columns": ["ts", "row_type", "provider_name"],
     "min_rows": 1, "require_rows": ["provider", "contract_term"]},
    {"n": 7, "filename": "ai_training.csv", "glob": "*training*.csv",
     "proves": "Staff AI-training completed + verified",
     "columns": ["ts", "staff_id", "module_name", "completed"],
     "min_rows": 1, "require_completed_yes": True},
    {"n": 8, "filename": "incident_notifications.csv", "glob": "*incident*.csv",
     "proves": "Incident notifications within SLA with named owner",
     "columns": ["ts", "incident_id", "notified_within_sla", "owner"],
     "min_rows": 1},
]

# Module names accepted by the strict Signoff generator contract (file 7).
# The generator must use one of these EXACT strings; anything else fails.
ALLOWED_MODULES = [
    "Responsible AI", "Prompt Safety", "Data Privacy", "Bias Detection",
    "Model Governance", "Incident Response", "PII Handling", "Access Control",
]

# Column aliases accepted by Signoff (canonical name -> accepted variants)
ALIASES = {
    "ts": ["timestamp", "time", "date", "created_at", "date_time", "datetime"],
    "reviewer_id": ["reviewer", "reviewedBy", "reviewed_by", "approved_by", "approver"],
    "agent_id": ["agent", "handled_by", "handledBy", "employee_id"],
    "approver_id": ["approver", "approved_by", "reviewedBy", "reviewer", "reviewer_id", "actor"],
    "supervisor_id": ["supervisor", "team_lead", "teamLead", "manager"],
    "authorised": ["authorized", "is_authorised", "authorized_flag"],
    "named_accountable": ["accountable", "accountable_named", "accountable_owner"],
    "completed": ["status", "state"],
    "notified_within_sla": ["within_sla", "notification_sla_met"],
}


def _h(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s or "").lower())


def resolve_columns(header: list[str], canonical: list[str]) -> tuple[dict[str, str], list[str], dict[str, str]]:
    """Return (canonical -> actual header, missing canonicals, alias-use map)."""
    lookup: dict[str, str] = {}
    for h in header:
        lookup.setdefault(_h(h), h)
    resolved: dict[str, str] = {}
    missing: list[str] = []
    used_aliases: dict[str, str] = {}
    for c in canonical:
        variants = [c] + ALIASES.get(c, [])
        hit = None
        for v in variants:
            if _h(v) in lookup:
                hit = lookup[_h(v)]
                if _h(v) != _h(c):
                    used_aliases[c] = hit
                break
        if hit:
            resolved[c] = hit
        else:
            missing.append(c)
    return resolved, missing, used_aliases


def parse_ts(value: str) -> dt.datetime | None:
    v = (value or "").strip()
    if not v:
        return None
    try:
        d = dt.datetime.fromisoformat(v.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y",
                "%m/%d/%Y %H:%M", "%Y/%m/%d %H:%M:%S"):
        try:
            return dt.datetime.strptime(v, fmt).replace(tzinfo=dt.timezone.utc)
        except ValueError:
            continue
    return None


def window_bounds(as_of: str) -> tuple[str, str]:
    end = dt.date.fromisoformat(as_of)
    return (end - dt.timedelta(days=90)).isoformat(), end.isoformat()


def default_as_of() -> str:
    return dt.datetime.now(dt.timezone.utc).date().isoformat()


# --------------------------------------------------------------------------- #
# Excel-saved-as-CSV tolerant reader
# --------------------------------------------------------------------------- #
def read_rows(path: Path) -> tuple[list[str], list[dict]]:
    raw = Path(path).read_bytes()

    # Excel workbook genuinely saved with a .csv extension (OOXML zip, "PK").
    # This is NOT text-CSV: openpyxl must decode the binary. Strictly read-only.
    if raw[:4] == b"PK\x03\x04":
        import io as _io
        import warnings as _warnings
        from openpyxl import load_workbook as _load_workbook
        with _warnings.catch_warnings():
            _warnings.simplefilter("ignore")
            wb = _load_workbook(_io.BytesIO(raw), read_only=True, data_only=True)
            ws = wb.worksheets[0]
            grid = [list(r) for r in ws.iter_rows(values_only=True)]
            wb.close()
        if not grid:
            return [], []
        header = ["" if v is None else str(v) for v in grid[0]]
        rows = [dict(zip(header, ["" if v is None else str(v) for v in r]))
                for r in grid[1:]]
        return header, rows

    text = None
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            text = raw.decode("utf-16")
        except UnicodeDecodeError:
            text = None
    if text is None:
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
    reader = csv.DictReader(text.splitlines(), delimiter=delim)
    return (reader.fieldnames or []), [dict(r) for r in reader]


# --------------------------------------------------------------------------- #
# Synthetic export generator (fixture only)
# --------------------------------------------------------------------------- #
def _samples(name: str) -> list[dict]:
    p = config.SAMPLES_DIR / name
    return core._read_csv(p) if p.is_file() else []


def _local(iso_z: str, day_offset: int = 0) -> str:
    """Reformat a Z timestamp as a +02:00 local ISO-8601 instant (example style)."""
    try:
        d = dt.datetime.fromisoformat(iso_z.replace("Z", "+00:00"))
        d += dt.timedelta(days=day_offset)
        d = d.astimezone(dt.timezone(dt.timedelta(hours=2)))
        return d.isoformat(timespec="seconds")
    except Exception:  # noqa: BLE001
        return iso_z


OLD_TS = "2026-07-15T09:00:00+02:00"   # intentionally outside the 90-day window
OLD_TS2 = "2026-07-01T00:00:00+02:00"


def _write(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def generate_exports(out_dir: Path, as_of: str | None = None) -> list[dict]:
    """Write the 8 exact-named CSVs. Derived from bundled sample data (synthetic)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    as_of = as_of or default_as_of()
    calls = _samples("calls.csv")
    agents = _samples("agents.csv")
    incidents = _samples("incidents.csv")
    systems = _samples("ai_systems.csv")
    made = []

    def add(spec, rows, header):
        p = out_dir / spec["filename"]
        _write(p, header, rows)
        made.append({"n": spec["n"], "filename": p.name, "path": str(p),
                     "rows": len(rows), "columns": header,
                     "written_at_iso8601": core.iso_now(), "as_of": as_of})

    # 1 ----------------------------------------------------------------------
    reviewers = ["R-4421", "R-4422", "R-4423", "R-4424"]
    actions = {"BILL_ADJUST": "suggest_refund", "SIM_SWAP": "flag_identity_check",
               "PLAN_CHANGE": "recommend_plan_change", "NETWORK_RESET": "suggest_network_reset",
               "ESCALATE_NOC": "escalate_priority", "COMPLAINT_LOG": "suggest_compensation",
               "NEW_CONTRACT": "suggest_offer", "UPGRADE_HANDSET": "suggest_upgrade"}
    rows = []
    for i, c in enumerate(calls):
        rows.append([_local(c["started_at_iso8601"]),
                     actions.get(c["resolution_code"], "suggest_followup"),
                     "accepted" if i % 5 != 3 else "pending",
                     "" if i in (4, 9) else reviewers[i % len(reviewers)],  # honest gaps
                     c["agent_id"]])
    rows.append([OLD_TS, "escalate_priority", "accepted", "R-4400", "A-1042"])
    add(SPECS[0], rows, ["ts", "ai_action", "human_action", "reviewer_id", "agent_id"])

    # 2 ----------------------------------------------------------------------
    rows = [
        ["2026-10-03T14:00:00+02:00", "ops-lead", "kill_switch"],
        ["2026-10-12T10:30:00+02:00", "sec-admin", "access_revoked"],
        ["2026-10-28T16:45:00+02:00", "sec-admin", "access_revoked"],
        ["2026-10-01T09:00:00+02:00", "wfm-lead", "access_review"],
        ["2026-10-31T09:00:00+02:00", "wfm-lead", "access_review"],
        ["2026-10-15T11:20:00+02:00", "dpo-office", "retention_check"],
        ["2026-11-02T08:05:00+02:00", "dpo-office", "pii_log_check"],
        ["2026-10-20T07:40:00+02:00", "ai-ops", "login"],
        ["2026-10-21T07:42:00+02:00", "ai-ops", "config_change"],
        [OLD_TS2, "wfm-lead", "access_review"],  # parsed, excluded from coverage
    ]
    add(SPECS[1], rows, ["ts", "actor", "event_type"])

    # 3 ----------------------------------------------------------------------
    # Every ai_proposed decision must name its approver: the strict Signoff
    # contract rejects an empty approver_id on an ai_proposed row.
    gates = ["pricing_change", "refund_approval", "qa_override", "retention_offer",
             "priority_escalation", "account_flag"]
    rows = [[f"2026-10-{4+i:02d}T11:00:00+02:00", gates[i], "ai_proposed",
             f"A-{1042+i}"] for i in range(6)]
    rows += [["2026-10-22T13:15:00+02:00", "refund_approval", "human_approved", "A-1050"],
             ["2026-10-25T15:30:00+02:00", "qa_override", "human_approved", "A-1050"],
             [OLD_TS, "pricing_change", "ai_proposed", "A-1042"]]
    add(SPECS[2], rows, ["ts", "gate", "decision", "approver_id"])

    # 4 ----------------------------------------------------------------------
    sup = ["SUP-09", "SUP-11", "SUP-14"]
    rows = [[f"2026-10-{6+i:02d}T08:30:00+02:00", a["agent_id"], sup[i % 3],
             "no" if i == 3 else "yes"] for i, a in enumerate(agents[:6])]
    rows.append([OLD_TS, agents[0]["agent_id"], "SUP-09", "yes"])
    add(SPECS[3], rows, ["ts", "escalated_by", "supervisor_id", "authorised"])

    # 5 ----------------------------------------------------------------------
    rows = [["2026-10-01T00:00:00+02:00", "AI Ops Lead", "ACCT-01", "yes", "yes"]]
    for i, a in enumerate(agents):
        if a["role"] in ("Team Leader", "QA Analyst", "WFM Analyst"):
            rows.append([f"2026-10-{2+i:02d}T00:00:00+02:00", a["role"], a["agent_id"],
                         "yes" if a["role"] == "Team Leader" else "no", "no"])
    rows.append([OLD_TS2, "Deputy AI Ops Lead", "ACCT-02", "yes", "no"])
    add(SPECS[4], rows, ["ts", "role", "assigned_to", "is_authorised_supervisor",
                         "named_accountable"])

    # 6 ----------------------------------------------------------------------
    # Strict contract: a contract_term row MUST carry the SAME
    # (provider_name, reference) pair as its provider row, and term_or_version
    # MUST be the literal "no_training" — not a date. A provider with no
    # matching term is an honest FINDING, not a failure, and is never deleted.
    rows = []
    for i, s in enumerate(systems):
        rows.append([f"2026-09-{20+i:02d}T00:00:00+02:00", "provider", s["vendor"],
                     s["system_id"], s["model_version"], s["owner"]])
    for i, s in enumerate(systems[:-2]):
        rows.append([f"2026-09-{22+i:02d}T00:00:00+02:00", "contract_term", s["vendor"],
                     s["system_id"], "no_training", s["owner"]])
    add(SPECS[5], rows, ["ts", "row_type", "provider_name", "reference",
                         "term_or_version", "owner"])

    # 7 ----------------------------------------------------------------------
    # Strict contract: exactly four columns (no extra "verified"), completed is
    # lowercase yes/no only (never blank), module_name is drawn from the
    # allowed list. Training not completed is a FINDING, kept visible.
    rows = []
    for i, a in enumerate(agents):
        comp = "no" if i % 4 == 2 else "yes"
        rows.append([f"2026-09-{15+i:02d}T00:00:00+02:00", a["agent_id"],
                     ALLOWED_MODULES[i % len(ALLOWED_MODULES)], comp])
    rows.append([OLD_TS, "ST-331", "Responsible AI", "yes"])
    add(SPECS[6], rows, ["ts", "staff_id", "module_name", "completed"])

    # 8 ----------------------------------------------------------------------
    # Strict contract: owner is never blank. SLA misses stay as honest findings.
    rows = []
    for i, inc in enumerate(incidents):
        within = "no" if inc["severity"] in ("P1", "P2") and i % 3 == 0 else "yes"
        rows.append([_local(inc["detected_at_iso8601"]), inc["incident_id"], within, inc["owner"]])
    rows.append([OLD_TS, "INC-090", "yes", "J-551"])
    add(SPECS[7], rows, ["ts", "incident_id", "notified_within_sla", "owner"])

    return made


# --------------------------------------------------------------------------- #
# Validator — read-only, never rewrites or drops a row
# --------------------------------------------------------------------------- #
def _find(directory: Path, spec: dict) -> Path | None:
    for pattern in (spec["glob"], spec.get("glob_alt", "")):
        if not pattern:
            continue
        hits = [p for p in directory.iterdir()
                if p.is_file() and glob.fnmatch.fnmatch(p.name.lower(), pattern.lower())]
        if hits:
            return sorted(hits)[0]
    return None


def validate_file(spec: dict, directory: Path, as_of: str) -> dict:
    ws, we = window_bounds(as_of)
    start_d, end_d = dt.date.fromisoformat(ws), dt.date.fromisoformat(we)
    res = {"n": spec["n"], "expected_filename": spec["filename"], "glob": spec["glob"],
           "proves": spec["proves"], "required_columns": spec["columns"],
           "filename": None, "found": False, "status": "FAIL", "checks": [],
           "gaps": [], "total_rows": 0, "in_window_rows": 0,
           "out_of_window_rows": 0, "coverage_pct": 0.0,
           "alias_columns_used": {}, "event_types": [], "extra_columns": []}

    path = _find(directory, spec)
    if not path:
        res["checks"].append(["file matching glob present", "FAIL", "no matching file"])
        res["gaps"].append("File missing entirely — cannot be evidenced.")
        return res
    res["found"] = True
    res["filename"] = path.name

    try:
        header, rows = read_rows(path)
    except Exception as exc:  # noqa: BLE001
        res["checks"].append(["file readable as CSV", "FAIL", f"{type(exc).__name__}: {exc}"])
        return res
    res["total_rows"] = len(rows)
    res["checks"].append(["file readable as CSV", "PASS", f"{len(header)} columns, {len(rows)} data rows"])

    resolved, missing, aliases = resolve_columns(header, spec["columns"])
    res["alias_columns_used"] = aliases
    res["extra_columns"] = [h for h in header if _h(h) not in {_h(v) for v in resolved.values()}]
    if aliases:
        res["checks"].append(["column aliases mapped", "PASS",
                              ", ".join(f"{k} <- {v}" for k, v in aliases.items())])
    res["checks"].append(["required columns present", "PASS" if not missing else "FAIL",
                          "all present" if not missing else "missing: " + ", ".join(missing)])
    res["checks"].append([f"at least {spec['min_rows']} data row(s)",
                          "PASS" if len(rows) >= spec["min_rows"] else "FAIL",
                          f"{len(rows)} row(s) — header-only file fails"])

    # coverage (read-only)
    ts_col = resolved.get("ts")
    in_w = out_w = 0
    if ts_col:
        for r in rows:
            d = parse_ts(str(r.get(ts_col, "")))
            if d is None:
                continue
            ud = d.astimezone(dt.timezone.utc).date()
            if start_d <= ud <= end_d:
                in_w += 1
            else:
                out_w += 1
    res["in_window_rows"], res["out_of_window_rows"] = in_w, out_w
    res["coverage_pct"] = round(100.0 * in_w / len(rows), 1) if rows else 0.0
    res["checks"].append(["90-day coverage computed", "PASS",
                          f"{in_w}/{len(rows)} rows in window {ws} .. {we}; "
                          f"{out_w} older row(s) parsed but excluded from coverage"])

    def col(name):
        return resolved.get(name)

    # special checks ---------------------------------------------------------
    if spec.get("event_requirements"):
        ec = col("event_type")
        seen = {str(r.get(ec, "")).strip().lower() for r in rows} if ec else set()
        res["event_types"] = sorted(x for x in seen if x)
        for label, options in spec["event_requirements"]:
            ok = bool(seen & options)
            res["checks"].append([f"event type: {label}", "PASS" if ok else "FAIL",
                                  "present" if ok else "ABSENT — honest finding"])
            if not ok:
                res["gaps"].append(f"Missing audit event type: {label}")

    if spec.get("require_ai_proposed"):
        dc = col("decision")
        hits = [r for r in rows if dc and str(r.get(dc, "")).strip().lower() == "ai_proposed"]
        res["checks"].append([">=1 ai_proposed decision", "PASS" if hits else "FAIL", f"{len(hits)} row(s)"])
        ac = col("approver_id")
        if ac:
            blank = [r for r in hits if not str(r.get(ac, "")).strip()]
            if blank:
                res["gaps"].append(f"{len(blank)} ai_proposed decision(s) with no named approver (W-08).")

    if spec.get("require_named_accountable"):
        nc = next((h for h in header if _h(h) in
                   {_h("named_accountable")} | {_h(a) for a in ALIASES["named_accountable"]}), None)
        if nc:
            yes = [r for r in rows if str(r.get(nc, "")).strip().lower() == "yes"]
            res["checks"].append(["exactly one named_accountable=yes",
                                  "PASS" if len(yes) == 1 else "FAIL", f"{len(yes)} row(s)"])
            if len(yes) != 1:
                res["gaps"].append(f"Expected exactly 1 accountable owner, found {len(yes)}.")
        else:
            res["checks"].append(["named_accountable column present", "FAIL", "column absent"])
            res["gaps"].append("No named_accountable column — accountable person not evidenced.")

    if spec.get("require_rows"):
        rc = col("row_type")
        seen = {str(r.get(rc, "")).strip().lower() for r in rows} if rc else set()
        for want in spec["require_rows"]:
            ok = want in seen
            res["checks"].append([f"row_type '{want}' present", "PASS" if ok else "FAIL",
                                  "present" if ok else "ABSENT"])
        providers = {str(r.get(col("provider_name"), "")).strip() for r in rows
                     if rc and str(r.get(rc, "")).strip().lower() == "provider"}
        contracted = {str(r.get(col("provider_name"), "")).strip() for r in rows
                      if rc and str(r.get(rc, "")).strip().lower() == "contract_term"}
        lacking = sorted(p for p in providers if p and p not in contracted)
        if lacking:
            res["gaps"].append(f"{len(lacking)} provider(s) with no signed no-training contract term: "
                               + ", ".join(lacking))

    if spec.get("require_completed_yes"):
        cc = col("completed")
        yes = [r for r in rows if cc and str(r.get(cc, "")).strip() == "yes"]  # lowercase strict
        wrong_case = [r for r in rows if cc and str(r.get(cc, "")).strip().lower() == "yes"
                      and str(r.get(cc, "")).strip() != "yes"]
        res["checks"].append([">=1 completed=yes (lowercase)", "PASS" if yes else "FAIL",
                              f"{len(yes)} row(s)"])
        if wrong_case:
            res["gaps"].append(f"{len(wrong_case)} row(s) use 'Completed'/'YES' instead of lowercase 'yes'.")
        if cc:
            not_done = [r for r in rows if str(r.get(cc, "")).strip().lower() != "yes"]
            if not_done:
                res["gaps"].append(f"{len(not_done)} staff training row(s) not completed/verified.")

    # generic honest-finding scans ------------------------------------------
    for name in ("reviewer_id", "approver_id", "owner", "supervisor_id", "actor"):
        c = col(name)
        if c:
            blanks = sum(1 for r in rows if not str(r.get(c, "")).strip())
            if blanks:
                res["gaps"].append(f"{blanks} row(s) with blank {name} — not deleted.")
    for name, bad in (("authorised", {"no", "false"}),
                      ("notified_within_sla", {"no", "false"})):
        c = col(name)
        if c:
            n = sum(1 for r in rows if str(r.get(c, "")).strip().lower() in bad)
            if n:
                res["gaps"].append(f"{n} row(s) with {name}=no — control exception, reported not removed.")
    if out_w:
        res["gaps"].append(f"{out_w} event(s) older than 90 days: parsed, excluded from coverage percentages.")

    failed = [c for c in res["checks"] if c[1] == "FAIL"]
    res["status"] = "FAIL" if failed else ("PASS_WITH_FINDINGS" if res["gaps"] else "PASS")
    return res


def validate_all(directory: Path, as_of: str) -> dict:
    ws, we = window_bounds(as_of)
    files = [validate_file(s, Path(directory), as_of) for s in SPECS]
    return {
        "as_of": as_of, "window_start": ws, "window_end": we, "window_days": 90,
        "generated_at_iso8601": core.iso_now(),
        "generator": f"{config.PLATFORM_NAME} / {config.AGENT_NAME}",
        "schema_version": config.SCHEMA_VERSION,
        "directory": str(directory),
        "files": files,
        "summary": {
            "files_expected": len(SPECS),
            "files_found": sum(1 for f in files if f["found"]),
            "passed": sum(1 for f in files if f["status"] == "PASS"),
            "passed_with_findings": sum(1 for f in files if f["status"] == "PASS_WITH_FINDINGS"),
            "failed": sum(1 for f in files if f["status"] == "FAIL"),
            "total_rows_preserved": sum(f["total_rows"] for f in files),
            "total_gaps_reported": sum(len(f["gaps"]) for f in files),
            "rows_deleted": 0,
        },
        "alias_map": ALIASES,
        "disclaimer": HONESTY,
    }


# --------------------------------------------------------------------------- #
# STRICT contract validator — a Python port of the JavaScript acceptance gate
# (opencode_next_step_kit/validate_signoff_csv.mjs). The permissive validator
# above is for real client exports (aliases, extra columns, blank fields are
# reported as findings). THIS validator is the one the *generator* must satisfy:
# exact header, lowercase booleans, no blank owners, backend-specific rules.
# Createlee-generated fixtures must score 0 FAIL here before they are shipped.
# --------------------------------------------------------------------------- #
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$")

# Exact headers the generator must emit — mirrors the JS acceptance SPEC.
# These are WIDER than SPECS["columns"] (which lists only the mandatory subset
# Signoff needs from a real export); a generated fixture must match exactly.
STRICT_HEADERS = {
    "qa_reviews.csv": ["ts", "ai_action", "human_action", "reviewer_id", "agent_id"],
    "ai_audit_log.csv": ["ts", "actor", "event_type"],
    "ai_approvals.csv": ["ts", "gate", "decision", "approver_id"],
    "escalations.csv": ["ts", "escalated_by", "supervisor_id", "authorised"],
    "role_spec.csv": ["ts", "role", "assigned_to", "is_authorised_supervisor",
                      "named_accountable"],
    "ai_inventory.csv": ["ts", "row_type", "provider_name", "reference",
                         "term_or_version", "owner"],
    "ai_training.csv": ["ts", "staff_id", "module_name", "completed"],
    "incident_notifications.csv": ["ts", "incident_id", "notified_within_sla", "owner"],
}


def _strict_read(path: Path) -> list[list[str]]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    return [row for row in csv.reader(text.splitlines()) if row]


def strict_check_file(spec: dict, directory: Path) -> dict:
    expected = STRICT_HEADERS.get(spec["filename"], spec["columns"])
    p = Path(directory) / spec["filename"]
    out = {"filename": spec["filename"], "status": "FAIL", "failures": [], "findings": [],
           "rows": 0, "header_cols": 0, "expected_cols": len(expected),
           "width_mismatch_lines": []}
    if not p.is_file():
        out["failures"].append("file missing")
        return out
    raw = p.read_bytes()
    if raw[:2] == b"PK":
        out["failures"].append("XLSX binary saved as .csv")
        return out
    rows = _strict_read(p)
    if not rows:
        out["failures"].append("empty file")
        return out

    header, data = rows[0], rows[1:]
    out["header_cols"], out["rows"] = len(header), len(data)

    for i, r in enumerate(data):
        if len(r) != len(header):
            out["width_mismatch_lines"].append(i + 2)
    if out["width_mismatch_lines"]:
        out["failures"].append("row-width mismatch on line(s) "
                               + ",".join(map(str, out["width_mismatch_lines"])))
    if not data:
        out["failures"].append("header-only file (0 data rows)")

    if header != expected:
        out["failures"].append("header mismatch — expected: "
                               + ",".join(expected) + " | got: " + ",".join(header))

    def col(name):
        try:
            i = header.index(name)
        except ValueError:
            return None
        return [r[i] if i < len(r) else "" for r in data]

    ts = col("ts")
    if ts is not None:
        bad = [v for v in ts if v and not ISO_RE.match(v)]
        if bad:
            out["failures"].append(f"{len(bad)} invalid ISO-8601 timestamp(s): "
                                   + ", ".join(bad[:3]))

    f = spec["filename"]
    if f == "ai_audit_log.csv":
        e = col("event_type")
        if e is not None:
            groups = [("kill_switch/access_revoked", {"kill_switch", "access_revoked"}),
                      ("access_review", {"access_review"}),
                      ("retention_check/pii_log_check", {"retention_check", "pii_log_check"})]
            for label, opts in groups:
                if not (set(e) & opts):
                    out["failures"].append(f"missing audit event group: {label}")
    elif f == "ai_approvals.csv":
        d, a = col("decision"), col("approver_id")
        if d is not None:
            if "ai_proposed" not in d:
                out["failures"].append("0 rows with decision=ai_proposed")
            if a is not None:
                for i, v in enumerate(d):
                    if v == "ai_proposed" and not a[i]:
                        out["failures"].append(f"ai_proposed row {i + 2} has empty approver_id")
    elif f == "escalations.csv":
        a = col("authorised")
        if a is not None:
            no = sum(1 for v in a if v == "no")
            if no:
                out["findings"].append(f"{no} row(s) with authorised=no — honest control exception, keep it")
            bad = sorted({v for v in a if v not in ("yes", "no")})
            if bad:
                out["failures"].append("authorised must be lowercase yes/no, got: " + ", ".join(bad))
    elif f == "role_spec.csv":
        n = col("named_accountable")
        if n is not None:
            yes = sum(1 for v in n if v == "yes")
            if yes != 1:
                out["failures"].append(f"expected exactly 1 named_accountable=yes, found {yes}")
    elif f == "ai_inventory.csv":
        t, pn, ref, tv, own = (col("row_type"), col("provider_name"),
                               col("reference"), col("term_or_version"), col("owner"))
        if t is not None:
            if "provider" not in t:
                out["failures"].append("0 row_type=provider")
            if "contract_term" not in t:
                out["failures"].append("0 row_type=contract_term")
            if pn is not None and ref is not None and tv is not None:
                providers, contracted = set(), set()
                for i, v in enumerate(t):
                    if v == "provider":
                        providers.add(pn[i])
                    if v == "contract_term":
                        if tv[i] != "no_training":
                            out["failures"].append(
                                f"contract_term row {i + 2}: term_or_version must be "
                                f"no_training (got '{tv[i]}')")
                        if pn[i] == "no_training":
                            out["failures"].append(
                                f"contract_term row {i + 2}: no_training wrongly placed in provider_name")
                        contracted.add(f"{pn[i]}|{ref[i]}")
                for i, v in enumerate(t):
                    if v == "provider" and f"{pn[i]}|{ref[i]}" not in contracted:
                        out["findings"].append(
                            f"provider {pn[i]} has no matching no-training contract term")
            if own is not None and any(not v for v in own):
                out["failures"].append("empty owner field(s)")
    elif f == "ai_training.csv":
        c, m = col("completed"), col("module_name")
        if c is not None:
            bad = sorted({v for v in c if v not in ("yes", "no")})
            if bad:
                out["failures"].append("completed must be lowercase yes/no, got: " + ", ".join(bad))
            if "yes" not in c:
                out["failures"].append("0 rows with completed=yes")
            no = sum(1 for v in c if v == "no")
            if no:
                out["findings"].append(f"{no} training row(s) not completed — honest finding, keep it")
        if m is not None:
            bad = sorted({v for v in m if v not in ALLOWED_MODULES})
            if bad:
                out["failures"].append("module_name not in allowed list: " + ", ".join(bad))
    elif f == "incident_notifications.csv":
        s, o = col("notified_within_sla"), col("owner")
        if s is not None:
            if any(v not in ("yes", "no") for v in s):
                out["failures"].append("notified_within_sla must be lowercase yes/no")
        if o is not None and any(not v for v in o):
            out["failures"].append("empty owner field(s)")

    out["status"] = "FAIL" if out["failures"] else (
        "PASS_WITH_FINDINGS" if out["findings"] else "PASS")
    return out


def validate_strict(directory: Path, as_of: str | None = None) -> dict:
    """Strict generator acceptance gate. verdict == ACCEPTABLE means 0 FAIL."""
    files = [strict_check_file(s, Path(directory)) for s in SPECS]
    return {
        "gate": "strict generator contract (validate_signoff_csv.mjs port)",
        "as_of": as_of or default_as_of(),
        "generated_at_iso8601": core.iso_now(),
        "files": files,
        "summary": {
            "files_expected": len(SPECS),
            "files_found": sum(1 for f in files if f["rows"] > 0),
            "passed": sum(1 for f in files if f["status"] == "PASS"),
            "passed_with_findings": sum(1 for f in files if f["status"] == "PASS_WITH_FINDINGS"),
            "failed": sum(1 for f in files if f["status"] == "FAIL"),
            "total_rows_preserved": sum(f["rows"] for f in files),
            "width_clean": all(not f["width_mismatch_lines"] for f in files),
            "rows_deleted": 0,
            "verdict": "ACCEPTABLE" if all(f["status"] != "FAIL" for f in files)
            else "NOT ACCEPTABLE",
        },
        "note": "Simulated data only. Passing is not real compliance evidence.",
    }


# --------------------------------------------------------------------------- #
# Report as a Createlee document (exportable to csv/txt/json/pdf/docx)
# --------------------------------------------------------------------------- #
def build_report_doc(report: dict, review_status: str = "EXAMPLE_PREVIEW — PENDING OPERATOR REVIEW") -> dict:
    now = core.iso_now()
    doc_id = "CL-" + core.compact_stamp() + "-EVID-" + report["as_of"].replace("-", "")
    meta = {
        "document_id": doc_id, "title": "Signoff Evidence Validation Report",
        "domain": "EVIDENCE", "domain_label": "Operational Evidence Pack",
        "document_type": "evidence_validation_report", "generated_at_iso8601": now,
        "time_standard": "ISO-8601 / UTC", "schema_version": config.SCHEMA_VERSION,
        "generator": f"{config.PLATFORM_NAME} / {config.AGENT_NAME}",
        "review_status": review_status, "source_files": [f["filename"] or f["expected_filename"]
                                                         for f in report["files"]],
        "source_file_count": len(report["files"]), "include_timestamp": True,
        "as_of": report["as_of"], "window_start": report["window_start"],
        "window_end": report["window_end"],
    }
    s = report["summary"]
    summary_rows = [[f["n"], f["expected_filename"], f["filename"] or "MISSING", f["status"],
                     str(f["total_rows"]), str(f["in_window_rows"]), str(f["out_of_window_rows"]),
                     f"{f['coverage_pct']}%", str(len(f["gaps"]))] for f in report["files"]]
    gaps_rows = [[str(f["n"]), f["filename"] or f["expected_filename"], g]
                 for f in report["files"] for g in f["gaps"]]
    checks_rows = [[str(f["n"]), c[0], c[1], c[2]] for f in report["files"] for c in f["checks"]]
    alias_rows = [[k, ", ".join(v)] for k, v in report["alias_map"].items()]

    sections = [
        {"heading": "Scope & As-Of Date",
         "fields": [
             {"label": "As-of date (--as-of)", "value": report["as_of"], "type": "date"},
             {"label": "Coverage window (90 days ending on as-of)",
              "value": f"{report['window_start']} .. {report['window_end']}", "type": "text"},
             {"label": "Window handling", "value": "Events older than 90 days are still parsed but excluded from coverage percentages", "type": "text"},
             {"label": "Generated at (ISO-8601 UTC)", "value": now, "type": "timestamp"},
             {"label": "Review status", "value": review_status, "type": "text"},
             {"label": "Approvals", "value": "No external organisational approval required for this export step; Createlee's own operator review gate still applies", "type": "text"},
         ], "paragraphs": [report["disclaimer"]], "table": None},
        {"heading": "Per-File Results (required columns checked, rows never deleted)",
         "fields": [], "paragraphs": [],
         "table": {"columns": ["#", "Expected filename", "Actual filename", "Status", "Rows",
                               "In window", "Out of window", "Coverage", "Findings"],
                   "rows": summary_rows, "source_file": "8 evidence CSVs", "row_count": len(summary_rows)}},
        {"heading": "Column & Row-Count Checks", "fields": [], "paragraphs": [],
         "table": {"columns": ["File #", "Check", "Result", "Detail"], "rows": checks_rows,
                   "source_file": "validator", "row_count": len(checks_rows)}},
        {"heading": "Honest Findings / Gaps (preserved, not cleaned)",
         "fields": [{"label": "Total gaps reported", "value": str(s["total_gaps_reported"]), "type": "number"},
                    {"label": "Rows deleted", "value": "0", "type": "number"},
                    {"label": "Rows preserved", "value": str(s["total_rows_preserved"]), "type": "number"}],
         "paragraphs": [], "table": {"columns": ["File #", "Filename", "Finding"], "rows": gaps_rows,
                                     "source_file": "validator", "row_count": len(gaps_rows)}},
        {"heading": "Accepted Column Aliases", "fields": [], "paragraphs":
         ["Excel content saved with a .csv extension is supported: UTF-8/UTF-8-BOM/UTF-16/CP1252/Latin-1 encoding and comma / semicolon / tab / pipe delimiters are auto-detected."],
         "table": {"columns": ["Canonical", "Accepted aliases"], "rows": alias_rows,
                   "source_file": "Signoff spec", "row_count": len(alias_rows)}},
    ]
    records = [{
        "_n": f["n"], "expected_filename": f["expected_filename"],
        "actual_filename": f["filename"] or "MISSING", "status": f["status"],
        "required_columns": "|".join(f["required_columns"]),
        "columns_ok": "yes" if not any(c[1] == "FAIL" and "columns" in c[0] for c in f["checks"]) else "no",
        "total_rows": f["total_rows"], "in_window_rows": f["in_window_rows"],
        "out_of_window_rows": f["out_of_window_rows"], "coverage_pct": f["coverage_pct"],
        "findings": len(f["gaps"]), "as_of": report["as_of"],
        "window_start": report["window_start"], "window_end": report["window_end"],
        "generated_at_iso8601": now, "review_status": review_status,
    } for f in report["files"]]
    return {"document_id": doc_id, "meta": meta, "sections": sections,
            "records": records, "disclaimer": report["disclaimer"]}


# --------------------------------------------------------------------------- #
# High-level pack builder — the single entry point used by the app / CLI
# --------------------------------------------------------------------------- #
REPORT_FORMATS = ("csv", "txt", "json", "pdf", "docx")


def write_excel_csv_demo(out_dir: Path) -> Path:
    """Write proof that Excel-content-saved-as-.csv is accepted.

    Two variants in a subfolder (ignored by the validator since it only scans
    top-level files): UTF-8-BOM + semicolon + aliased header, and UTF-16-LE +
    tab delimiter + aliased date column. The validator resolves aliases and
    auto-detects encoding/delimiter on read. Nothing here is rewritten.
    """
    demo = Path(out_dir) / "examples_excel_as_csv"
    demo.mkdir(parents=True, exist_ok=True)

    a = demo / "qa_review_excel_bom_semicolon.csv"
    a.write_bytes(b"\xef\xbb\xbf" + (
        "timestamp;ai_action;human_action;approved_by;employee_id\n"
        "2026-10-05T09:12:00+02:00;escalate_priority;accepted;R-4421;A-773\n"
        "2026-10-06T09:40:00+02:00;suggest_refund;pending;;A-774\n"
    ).encode("utf-8"))

    b = demo / "ai_audit_excel_utf16_tab.csv"
    rows = [["date_time", "actor", "event_type"],
            ["2026-10-03T14:00:00+02:00", "ops-lead", "kill_switch"],
            ["2026-10-01T09:00:00+02:00", "wfm-lead", "access_review"],
            ["2026-10-15T11:20:00+02:00", "dpo-office", "retention_check"]]
    tmp = demo / ".tmp_utf16"
    with tmp.open("w", newline="", encoding="utf-16") as f:
        csv.writer(f, delimiter="\t", lineterminator="\n").writerows(rows)
    b.write_bytes(tmp.read_bytes())
    tmp.unlink(missing_ok=True)

    (demo / "README.txt").write_text(
        "Excel-content-saved-as-.csv tolerance demo\n"
        "=========================================\n\n"
        "These two files prove the reader accepts real-world Excel CSV exports:\n\n"
        "  qa_review_excel_bom_semicolon.csv  UTF-8 BOM + ';' delimiter + aliased headers\n"
        "      timestamp -> ts | approved_by -> reviewer_id | employee_id -> agent_id\n"
        "  ai_audit_excel_utf16_tab.csv      UTF-16 LE + TAB delimiter + date_time -> ts\n\n"
        "Supported: UTF-8 / UTF-8-BOM / UTF-16 / CP1252 / Latin-1 encodings and\n"
        "comma / semicolon / tab / pipe delimiters (auto-detected). Column aliases\n"
        "are resolved automatically. Files are strictly read-only and never rewritten.\n\n"
        "To verify: python3.11 evidence.py --out <folder containing a copy> --validate-only\n",
        encoding="utf-8")
    return demo


def _render_strict_txt(strict: dict) -> str:
    s = strict["summary"]
    lines = [
        "Createlee — STRICT Signoff generator contract check",
        "===================================================",
        "This is the acceptance gate the *generated* fixtures must pass before they",
        "are shipped to a client. It mirrors validate_signoff_csv.mjs exactly.",
        "The permissive validator in the report is for REAL client exports.",
        "",
        f"As-of:                       {strict['as_of']}",
        f"Generated at (ISO-8601 UTC): {strict['generated_at_iso8601']}",
        "",
        "RESULT",
        "------",
        f"Verdict:                     {s['verdict']}",
        f"Files expected:              {s['files_expected']}",
        f"Files found:                 {s['files_found']}",
        f"PASS:                        {s['passed']}",
        f"PASS_WITH_FINDINGS:          {s['passed_with_findings']}",
        f"FAIL:                        {s['failed']}",
        f"Rows preserved:              {s['total_rows_preserved']}",
        f"Width clean:                 {s['width_clean']}",
        f"Rows deleted:                {s['rows_deleted']}",
        "",
        "PER-FILE",
        "--------",
    ]
    for f in strict["files"]:
        lines.append(f"  {f['filename']:<30} {f['status']:<20} rows={f['rows']:>3} "
                     f"header={f['header_cols']}/{f['expected_cols']}")
        for x in f["failures"]:
            lines.append(f"      FAIL: {x}")
        for x in f["findings"]:
            lines.append(f"      FINDING: {x}")
    lines += ["", "NOTE", "----", "  " + strict["note"]]
    return "\n".join(lines) + "\n"


def build_pack(out_dir: Path | str, as_of: str | None = None,
               generate_examples: bool = True,
               formats: tuple[str, ...] = REPORT_FORMATS) -> dict:
    """Build the full evidence pack in `out_dir`.

    generate_examples=True  -> write the 8 synthetic example CSVs first (fixture mode).
    generate_examples=False -> validate whatever evidence CSVs already exist in
                               `out_dir` (real-export mode; nothing is overwritten).

    Either way the validator is strictly read-only: no row is ever deleted or
    rewritten, and gaps are reported as honest findings.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    as_of = as_of or default_as_of()

    generated = []
    demo_dir = None
    if generate_examples:
        generated = generate_exports(out_dir, as_of)
        demo_dir = write_excel_csv_demo(out_dir)

    report = validate_all(out_dir, as_of)
    strict = validate_strict(out_dir, as_of)
    doc = build_report_doc(report)

    # Keep exactly ONE current report set. These are Createlee-generated derived
    # artifacts only — the 8 evidence CSVs are never matched or touched, and no
    # evidence row is ever deleted.
    _stale = re.compile(
        r"evidence_validation_report_\d{8}T\d{6}Z(_\d+)?\.(csv|txt|json|pdf|docx)$")
    for old in out_dir.iterdir():
        if old.is_file() and _stale.fullmatch(old.name):
            old.unlink()

    exported = {}
    for fmt in formats:
        p = core.export_document(doc, fmt, out_dir, include_timestamp=True)
        exported[fmt] = str(p)

    # Raw machine-readable validation data (distinct from the JSON document export)
    data_path = out_dir / "evidence_validation_report_data.json"
    import json as _json
    data_path.write_text(_json.dumps(report, indent=2, ensure_ascii=False, default=str),
                         encoding="utf-8")
    strict_path = out_dir / "VALIDATION_STRICT.json"
    strict_path.write_text(_json.dumps(strict, indent=2, ensure_ascii=False, default=str),
                           encoding="utf-8")
    strict_txt = out_dir / "VALIDATION_STRICT.txt"
    strict_txt.write_text(_render_strict_txt(strict), encoding="utf-8")

    # INDEX.csv — every file in the pack, with ISO-8601 build time
    now = core.iso_now()
    index_path = out_dir / "INDEX.csv"
    with index_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["filename", "kind", "size_bytes", "as_of", "generated_at_iso8601"])
        for p in sorted(out_dir.iterdir()):
            if p.is_file() and p.name != "INDEX.csv":
                if p.name.startswith("evidence_validation_report_") and p.suffix in (".csv", ".txt", ".json", ".pdf", ".docx"):
                    kind = "validation report (document export)"
                elif p.name == "evidence_validation_report_data.json":
                    kind = "raw validation data (JSON)"
                elif p.name.startswith("VALIDATION_STRICT"):
                    kind = "strict generator-contract check"
                elif p.name == "README.txt":
                    kind = "pack readme"
                else:
                    kind = "evidence CSV export"
                w.writerow([p.name, kind, p.stat().st_size, as_of, now])

    # README.txt — human summary, honest boundary, and how to use real exports
    s = report["summary"]
    lines = [
        "Createlee / Engeznee — Signoff Evidence Pack",
        "===========================================",
        "",
        f"As-of date (--as-of):        {report['as_of']}",
        f"Coverage window (90 days):   {report['window_start']} .. {report['window_end']}",
        "Window handling:             Events older than 90 days are still parsed but",
        "                             excluded from coverage percentages.",
        f"Generated at (ISO-8601 UTC): {report['generated_at_iso8601']}",
        f"Generator:                   {report['generator']}  (schema {report['schema_version']})",
        "",
        "RESULT",
        "------",
        f"Files expected:              {s['files_expected']}",
        f"Files found:                 {s['files_found']}",
        f"PASS:                        {s['passed']}",
        f"PASS_WITH_FINDINGS:          {s['passed_with_findings']}",
        f"FAIL:                        {s['failed']}",
        f"Rows preserved:              {s['total_rows_preserved']}",
        f"Gaps reported (honest):      {s['total_gaps_reported']}",
        f"Rows deleted:                {s['rows_deleted']}   (never delete rows to look clean)",
        "",
        "STRICT GENERATOR CONTRACT (the gate the generated fixtures must pass)",
        "----------------------------------------------------------------------",
        f"Verdict:                     {strict['summary']['verdict']}",
        f"PASS:                        {strict['summary']['passed']}",
        f"PASS_WITH_FINDINGS:          {strict['summary']['passed_with_findings']}",
        f"FAIL:                        {strict['summary']['failed']}   (must be 0 before shipping)",
        "",
        "PER-FILE STATUS",
        "---------------",
    ]
    for f in report["files"]:
        lines.append(f"  #{f['n']} {f['filename'] or f['expected_filename']:<30} {f['status']:<20} "
                     f"rows={f['total_rows']:>3}  in-window={f['in_window_rows']:>3}  "
                     f"out={f['out_of_window_rows']}  cov={f['coverage_pct']}%  findings={len(f['gaps'])}")
        lines.append(f"      required columns: {', '.join(f['required_columns'])}")
    lines += [
        "",
        "FILES IN THIS PACK",
        "------------------",
        "  8 evidence CSV exports (exact Section-2 filenames / required columns)",
        "  evidence_validation_report_<ISO8601>.{csv,txt,json,pdf,docx}  — the report in 5 formats",
        "  evidence_validation_report_data.json — raw validation data",
        "  VALIDATION_STRICT.json / VALIDATION_STRICT.txt — strict generator-contract check",
        "  INDEX.csv — manifest of every file with ISO-8601 build time",
        "  README.txt — this file",
    ]
    if demo_dir:
        lines += ["  examples_excel_as_csv/ — proof that Excel-saved-as-.csv works",
                  "      (UTF-8-BOM + ';' + aliases, and UTF-16 + TAB; read-only)"]
    lines += [
        "",
        "COLUMN ALIASES & EXCEL-AS-CSV SUPPORT",
        "-------------------------------------",
        "  Signoff accepts column aliases (see 'Accepted Column Aliases' in the report).",
        "  Excel content saved with a .csv extension is supported: UTF-8 / UTF-8-BOM /",
        "  UTF-16 / CP1252 / Latin-1 encodings and comma / semicolon / tab / pipe",
        "  delimiters are auto-detected on read. Files are never rewritten.",
        "",
        "HOW TO USE WITH YOUR REAL EXPORTS",
        "---------------------------------",
        "  Drop your 8 genuine system exports into this folder using the exact Section-2",
        "  filenames (or matching glob patterns), then re-run the pack in validate-only",
        "  mode: your 8 evidence CSVs are never overwritten (only the derived report,",
        "  INDEX and README are refreshed):",
        "      python3.11 evidence.py --out <this folder> --as-of 2026-11-06 --validate-only",
        "  The 8 CSVs are internal operational exports you already generate; no external",
        "  organisational approval is required to produce them. Createlee's own operator",
        "  review gate still applies before any AI-authored report is saved or emailed.",
        "",
        "HONESTY NOTICE",
        "--------------",
    ]
    for w in _wrap(HONESTY, 96):
        lines.append("  " + w)
    lines += ["", "  Gaps below are preserved and reported, never silently cleaned up:", ""]
    for f in report["files"]:
        for g in f["gaps"]:
            lines.append(f"    - [{f['filename'] or f['expected_filename']}] {g}")
    (out_dir / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {
        "ok": True, "as_of": as_of, "window_start": report["window_start"],
        "window_end": report["window_end"], "out_dir": str(out_dir),
        "generated_files": generated, "report": report, "report_doc": doc,
        "report_document_id": doc["document_id"], "report_exports": exported,
        "index": str(index_path), "readme": str(out_dir / "README.txt"),
        "raw_data": str(data_path), "strict": strict,
        "strict_json": str(strict_path), "strict_txt": str(strict_txt),
        "excel_csv_demo": str(demo_dir) if demo_dir else None,
    }


def _wrap(text: str, width: int) -> list[str]:
    words, out, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            out.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        out.append(cur)
    return out


# --------------------------------------------------------------------------- #
# CLI:  python3.11 evidence.py --out /workspace/evidence_pack --as-of 2026-11-06
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import argparse
    import json as _json

    ap = argparse.ArgumentParser(description="Createlee Signoff evidence pack builder/validator")
    ap.add_argument("--out", default=str(config.EVIDENCE_DIR), help="output directory")
    ap.add_argument("--as-of", default=None, help="YYYY-MM-DD (default: today UTC)")
    ap.add_argument("--validate-only", action="store_true",
                    help="do NOT write example CSVs; validate files already present")
    args = ap.parse_args()
    result = build_pack(args.out, args.as_of, generate_examples=not args.validate_only)
    s = result["report"]["summary"]
    print(f"as-of: {result['as_of']}  window: {result['window_start']} .. {result['window_end']}")
    print(f"out_dir: {result['out_dir']}")
    print(f"summary: {_json.dumps(s, ensure_ascii=False)}")
    for f in result["report"]["files"]:
        print(f"  #{f['n']} {(f['filename'] or f['expected_filename']):<30} {f['status']:<20} "
              f"rows={f['total_rows']:>3} cov={f['coverage_pct']}% findings={len(f['gaps'])}")
    print("report exports: " + ", ".join(f"{k}={Path(v).name}"
                                         for k, v in result["report_exports"].items()))
