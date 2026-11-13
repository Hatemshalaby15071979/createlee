"""Createlee Hand-off Packs — the exact files each project needs, ready to send.

WHY THIS EXISTS
---------------
The operator's workflow is:

    1. Createlee generates a simulated but FORMAT-EXACT file set.
    2. The simulated rows are sent to the client as a filled-in template.
    3. The client replaces ONLY the data rows with their real rows, keeping the
       header, column order and formatting byte-for-byte identical.
    4. The client emails the files back.
    5. Signoff runs against the returned files and the project's production gate
       is evaluated.

For step 3 to be safe the header, column count, dtype conventions and
lowercase yes/no values must be identical between the simulated and the real
file. This module builds one hand-off folder per project so the client knows
exactly what to replace and what to leave alone.

PROJECTS COVERED
----------------
  signoff                 The 8 evidence CSVs that Signoff consumes.
  helix-codex             9 production gate evidence documents + 2 ownership
                          CSVs. 6 of the 9 can ONLY be produced by the client's
                          organisation (certification, audit, architecture, DR,
                          security and legal review) and are shipped as
                          explicitly-marked UNSIGNED templates.
  live-support-assistant  Procedure corpus (>=20) + expected-outcome labels
                          (>=50).
  compliproof             Two reconciled CSV exports + the P0 evidence
                          checklist. 0 of 7 P0 gates are closable by CSV; the
                          checklist says exactly what each one needs.

HONESTY BOUNDARY
----------------
Every generated row is SIMULATED. Nothing here is compliance evidence. The
`cannot_generate` list in each manifest names the evidence Createlee cannot
produce, so the operator can mark those gates honestly open instead of implying
they are closed. No signature is ever fabricated: signed gate documents ship
with `"signature": null` and `"status": "ORG_MUST_COMPLETE"`.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import config
import csv_safe
import core
import evidence
import library

HONESTY = (
    "Simulated, format-exact template data. The client must replace ONLY the data "
    "rows with their own real rows and keep the header, column order and value "
    "conventions unchanged. Passing a validator does not make simulated data real "
    "compliance evidence."
)


# --------------------------------------------------------------------------- #
# Shared writer / manifest helpers
# --------------------------------------------------------------------------- #
def _w(path: Path, header: list[str], rows: list[list]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv_safe.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
    return path


def _json(path: Path, obj) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _rows_of(path: Path) -> int:
    with path.open(encoding="utf-8") as f:
        return max(0, sum(1 for _ in f) - 1)


# --------------------------------------------------------------------------- #
# Project 1 — Signoff (the gate itself): the 8 evidence exports
# --------------------------------------------------------------------------- #
SIGNOFF_FILES = [
    ("qa_reviews.csv", "ts, ai_action, human_action, reviewer_id, agent_id",
     "Every AI-proposed QA action reviewed by a named human"),
    ("ai_audit_log.csv", "ts, actor, event_type",
     "Kill switch / access revocation / access review / retention / PII log checks"),
    ("ai_approvals.csv", "ts, gate, decision, approver_id",
     "AI-proposed decisions named by approver"),
    ("escalations.csv", "ts, escalated_by, supervisor_id, authorised",
     "Escalations go only to authorised supervisors"),
    ("role_spec.csv", "ts, role, assigned_to, is_authorised_supervisor, named_accountable",
     "Named accountable person + least-privilege roster"),
    ("ai_inventory.csv", "ts, row_type, provider_name, reference, term_or_version, owner",
     "AI provider inventory + signed no-training contract term"),
    ("ai_training.csv", "ts, staff_id, module_name, completed",
     "Staff AI-training completed + verified"),
    ("incident_notifications.csv", "ts, incident_id, notified_within_sla, owner",
     "Incident notifications within SLA with named owner"),
]


def build_signoff(out: Path, as_of: str) -> dict:
    project = out / "signoff"
    project.mkdir(parents=True, exist_ok=True)
    made = evidence.generate_exports(project, as_of)
    strict = evidence.validate_strict(project, as_of)
    permissive = evidence.validate_all(project, as_of)
    _json(project / "VALIDATION_STRICT.json", strict)
    (project / "VALIDATION_STRICT.txt").write_text(
        evidence._render_strict_txt(strict), encoding="utf-8")
    _json(project / "VALIDATION_PERMISSIVE.json", permissive)

    files = []
    for f in SIGNOFF_FILES:
        name = f[0]
        p = project / name
        files.append({
            "filename": name,
            "required_columns": f[1],
            "what_it_proves": f[2],
            "min_rows": 1,
            "generated_rows": _rows_of(p) if p.is_file() else 0,
            "client_action": "replace_data_rows_only",
            "validation": "strict + permissive",
        })

    manifest = {
        "project": "signoff",
        "title": "Signoff — 8 operational evidence exports",
        "purpose": "Input B for the Signoff gate. These 8 files are the evidence that "
                   "unblocks the signed_production_evidence gate for Helix-Codex and "
                   "supplies the ownership / on-call gates.",
        "as_of": as_of,
        "generated_at_iso8601": core.iso_now(),
        "files": files,
        "validate_command": "python3.11 evidence.py --out <this folder> --as-of <date> --validate-only",
        "strict_verdict": strict["summary"]["verdict"],
        "strict_failed": strict["summary"]["failed"],
        "cannot_generate": [],
        "note": "All 8 files are generatable as FORMAT-EXACT templates. The ROWS must be "
                "the client's real exports before Signoff can treat them as evidence.",
        "honesty": HONESTY,
    }
    _json(project / "request_manifest.json", manifest)
    return manifest


# --------------------------------------------------------------------------- #
# Project 2 — Helix-Codex: 9 production gates + ownership CSVs
# --------------------------------------------------------------------------- #
HELIX_GATES = [
    ("signed_production_evidence",
     "A cryptographically signed evidence pack produced by an off-system key.",
     "GENERATABLE_PARTIAL",
     {"evidence_pack_id": "", "as_of": "", "window_days": 90,
      "evidence_files": ["qa_reviews.csv", "ai_audit_log.csv", "ai_approvals.csv",
                         "escalations.csv", "role_spec.csv", "ai_inventory.csv",
                         "ai_training.csv", "incident_notifications.csv"],
      "pack_sha256": "", "signer_key_id": "", "signature": None},
     "Createlee produces the 8-file pack. The SIGNATURE must come from a key the "
     "audited system does not hold. Declare the public key to the release gate."),
    ("certified_data_isolation",
     "Independent certification of tenant/data isolation at production scale.",
     "ORG_ONLY",
     {"certifying_body": "", "certification_id": "", "scope": "",
      "test_method": "", "production_scale_evidence": "", "valid_from": "",
      "valid_until": "", "signature": None},
     "Requires a certification body your organisation appoints. No CSV closes this."),
    ("external_observer_audit",
     "Third-party audit of the control plane and audit chain.",
     "ORG_ONLY",
     {"auditor": "", "audit_id": "", "scope": "", "findings": [],
      "opinion": "", "report_sha256": "", "signature": None},
     "Requires an external auditor. No CSV closes this."),
    ("production_deployment_architecture",
     "Approved production deployment topology and review sign-off.",
     "ORG_ONLY",
     {"topology_diagram_sha256": "", "network": "", "tls": "", "ha": "",
      "secrets_management": "", "reviewer": "", "review_date": "", "signature": None},
     "Requires an architecture review by your infrastructure owner."),
    ("disaster_recovery_evidence",
     "Validated DR / backup plan exercised against the production environment.",
     "ORG_ONLY",
     {"dr_test_date": "", "rpo_minutes": None, "rto_minutes": None,
      "restore_log_sha256": "", "operator": "", "signature": None},
     "Requires a real DR test in production. No CSV closes this."),
    ("operational_ownership",
     "Named production operations owner and rotation.",
     "GENERATABLE",
     {"owner_name": "", "role": "", "rotation": "", "accepted_at": "", "signature": None},
     "Createlee supplies role_spec.csv with exactly one named_accountable=yes; "
     "the client fills the name and signs."),
    ("incident_oncall_ownership",
     "Named production on-call and escalation contract.",
     "GENERATABLE_PARTIAL",
     {"oncall_owner": "", "escalation_path": "", "sla_minutes": None,
      "contract_ref": "", "signature": None},
     "Createlee supplies incident_notifications.csv with named owners."),
    ("security_review",
     "Completed independent security review / penetration test.",
     "ORG_ONLY",
     {"reviewer": "", "review_id": "", "scope": "", "findings": [],
      "remediation": "", "report_sha256": "", "signature": None},
     "Requires a signed security review. No CSV closes this."),
    ("legal_privacy_review",
     "Legal and data-privacy review for the production jurisdiction.",
     "ORG_ONLY",
     {"jurisdiction": "", "lawful_basis": "", "dpa_ref": "", "reviewer": "",
      "review_date": "", "signature": None},
     "Requires legal sign-off. No CSV closes this."),
]


def build_helix(out: Path, as_of: str) -> dict:
    project = out / "helix-codex"
    gate_dir = project / "gate-evidence"
    gate_dir.mkdir(parents=True, exist_ok=True)
    made = evidence.generate_exports(project / "signoff-inputs", as_of)

    files = []
    for gate, demand, kind, payload, note in HELIX_GATES:
        obj = {
            "gate": gate,
            "scope": "production",
            "status": "ORG_MUST_COMPLETE" if kind == "ORG_ONLY" else "TEMPLATE",
            "generated_at_iso8601": core.iso_now(),
            "as_of": as_of,
            "demand": demand,
            "payload": payload,
            "signature": None,
            "signature_instruction": (
                "Sign the canonical JSON of this file with an RSA key held OUTSIDE "
                "the audited repository and store <gate>.evidence.json.sig beside it, "
                "also outside the repository. Never commit the private key."),
            "operator_note": note,
            "generated_by": f"{config.PLATFORM_NAME} / {config.AGENT_NAME} — UNSIGNED TEMPLATE",
        }
        _json(gate_dir / f"{gate}.evidence.json", obj)
        files.append({
            "filename": f"gate-evidence/{gate}.evidence.json",
            "kind": kind,
            "client_action": ("owner_completes_and_signs" if kind != "ORG_ONLY"
                              else "org_evidence_only"),
            "what_it_proves": demand,
            "operator_note": note,
        })

    # Ownership / on-call CSVs, sent as filled templates.
    role_rows = [
        ["2026-10-01T00:00:00+02:00", "AI Ops Lead", "ACCT-01", "yes", "yes"],
        ["2026-10-09T00:00:00+02:00", "Team Leader", "A-1049", "yes", "no"],
        ["2026-10-10T00:00:00+02:00", "QA Analyst", "A-1050", "no", "no"],
        ["2026-10-11T00:00:00+02:00", "WFM Analyst", "A-1051", "no", "no"],
    ]
    _w(project / "operational_ownership.csv",
       ["ts", "role", "assigned_to", "is_authorised_supervisor", "named_accountable"],
       role_rows)
    inc_rows = [
        ["2026-11-05T08:42:11+02:00", "INC-20261105-001", "no", "NOC Duty Manager"],
        ["2026-11-05T10:15:00+02:00", "INC-20261105-002", "yes", "CRM Platform Lead"],
        ["2026-11-05T12:05:00+02:00", "INC-20261105-003", "yes", "Network Ops Lead"],
    ]
    _w(project / "incident_oncall_ownership.csv",
       ["ts", "incident_id", "notified_within_sla", "owner"], inc_rows)
    files += [
        {"filename": "operational_ownership.csv",
         "kind": "GENERATABLE", "client_action": "replace_data_rows_only",
         "what_it_proves": "Named accountable person + least-privilege roster",
         "operator_note": "Keep exactly ONE row with named_accountable=yes."},
        {"filename": "incident_oncall_ownership.csv",
         "kind": "GENERATABLE_PARTIAL", "client_action": "replace_data_rows_only",
         "what_it_proves": "Incident/on-call ownership with named owner",
         "operator_note": "Owner is never blank; SLA misses stay as honest findings."},
    ]

    manifest = {
        "project": "helix-codex",
        "title": "Helix-Codex (Helix-Prime) — nine production gates",
        "purpose": "Each gate needs <gate>.evidence.json + .sig stored OUTSIDE the repo, "
                   "scope production, signed with a key the audited system does not hold.",
        "as_of": as_of,
        "generated_at_iso8601": core.iso_now(),
        "files": files,
        "gates_generatable": sum(1 for g in HELIX_GATES if g[2] == "GENERATABLE"),
        "gates_partial": sum(1 for g in HELIX_GATES if g[2] == "GENERATABLE_PARTIAL"),
        "gates_org_only": sum(1 for g in HELIX_GATES if g[2] == "ORG_ONLY"),
        "cannot_generate": [
            "certified_data_isolation — needs an appointed certification body",
            "external_observer_audit — needs an independent auditor",
            "production_deployment_architecture — needs an infrastructure review",
            "disaster_recovery_evidence — needs a real production DR test",
            "security_review — needs a signed independent security review",
            "legal_privacy_review — needs legal sign-off",
        ],
        "honesty": HONESTY,
    }
    _json(project / "request_manifest.json", manifest)
    return manifest


# --------------------------------------------------------------------------- #
# Project 3 — live-support-assistant: corpus + labels
# --------------------------------------------------------------------------- #
CORPUS_COLUMNS = ["doc_id", "title", "content", "tenant_id", "published", "version", "retired"]
LABEL_COLUMNS = ["ticket_id", "tenant_id", "question", "expected_decision",
                 "expected_sop_id", "source"]


def build_live_support(out: Path, as_of: str) -> dict:
    project = out / "live-support-assistant"
    project.mkdir(parents=True, exist_ok=True)

    corpus = library.procedure_records()
    _w(project / "procedure_corpus.csv", CORPUS_COLUMNS, corpus)
    corpus_json = [dict(zip(CORPUS_COLUMNS, r)) for r in corpus]
    _json(project / "procedure_corpus.json",
          {"schema": "procedure_corpus/v1", "generated_at_iso8601": core.iso_now(),
           "as_of": as_of, "documents": corpus_json})

    labels = library.label_records()
    _w(project / "expected_outcome_labels.csv", LABEL_COLUMNS, labels)

    files = [
        {"filename": "procedure_corpus.csv",
         "required_columns": ", ".join(CORPUS_COLUMNS),
         "min_rows": 20, "generated_rows": len(corpus),
         "client_action": "replace_data_rows_keep_doc_ids_unique",
         "what_it_proves": "The SOPs/knowledge base the assistant answers from"},
        {"filename": "procedure_corpus.json",
         "required_columns": "same as CSV (JSON array under 'documents')",
         "min_rows": 20, "generated_rows": len(corpus),
         "client_action": "replace_data_rows_keep_doc_ids_unique",
         "what_it_proves": "Same corpus in JSON form (either form is accepted)"},
        {"filename": "expected_outcome_labels.csv",
         "required_columns": ", ".join(LABEL_COLUMNS),
         "min_rows": 50, "generated_rows": len(labels),
         "client_action": "replace_data_rows",
         "what_it_proves": "Labelled ticket outcomes for evaluation"},
    ]

    manifest = {
        "project": "live-support-assistant",
        "title": "live-support-assistant — corpus + expected-outcome labels",
        "purpose": "The evidence that lets the assistant be evaluated against the "
                   "client's own procedures and a labelled ticket sample.",
        "as_of": as_of,
        "generated_at_iso8601": core.iso_now(),
        "files": files,
        "cannot_generate": [
            "Tenant isolation proof — needs an authenticated cross-tenant negative control",
            "Authenticated end-to-end flow evidence — needs a hosted runtime",
            "Hosted telemetry / escalation transport evidence",
            "External security audit",
            "Billing integration evidence",
            "Per-tenant threshold calibration record (0.18 is a starting point, not validated)",
        ],
        "honesty": HONESTY,
    }
    _json(project / "request_manifest.json", manifest)
    return manifest


# --------------------------------------------------------------------------- #
# Project 4 — CompliProof: two reconciled exports + P0 evidence checklist
# --------------------------------------------------------------------------- #
COMPLIPROOF_P0 = [
    ("P0-1", "Packaging / deployment",
     "wheel manifest; clean-venv install log; docker build log; CI run URL",
     "NO — needs a hosted CI run and a clean-runner install matrix"),
    ("P0-2", "Evidence integrity",
     "tamper test log; seal manifest; independent review",
     "NO — needs an independent reviewer and a non-symmetric key lifecycle"),
    ("P0-3", "Audit ledger",
     "concurrency test; tamper test; external anchor receipt; test-isolation test; ledger inventory",
     "NO — needs an external timestamp anchor receipt (e.g. freetsa)"),
    ("P0-4", "Reporting / reconciliation",
     "golden test suite; served report artifact; CSV parse test; report audit event",
     "PARTIAL — the two CSVs let you run the reconciliation; the served report and audit event must be produced by CompliProof itself"),
    ("P0-5", "Server reporting",
     "route test suite; auth test; security scan",
     "NO — needs routes, auth and a security scan"),
    ("P0-6", "Authentication",
     "auth test suite; session store inspection; RBAC test; security review",
     "NO — needs a real auth implementation and security review"),
    ("P0-7", "Dashboard / UI security",
     "UI test; route inventory; security scan",
     "NO — needs a browser acceptance test and route inventory"),
]


def build_compliproof(out: Path, as_of: str) -> dict:
    project = out / "compliproof"
    project.mkdir(parents=True, exist_ok=True)

    a, b = library._account_rows()
    _w(project / "system_a.csv", ["id", "customer_name", "plan", "status"], a)
    _w(project / "system_b.csv", ["id", "customer_name", "plan", "status"], b)
    rec_rows, rec = library.reconcile(a, b)
    _w(project / "reconciliation_report.csv",
       ["id", "in_system_a", "in_system_b", "customer_name_match",
        "plan_match", "status_match", "finding"], rec_rows)

    _w(project / "P0_EVIDENCE_CHECKLIST.csv",
       ["p0_id", "area", "required_evidence", "closable_by_createlee", "status"],
       [[pid, area, req, close, "OPEN"] for pid, area, req, close in COMPLIPROOF_P0])

    files = [
        {"filename": "system_a.csv",
         "required_columns": "id (key, non-empty, no duplicates) + business columns",
         "min_rows": 1, "generated_rows": len(a),
         "client_action": "replace_data_rows_keep_unique_id",
         "what_it_proves": "System A side of the reconciliation"},
        {"filename": "system_b.csv",
         "required_columns": "id (key, non-empty, no duplicates) + matching business columns",
         "min_rows": 1, "generated_rows": len(b),
         "client_action": "replace_data_rows_keep_unique_id",
         "what_it_proves": "System B side of the reconciliation"},
        {"filename": "reconciliation_report.csv",
         "required_columns": "generated by CompliProof, not filled by the client",
         "min_rows": 1, "generated_rows": len(rec_rows),
         "client_action": "none_generated",
         "what_it_proves": "Expected reconciliation shape (matched / A-only / B-only / mismatched)"},
        {"filename": "P0_EVIDENCE_CHECKLIST.csv",
         "required_columns": "p0_id, area, required_evidence, closable_by_createlee, status",
         "min_rows": 7, "generated_rows": len(COMPLIPROOF_P0),
         "client_action": "none_generated",
         "what_it_proves": "The 7 open P0 gates and exactly what closes each one"},
    ]

    manifest = {
        "project": "compliproof",
        "title": "CompliProof — two reconciled exports + P0 evidence checklist",
        "purpose": "Run the reconciliation command against the client's two systems. "
                   "The 7 P0 production gates are infrastructure evidence, NOT CSVs.",
        "as_of": as_of,
        "generated_at_iso8601": core.iso_now(),
        "files": files,
        "reconcile_command": ("PYTHONPATH=src python -m compliproof.cli reconcile "
                              "system_a.csv system_b.csv id"),
        "reconciliation_summary": rec,
        "cannot_generate": [f"{pid} {area} — {close}" for pid, area, _, close in COMPLIPROOF_P0],
        "honesty": HONESTY,
    }
    _json(project / "request_manifest.json", manifest)
    return manifest


# --------------------------------------------------------------------------- #
# Cross-project documents
# --------------------------------------------------------------------------- #
CLIENT_RULES = """\
CLIENT INSTRUCTIONS — how to fill these files
=============================================

WHAT WE ARE ASKING YOU TO DO
----------------------------
Every file in this folder is a real, working example with simulated rows. It is
already in the exact format the verification tool expects. Replace ONLY the data
rows with your own rows. Keep everything else identical.

RULES — do not break these
--------------------------
1. DO NOT change the header row. Column names, order and spelling must match
   exactly. If a column does not apply to you, leave it in place and put a value
   (or an empty value where the column allows it) — never delete the column.
2. DO NOT add or remove columns.
3. Replace the example rows with your rows. A file must keep at least the
   minimum row count shown in REQUEST_LIST.md.
4. Use lowercase `yes` / `no` for boolean columns. Not "Yes", not "Completed",
   not "TRUE".
5. Timestamps must be ISO-8601 with a timezone offset, e.g.
   2026-10-05T09:12:00+02:00. Do not use Excel date serials.
6. DO NOT delete rows to make a gap disappear. Gaps are reported as honest
   findings, and a missing row is itself a finding.
7. Keep the exact filename. Do not rename to `qa_reviews (1).csv`.
8. Save as UTF-8 CSV. If your system exports Excel content with a `.csv`
   extension we can read that too — do not "fix" the encoding yourself.

WHAT WE WILL DO WITH THE FILES
------------------------------
We run the verification tool against them. It reports, per question:
  - Yes, with evidence
  - Gap (what is missing and why)
  - Not applicable (no events in the window)
Nothing is edited on your behalf and no row is ever deleted. The result is a
signed pack that records exactly what was evidenced and what was not.

PRIVACY
-------
Your name and organisation will not appear in any public document. Files stay
outside the source repository and are never committed.

WHAT THESE FILES CANNOT PROVE
-----------------------------
Some production gates are organisational, not data: tenant-isolation
certification, external audit, deployment architecture review, disaster-recovery
testing, security review and legal/privacy review. No CSV can close those. They
are listed per project in REQUEST_LIST.md and will be reported as open until the
relevant signed document exists.
"""


def _request_list_md(manifest: dict) -> str:
    lines = [
        f"# {manifest['title']}",
        "",
        manifest["purpose"],
        "",
        f"- **As-of date:** {manifest['as_of']}",
        f"- **Generated (ISO-8601 UTC):** {manifest['generated_at_iso8601']}",
        f"- **Generated by:** {config.PLATFORM_NAME} / {config.AGENT_NAME}",
        "",
        "## Files to return",
        "",
    ]
    if manifest.get("validate_command"):
        lines += ["```", manifest["validate_command"], "```", ""]
    if manifest.get("reconcile_command"):
        lines += ["```", manifest["reconcile_command"], "```", ""]

    lines += ["| # | File | Required columns | Min rows | Generated rows | Client action |",
              "|---|---|---|---|---|---|"]
    for i, f in enumerate(manifest["files"], 1):
        lines.append(
            f"| {i} | `{f['filename']}` | {f.get('required_columns', '—')} | "
            f"{f.get('min_rows', '—')} | {f.get('generated_rows', '—')} | "
            f"{f.get('client_action', '—')} |")

    if manifest.get("strict_verdict"):
        lines += ["", f"**Strict generator check:** {manifest['strict_verdict']} "
                      f"({manifest['strict_failed']} failures)."]

    lines += ["", "## What Createlee cannot generate", ""]
    for x in manifest.get("cannot_generate", []):
        lines.append(f"- {x}")

    lines += ["", "## Honesty boundary", "", manifest["honesty"], ""]
    return "\n".join(lines)


def _overview_md(manifests: list[dict]) -> str:
    lines = [
        "# Requested files by project — Createlee hand-off packs",
        "",
        "This is the definitive list of files Createlee must generate so that the",
        "client can replace only their own rows and send them back for Signoff.",
        "",
        f"Generated: {core.iso_now()} (ISO-8601 UTC)",
        "",
        "| Project | Generatable files | Org-only / not generatable |",
        "|---|---|---|",
    ]
    for m in manifests:
        gen = sum(1 for f in m["files"]
                  if f.get("client_action") in ("replace_data_rows_only",
                                                "replace_data_rows",
                                                "replace_data_rows_keep_doc_ids_unique",
                                                "replace_data_rows_keep_unique_id",
                                                "owner_completes_and_signs"))
        lines.append(f"| {m['title']} | {gen} | {len(m.get('cannot_generate', []))} |")
    lines += ["", "## Per-project detail", ""]
    for m in manifests:
        lines += [f"### {m['title']}", "", m["purpose"], ""]
        for f in m["files"]:
            lines.append(f"- `{f['filename']}` — {f.get('what_it_proves', '')}")
        if m.get("cannot_generate"):
            lines += ["", "**Not generatable / org-only:**", ""]
            for x in m["cannot_generate"]:
                lines.append(f"- {x}")
        lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def build_all(out_dir: Path | str, as_of: str | None = None) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    as_of = as_of or evidence.default_as_of()

    builders = [build_signoff, build_helix, build_live_support, build_compliproof]
    manifests = [b(out, as_of) for b in builders]

    (out / "REQUESTED-FILES-BY-PROJECT.md").write_text(_overview_md(manifests),
                                                       encoding="utf-8")
    (out / "CLIENT-INSTRUCTIONS.md").write_text(CLIENT_RULES, encoding="utf-8")
    for m in manifests:
        pd = out / m["project"]
        (pd / "REQUEST_LIST.md").write_text(_request_list_md(m), encoding="utf-8")
        (pd / "CLIENT-INSTRUCTIONS.md").write_text(CLIENT_RULES, encoding="utf-8")

    index_rows = []
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "INDEX.csv":
            rel = p.relative_to(out).as_posix()
            index_rows.append([rel, p.stat().st_size, as_of, core.iso_now()])
    _w(out / "INDEX.csv", ["relative_path", "size_bytes", "as_of",
                           "generated_at_iso8601"], index_rows)

    result = {
        "ok": True, "out_dir": str(out), "as_of": as_of,
        "generated_at_iso8601": core.iso_now(),
        "projects": manifests,
        "overview": str(out / "REQUESTED-FILES-BY-PROJECT.md"),
        "client_instructions": str(out / "CLIENT-INSTRUCTIONS.md"),
        "files_written": len(index_rows),
    }
    _json(out / "handoff_manifest.json", result)
    return result


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Build Createlee per-project hand-off packs")
    ap.add_argument("--out", default=str(config.BASE_DIR / "handoff"))
    ap.add_argument("--as-of", default=None, help="YYYY-MM-DD (default: today UTC)")
    args = ap.parse_args()
    r = build_all(args.out, args.as_of)
    print(f"as-of: {r['as_of']}  out: {r['out_dir']}  files: {r['files_written']}")
    for m in r["projects"]:
        print(f"  {m['project']:<24} files={len(m['files']):<3} "
              f"cannot_generate={len(m.get('cannot_generate', []))}")
    print(f"  overview: {r['overview']}")
