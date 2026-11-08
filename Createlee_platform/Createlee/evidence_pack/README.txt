Createlee / Engeznee — Signoff Evidence Pack
===========================================

As-of date (--as-of):        2026-11-06
Coverage window (90 days):   2026-08-08 .. 2026-11-06
Window handling:             Events older than 90 days are still parsed but
                             excluded from coverage percentages.
Generated at (ISO-8601 UTC): 2026-11-06T23:34:08Z
Generator:                   Createlee / Engeznee  (schema 1.0)

RESULT
------
Files expected:              8
Files found:                 8
PASS:                        0
PASS_WITH_FINDINGS:          8
FAIL:                        0
Rows preserved:              80
Gaps reported (honest):      12
Rows deleted:                0   (never delete rows to look clean)

STRICT GENERATOR CONTRACT (the gate the generated fixtures must pass)
----------------------------------------------------------------------
Verdict:                     ACCEPTABLE
PASS:                        5
PASS_WITH_FINDINGS:          3
FAIL:                        0   (must be 0 before shipping)

PER-FILE STATUS
---------------
  #1 qa_reviews.csv                 PASS_WITH_FINDINGS   rows= 13  in-window= 12  out=1  cov=92.3%  findings=2
      required columns: ts, ai_action, human_action, reviewer_id, agent_id
  #2 ai_audit_log.csv               PASS_WITH_FINDINGS   rows= 10  in-window=  9  out=1  cov=90.0%  findings=1
      required columns: ts, actor, event_type
  #3 ai_approvals.csv               PASS_WITH_FINDINGS   rows=  9  in-window=  8  out=1  cov=88.9%  findings=1
      required columns: ts, gate, decision, approver_id
  #4 escalations.csv                PASS_WITH_FINDINGS   rows=  7  in-window=  6  out=1  cov=85.7%  findings=2
      required columns: ts, escalated_by, supervisor_id, authorised
  #5 role_spec.csv                  PASS_WITH_FINDINGS   rows=  5  in-window=  4  out=1  cov=80.0%  findings=1
      required columns: ts, role, assigned_to, is_authorised_supervisor
  #6 ai_inventory.csv               PASS_WITH_FINDINGS   rows= 14  in-window= 14  out=0  cov=100.0%  findings=1
      required columns: ts, row_type, provider_name
  #7 ai_training.csv                PASS_WITH_FINDINGS   rows= 11  in-window= 10  out=1  cov=90.9%  findings=2
      required columns: ts, staff_id, module_name, completed
  #8 incident_notifications.csv     PASS_WITH_FINDINGS   rows= 11  in-window= 10  out=1  cov=90.9%  findings=2
      required columns: ts, incident_id, notified_within_sla, owner

FILES IN THIS PACK
------------------
  8 evidence CSV exports (exact Section-2 filenames / required columns)
  evidence_validation_report_<ISO8601>.{csv,txt,json,pdf,docx}  — the report in 5 formats
  evidence_validation_report_data.json — raw validation data
  VALIDATION_STRICT.json / VALIDATION_STRICT.txt — strict generator-contract check
  INDEX.csv — manifest of every file with ISO-8601 build time
  README.txt — this file
  examples_excel_as_csv/ — proof that Excel-saved-as-.csv works
      (UTF-8-BOM + ';' + aliases, and UTF-16 + TAB; read-only)

COLUMN ALIASES & EXCEL-AS-CSV SUPPORT
-------------------------------------
  Signoff accepts column aliases (see 'Accepted Column Aliases' in the report).
  Excel content saved with a .csv extension is supported: UTF-8 / UTF-8-BOM /
  UTF-16 / CP1252 / Latin-1 encodings and comma / semicolon / tab / pipe
  delimiters are auto-detected on read. Files are never rewritten.

HOW TO USE WITH YOUR REAL EXPORTS
---------------------------------
  Drop your 8 genuine system exports into this folder using the exact Section-2
  filenames (or matching glob patterns), then re-run the pack in validate-only
  mode: your 8 evidence CSVs are never overwritten (only the derived report,
  INDEX and README are refreshed):
      python3.11 evidence.py --out <this folder> --as-of 2026-11-06 --validate-only
  The 8 CSVs are internal operational exports you already generate; no external
  organisational approval is required to produce them. Createlee's own operator
  review gate still applies before any AI-authored report is saved or emailed.

HONESTY NOTICE
--------------
  Synthetic example exports generated from Createlee bundled sample data. These are NOT real
  compliance evidence. Replace with genuine system exports before any actual signoff. Gaps are
  preserved and reported, never deleted.

  Gaps below are preserved and reported, never silently cleaned up:

    - [qa_reviews.csv] 2 row(s) with blank reviewer_id — not deleted.
    - [qa_reviews.csv] 1 event(s) older than 90 days: parsed, excluded from coverage percentages.
    - [ai_audit_log.csv] 1 event(s) older than 90 days: parsed, excluded from coverage percentages.
    - [ai_approvals.csv] 1 event(s) older than 90 days: parsed, excluded from coverage percentages.
    - [escalations.csv] 1 row(s) with authorised=no — control exception, reported not removed.
    - [escalations.csv] 1 event(s) older than 90 days: parsed, excluded from coverage percentages.
    - [role_spec.csv] 1 event(s) older than 90 days: parsed, excluded from coverage percentages.
    - [ai_inventory.csv] 2 provider(s) with no signed no-training contract term: Internal, Vendor D
    - [ai_training.csv] 2 staff training row(s) not completed/verified.
    - [ai_training.csv] 1 event(s) older than 90 days: parsed, excluded from coverage percentages.
    - [incident_notifications.csv] 3 row(s) with notified_within_sla=no — control exception, reported not removed.
    - [incident_notifications.csv] 1 event(s) older than 90 days: parsed, excluded from coverage percentages.
