"""Full end-to-end regression suite for Createlee / Engeznee.

Run with env vars pointing OUTPUT_DIR / SESSION_DIR / EVIDENCE_DIR at a temp
sandbox so the real /workspace deliverables are never touched.
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

REPORT_DIR = Path(os.environ.get("CREATELEE_SELFTEST_OUT", str(HERE / "verification")))
REPORT_DIR.mkdir(parents=True, exist_ok=True)

TMP = Path(tempfile.mkdtemp(prefix="clreg_"))
os.environ["CREATELEE_OUTPUT_DIR"] = str(TMP / "outputs")
os.environ["CREATELEE_SESSION_DIR"] = str(TMP / "sessions")
os.environ["CREATELEE_EVIDENCE_DIR"] = str(TMP / "evidence")
os.environ["CREATELEE_LIBRARY_DIR"] = str(TMP / "library")
os.environ["CREATELEE_HANDOFF_DIR"] = str(TMP / "handoff")
os.environ["CREATELEE_SETTINGS_PATH"] = str(TMP / "settings.json")
# Isolate SMTP: never use the operator's real .env credentials in a test run.
for _k in ("CREATELEE_SMTP_HOST", "CREATELEE_SMTP_USER", "CREATELEE_SMTP_PASSWORD",
           "CREATELEE_SMTP_FROM", "CREATELEE_DEFAULT_EMAIL_TO"):
    os.environ[_k] = ""
os.environ["CREATELEE_WEB_TIMEOUT"] = "4"

import app as A  # noqa: E402
import config  # noqa: E402
import core  # noqa: E402
import evidence  # noqa: E402

c = A.app.test_client()
R = []


def check(name, ok, detail=""):
    R.append({"check": name, "ok": bool(ok), "detail": str(detail)[:300]})
    print(("  PASS " if ok else "  FAIL ") + name + (("  | " + str(detail)[:180]) if detail else ""))


def chat(msg, sid=None):
    body = {"message": msg}
    if sid:
        body["sid"] = sid
    return c.post("/api/chat", json=body)


# --- 1. Static / integration endpoints ------------------------------------
r = c.get("/")
check("GET / renders UI", r.status_code == 200 and b"Createlee" in r.data, r.status_code)
r = c.get("/api/status")
j = r.get_json()
check("GET /api/status", r.status_code == 200 and j["platform"] == "Createlee"
      and j["agent"] == "Engeznee", f"formats={j['formats']}")
check("status has 5 formats", set(j["formats"]) == {"csv", "txt", "json", "pdf", "docx"}, j["formats"])

r = c.post("/api/session", json={"new": True})
j = r.get_json()
sid = j["sid"]
check("POST /api/session seeds samples", j["ok"] and len(j["state"]["uploads"]) >= 7,
      f"{len(j['state']['uploads'])} uploads, sid={sid}")
check("session state has ISO-8601 created_at", "T" in j["state"]["created_at_iso8601"])

r = c.get("/api/state/" + sid)
check("GET /api/state/<sid>", r.status_code == 200 and r.get_json()["ok"])

r = c.get("/api/template/questions.csv")
check("GET /api/template/questions.csv", r.status_code == 200 and len(r.data) > 500, len(r.data))
r = c.get("/api/template/mapping-table.template.csv")
check("GET /api/template/mapping-table.template.csv", r.status_code == 200 and len(r.data) > 500)

# --- 2. Engeznee informational commands -----------------------------------
r = chat("help", sid); check("chat: help", "evidence --as-of" in r.get_json()["reply"])
r = chat("status", sid); check("chat: status", "ISO-8601 / UTC" in r.get_json()["reply"])
r = chat("analyze", sid); check("chat: analyze", "Analysed" in r.get_json()["reply"])
r = chat("list", sid)
lj = r.get_json()
check("chat: list", "Documents defined" in lj["reply"], f"{lj['reply'].splitlines()[0]}")
check("list detects canonical 11-column schema", "canonical 11-column" in lj["reply"])

# --- 3. Web enrichment (optional, must not crash) --------------------------
t0 = time.time()
r = chat("web: ISO 8601", sid)
check("chat: web: reference pack", r.status_code == 200 and "Live web references" in r.get_json()["reply"],
      f"{time.time()-t0:.1f}s")

# --- 4. Generate the full document pack (9 types x 5 formats) --------------
r = chat("generate all as csv,txt,json,pdf,docx", sid)
gj = r.get_json()
check("chat: generate all (5 formats)", gj.get("ok") and gj.get("staged_count") == 9,
      f"staged={gj.get('staged_count')}")
check("generate only STAGES (nothing saved)", "NOTHING saved" in gj["reply"])
check("all staged drafts pending review",
      all(s["review_status"].startswith("DRAFT") or "PENDING" in s["review_status"] or "REVIEW" in s["review_status"]
          for s in gj["state"]["staged"]),
      gj["state"]["staged"][0]["review_status"] if gj["state"]["staged"] else "n/a")

r = c.get(f"/api/preview/{sid}/0")
check("GET /api/preview/<sid>/0", r.status_code == 200 and len(r.get_json()["text"]) > 200)

# --- 5. THE GATE: must block without explicit approval ---------------------
r = c.post("/api/approve", json={"sid": sid, "selected": list(range(9))})
check("approve WITHOUT approved=true -> 403", r.status_code == 403, r.get_json().get("error"))
r = c.post("/api/approve", json={"sid": sid, "approved": True, "selected": [], "action": "save"})
check("approve with empty selection -> 400", r.status_code == 400, r.get_json().get("error"))
check("gate left drafts intact", len(c.get(f"/api/state/{sid}").get_json()["state"]["staged"]) == 9)

# --- 6. Approved save -> 45 files, all valid ------------------------------
r = c.post("/api/approve", json={"sid": sid, "approved": True,
                                 "selected": list(range(9)), "action": "save"})
aj = r.get_json()
created = aj.get("created", [])
check("approved save creates 45 files", aj.get("ok") and len(created) == 45, len(created))
fmt_count = {}
for f in created:
    fmt_count[f["format"]] = fmt_count.get(f["format"], 0) + 1
check("all 5 formats exported 9x", fmt_count == {k: 9 for k in ("csv", "txt", "json", "pdf", "docx")}, fmt_count)

out = Path(os.environ["CREATELEE_OUTPUT_DIR"])
pdfs = list(out.glob("*.pdf")); docxs = list(out.glob("*.docx")); jsons = list(out.glob("*.json"))
check("PDF magic valid", all(p.read_bytes()[:4] == b"%PDF" for p in pdfs), f"{len(pdfs)} pdfs")
check("DOCX magic valid", all(p.read_bytes()[:2] == b"PK" for p in docxs), f"{len(docxs)} docx")
check("JSON parses + ISO-8601 metadata",
      all("generated_at_iso8601" in json.loads(p.read_text(encoding="utf-8"))["meta"] for p in jsons),
      f"{len(jsons)} json")
check("approval log written", (out / "createlee_approval_log.jsonl").is_file())

r = c.get("/download/" + created[0]["filename"])
check("GET /download/<file>", r.status_code == 200 and len(r.data) > 100)
r = c.get("/api/files")
check("GET /api/files lists outputs and hides audit log",
      r.get_json()["count"] >= 45 and all(not f["filename"].endswith(".jsonl")
                                          for f in r.get_json()["files"]))

# --- 7. Email: .eml draft fallback, never a silent send --------------------
r = chat("generate QA as pdf", sid)
restaged = r.get_json().get("staged_count", 0)
check("re-stage for email test", restaged >= 1, f"{restaged} QA doc type(s)")
r = c.post("/api/approve", json={"sid": sid, "approved": True, "selected": [0],
                                 "action": "email", "email_to": "third.party@example.com"})
ej = r.get_json()
check("email action returns a mode (no silent send)", ej.get("ok") and bool(ej.get("email", {}).get("mode")),
      ej.get("email", {}).get("mode"))
check(".eml draft produced without SMTP creds",
      any(f["format"] == "eml" for f in ej["state"]["outputs"]) or
      bool(list(out.glob("*.eml"))), "portable draft")

# --- 8. Evidence / Signoff task -------------------------------------------
r = chat("evidence --as-of 2026-11-06", sid)
vj = r.get_json()
check("chat: evidence command", vj.get("ok") and vj.get("staged_count") == 1)
check("evidence reports as-of + 90-day window",
      "2026-11-06" in vj["reply"] and "2026-08-08" in vj["reply"])
check("evidence reports 8/8 files and 0 deletions",
      "8/8" in vj["reply"] and "Rows deleted: 0" in vj["reply"])
check("evidence stages report for operator review",
      "STAGED" in vj["reply"] and "REVIEW" in vj["state"]["staged"][0]["review_status"])

r = c.post("/api/evidence", json={"as_of": "2026-11-06"})
pj = r.get_json()
check("POST /api/evidence", r.status_code == 200 and pj["ok"]
      and pj["report"]["summary"]["files_found"] == 8)
check("POST /api/evidence exposes 5 report formats", len(pj["files"]) == 5, list(pj["files"]))
r = c.post("/api/evidence", json={"as_of": "2026-13-99"})
check("POST /api/evidence rejects bad date -> 400", r.status_code == 400)

# read-only validation: 8 evidence CSVs never modified
evd = Path(os.environ["CREATELEE_EVIDENCE_DIR"])
import hashlib
before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
          for p in evd.iterdir() if p.is_file()}
rr = evidence.build_pack(evd, "2026-11-06", generate_examples=False)
after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
         for p in evd.iterdir() if p.is_file()}
eight = {s["filename"] for s in evidence.SPECS}
check("validate-only never touches the 8 evidence CSVs",
      all(before.get(n) == after.get(n) for n in eight), "8/8 byte-identical")
check("validate-only still reports honest gaps / 0 deletions",
      rr["report"]["summary"]["rows_deleted"] == 0 and
      rr["report"]["summary"]["total_gaps_reported"] >= 8,
      rr["report"]["summary"]["total_gaps_reported"])

# Excel-as-CSV + aliases
demo = evd / "examples_excel_as_csv"
check("Excel-as-CSV demo files present", (demo / "qa_review_excel_bom_semicolon.csv").is_file()
      and (demo / "ai_audit_excel_utf16_tab.csv").is_file())
h, rows = evidence.read_rows(demo / "qa_review_excel_bom_semicolon.csv")
_, _, aliases = evidence.resolve_columns(h, evidence.SPECS[0]["columns"])
check("BOM+semicolon+aliases resolved", len(rows) == 2 and "reviewer_id" in aliases, aliases)
h, rows = evidence.read_rows(demo / "ai_audit_excel_utf16_tab.csv")
check("UTF-16+TAB read", len(rows) == 3 and "date_time" in h)

# strict generator contract: the SHIPPED fixtures must score 0 FAIL
strict = evidence.validate_strict(evd, "2026-11-06")
check("strict contract: 8/8 files found, 0 FAIL",
      strict["summary"]["files_found"] == 8 and strict["summary"]["failed"] == 0,
      strict["summary"]["verdict"])
check("strict contract: verdict ACCEPTABLE",
      strict["summary"]["verdict"] == "ACCEPTABLE")


# --- 8b. System library task -----------------------------------------------
r = chat("library --as-of 2026-11-06", sid)
lj2 = r.get_json()
check("chat: library command", lj2.get("ok") and lj2.get("staged_count") == 1)
check("library reports corpus >= 20 and labels >= 50",
      "24 procedures" in lj2["reply"] and "64 tickets" in lj2["reply"])
check("library reports reconciliation by id key",
      "fully reconciled" in lj2["reply"] and "rows deleted=0" in lj2["reply"])

r = c.post("/api/library", json={"as_of": "2026-11-06"})
libj = r.get_json()
check("POST /api/library", r.status_code == 200 and libj["ok"])
check("library corpus >= 20", libj["row_counts"]["corpus"] >= 20, libj["row_counts"]["corpus"])
check("library labels >= 50", libj["row_counts"]["labels"] >= 50, libj["row_counts"]["labels"])
check("library rows_deleted = 0", libj["reconciliation"]["rows_deleted"] == 0)
check("library honours 5 named limitations", len(libj["manifest"]["limitations"]) == 5)
check("library records web references with ISO-8601",
      len(libj["manifest"]["web_references"]) >= 10 and
      all("T" in x["retrieved_at_iso8601"] for x in libj["manifest"]["web_references"]))
check("POST /api/library rejects bad date -> 400",
      c.post("/api/library", json={"as_of": "2026-99-99"}).status_code == 400)

libd = Path(os.environ["CREATELEE_LIBRARY_DIR"])
def _csv(name):
    with (libd / name).open(encoding="utf-8") as f:
        rr = list(csv.reader(f))
    return rr[0], rr[1:]
ch, cr = _csv("procedure_corpus.csv")
check("procedure_corpus.csv has the 7 required columns",
      ch == ["doc_id", "title", "content", "tenant_id", "published", "version", "retired"] and len(cr) >= 20)
lh, lr = _csv("expected_outcome_labels.csv")
check("expected_outcome_labels.csv has the 6 required columns",
      lh == ["ticket_id", "tenant_id", "question", "expected_decision", "expected_sop_id", "source"]
      and len(lr) >= 50)
check("label decisions are answer/escalate only",
      {r[3] for r in lr} <= {"answer", "escalate"})
ah, ar = _csv("system_a.csv")
bh, br = _csv("system_b.csv")
rh, rr2 = _csv("reconciliation_report.csv")
check("system_a/system_b share the id key column",
      ah == bh == ["id", "customer_name", "plan", "status"] and ah[0] == "id")
check("reconciliation report preserves all union keys",
      len(rr2) == len({r[0] for r in ar} | {r[0] for r in br}))
check("library ingests 6 REAL uploaded files",
      len(list((libd / "uploaded").glob("*.csv"))) == 6)
check("library copies the 8 evidence CSVs",
      len(list((libd / "evidence").glob("*.csv"))) == 8)
check("library systems/ folder populated", len(list((libd / "systems").glob("*.csv"))) >= 12)
_reports = [p for p in libd.glob("library_build_report_*")
            if p.suffix in (".csv", ".txt", ".json", ".pdf", ".docx")]
check("library build report exported in 5 formats",
      len({p.suffix for p in _reports}) == 5, len(_reports))
check("INDEX.csv / LIBRARY_MANIFEST.json / README.txt present",
      all((libd / n).is_file() for n in
          ("INDEX.csv", "LIBRARY_MANIFEST.json", "README.txt", "references.csv")))
check("library report still goes through operator review gate",
      lj2["state"]["staged"][0]["review_status"].startswith("EXAMPLE_PREVIEW"))

# --- 8c. Per-project hand-off packs -----------------------------------------
r = chat("handoff --as-of 2026-11-06", sid)
hj = r.get_json()
check("chat: handoff command", r.status_code == 200 and hj.get("ok")
      and "HAND-OFF PACKS" in hj["reply"])

r = c.post("/api/handoff", json={"as_of": "2026-11-06"})
hd = r.get_json()
check("POST /api/handoff", r.status_code == 200 and hd["ok"])
projects = {m["project"]: m for m in hd["projects"]}
check("handoff covers all four projects",
      set(projects) == {"signoff", "helix-codex", "live-support-assistant", "compliproof"},
      sorted(projects))
check("handoff signoff pack passes the strict contract",
      projects["signoff"]["strict_failed"] == 0
      and projects["signoff"]["strict_verdict"] == "ACCEPTABLE")
check("handoff signoff supplies all 8 evidence files",
      len(projects["signoff"]["files"]) == 8)
check("handoff helix templates all 9 gates",
      len([f for f in projects["helix-codex"]["files"] if "gate-evidence" in f["filename"]]) == 9)
check("handoff helix names 6 org-only gates",
      len(projects["helix-codex"]["cannot_generate"]) == 6)
check("handoff live-support corpus >= 20, labels >= 50",
      projects["live-support-assistant"]["files"][0]["generated_rows"] >= 20
      and projects["live-support-assistant"]["files"][2]["generated_rows"] >= 50)
check("handoff compliproof lists 7 open P0 gates",
      len(projects["compliproof"]["cannot_generate"]) == 7)
check("handoff rejects bad date -> 400",
      c.post("/api/handoff", json={"as_of": "2026-99-99"}).status_code == 400)

hdd = Path(os.environ["CREATELEE_HANDOFF_DIR"])
check("handoff writes REQUESTED-FILES-BY-PROJECT.md + INDEX.csv",
      (hdd / "REQUESTED-FILES-BY-PROJECT.md").is_file() and (hdd / "INDEX.csv").is_file())
check("handoff writes per-project REQUEST_LIST.md + requests",
      all((hdd / p / "REQUEST_LIST.md").is_file()
          and (hdd / p / "request_manifest.json").is_file() for p in projects))

# --- 8d. Settings, local model and the executive-assistant agent -----------
import llm as _llm  # noqa: E402

r = c.get("/api/settings")
sj = r.get_json()
check("GET /api/settings", r.status_code == 200 and sj["ok"] and "settings" in sj)
check("settings exposes a models list", isinstance(sj.get("models"), list))
check("settings exposes the agent tool names", len(sj.get("tools", [])) >= 8)
check("GET /api/models", c.get("/api/models").status_code == 200
      and c.get("/api/models").get_json()["ok"])

r = c.post("/api/settings", json={"temperature": 0.2, "max_steps": 4, "autostart": False})
check("POST /api/settings saves values",
      r.status_code == 200 and r.get_json()["settings"]["temperature"] == 0.2
      and r.get_json()["settings"]["max_steps"] == 4)
check("POST /api/settings rejects bad temperature -> 400",
      c.post("/api/settings", json={"temperature": "hot"}).status_code == 400)
check("POST /api/settings rejects bad max_steps -> 400",
      c.post("/api/settings", json={"max_steps": "many"}).status_code == 400)

# Tool layer works without any model (deterministic, no network).
_ops = A.agent_ops(A.get_state(sid))
check("agent tool: project_readiness", A.agent._execute("project_readiness", {}, _ops)["ok"])
check("agent tool: list_documents", A.agent._execute("list_documents", {}, _ops)["ok"])
check("agent tool: platform_status", A.agent._execute("platform_status", {}, _ops)["ok"])
check("agent tool: unknown tool fails cleanly",
      A.agent._execute("does_not_exist", {}, _ops)["ok"] is False)

# Free-form chat must answer even with no model, and report its source.
_orig_status = _llm.ollama_status
_llm.ollama_status = lambda: {"available": False, "models": [], "selected": "",
                              "host": "stub", "autostart": True,
                              "last_start": {}, "binary": ""}
try:
    r = c.post("/api/chat", json={"sid": sid,
                                  "message": "What is still blocking Helix-Codex and what should I do next?"})
    aj = r.get_json()
finally:
    _llm.ollama_status = _orig_status
check("agent answers free-form chat without a model",
      r.status_code == 200 and aj["ok"] and len(aj["reply"]) > 40)
check("agent reports its source", aj.get("agent_source") in ("model", "fallback"),
      aj.get("agent_source"))
check("agent returns a trace list", isinstance(aj.get("trace"), list))
check("agent fallback names the blocker", "Helix-Codex" in aj["reply"]
      or "Helix" in aj["reply"])

# --- 9. Checklist-mode questions.csv (the user's W-01..W-10 CSV) ----------
checklist = (Path(config.SAMPLES_DIR) / "questions-ai-governance-checklist.csv").read_bytes()
r = c.post("/api/upload", data={"sid": sid, "files": (io.BytesIO(checklist), "questions.csv")},
           content_type="multipart/form-data")
check("POST /api/upload replaces questions.csv", r.status_code == 200 and r.get_json()["ok"])
r = chat("list", sid)
check("list auto-detects checklist schema", "checklist (Ref / Question / Yes / Partly / No)" in r.get_json()["reply"])
r = chat("generate all as csv,pdf", sid)
cj = r.get_json()
check("checklist generate stages 1 fillable doc", cj.get("staged_count") == 1,
      cj.get("staged_count"))
r = c.get(f"/api/preview/{sid}/0")
check("checklist preview has fillable [  ] boxes", "[  ]" in r.get_json()["text"])

# --- 10. Misc safety -------------------------------------------------------
r = chat("clear", sid)
check("chat: clear discards drafts", r.get_json()["state"]["staged"] == [])
r = c.post("/api/load-samples", json={"sid": sid})
check("POST /api/load-samples restores canonical pack", r.get_json()["ok"])
r = chat("nonsense command that is not real", sid)
check("unknown command handled gracefully (no crash)", r.status_code == 200 and r.get_json()["ok"])

# --- Summary ---------------------------------------------------------------
passed = sum(1 for x in R if x["ok"])
summary = {"platform": "Createlee", "agent": "Engeznee", "schema_version": config.SCHEMA_VERSION,
           "generated_at_iso8601": core.iso_now(), "time_standard": "ISO-8601 / UTC",
           "total_checks": len(R), "passed": passed, "failed": len(R) - passed,
           "all_passed": passed == len(R),
           "files_generated_in_test": len(list(out.glob("*"))),
           "checks": R}
(REPORT_DIR / "Createlee_verification_report.json").write_text(
    json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

lines = [
    "Createlee / Engeznee — End-to-End Reliability Verification",
    "===========================================================",
    f"Generated at (ISO-8601 UTC): {summary['generated_at_iso8601']}",
    f"Schema version:              {summary['schema_version']}",
    f"Result:                      {passed}/{len(R)} checks passed "
    f"({'ALL PASS' if passed == len(R) else str(len(R)-passed) + ' FAILED'})",
    "",
    "Scope: every HTTP route, every Engeznee command, all 5 exporters, the human",
    "approval gate, the email draft fallback, the 8-file Signoff evidence task,",
    "read-only validation, Excel-saved-as-CSV tolerance, column aliases, and",
    "checklist-mode questions.csv.",
    "",
    "CHECKS",
    "------",
]
for i, x in enumerate(R, 1):
    lines.append(f"  {i:>2}. [{'PASS' if x['ok'] else 'FAIL'}] {x['check']}")
    if x["detail"]:
        lines.append(f"        {x['detail']}")
lines += [
    "",
    "NOTES",
    "-----",
    "  - Test ran in an isolated temp sandbox; /workspace deliverables were not modified.",
    "  - Web enrichment is optional and network-dependent; 0 sources is not a failure.",
    "  - Ollama is absent in this VM by design; deterministic generation needs no LLM.",
    "  - Email with no SMTP credentials produces a portable .eml draft, never a send.",
    "  - The 8 evidence CSVs are synthetic fixtures, not real compliance evidence.",
    "",
]
(REPORT_DIR / "Createlee_verification_report.txt").write_text("\n".join(lines), encoding="utf-8")
print(f"\nRESULT: {passed}/{len(R)} passed | all_passed={summary['all_passed']}")
print(f"report: {REPORT_DIR / 'Createlee_verification_report.txt'}")
sys.exit(0 if passed == len(R) else 1)
