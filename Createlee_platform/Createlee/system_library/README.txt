Createlee / Engeznee - System Library
======================================

As-of (--as-of):             2026-11-06
Generated at (ISO-8601 UTC): 2026-11-06T22:39:24Z
Generator:                   Createlee / Engeznee (schema 1.0)
Review status:               EXAMPLE_PREVIEW - PENDING OPERATOR REVIEW

WHAT THIS IS
------------
A compact, reusable library of system files to be referred to afterwards.
Data is SIMULATED real-life operational data grounded in REAL published standards
fetched from the web (ITU-T, TM Forum, ISO/IEC 42001, EU AI Act). Start small,
expand later: replace any file with your own export of the same name.

ROW COUNTS
----------
  Procedure corpus:          24 documents   (required >= 20)
    published & active:      22
    draft or retired:        2
  Expected-outcome labels:   64 tickets     (required >= 50)
    answer / escalate:       38 / 26
    source real / synthetic: 10 / 54
  system_a.csv:              20 rows (key = id)
  system_b.csv:              19 rows (key = id)
  Fully reconciled:          15 / 21 union keys
  A-only / B-only:           2 / 1
  Field mismatches:          3
  Rows deleted:              0

FOLDER MAP
----------
  uploaded/    6 REAL files you supplied (XLSX saved as .csv -> UTF-8 CSV, rows preserved)
  evidence/    8 exact-named Signoff evidence CSVs from the previous task
  systems/     compact system library (tenants, agents, AI agents, customers, plans,
               tickets, SLA, channels, controls, roster, approvals, change log, ...)
  Primary required outputs at root: procedure_corpus.csv/.json,
               expected_outcome_labels.csv, system_a.csv, system_b.csv,
               reconciliation_report.csv, references.csv
  INDEX.csv / LIBRARY_MANIFEST.json / README.txt / build report (5 formats)

WEB REFERENCES (real public standards)
------------------------------------
  WEB-01  ITU
      ITU-T: Misuse of E.164 numbering resources (SG2 / WTSA Res.20 / E.156)
      https://www.itu.int/en/ITU-T/inr/Pages/misuse.aspx
      retrieved 2026-11-06T22:39:24Z
      verification: direct fetch - full page read
  WEB-02  ITU
      ITU-T: Universal International Freephone Number (UIFN) format
      https://www.itu.int/en/ITU-T/inr/unum/Pages/uifn.aspx
      retrieved 2026-11-06T22:39:24Z
      verification: search result / reference lead - page not fully verified
  WEB-03  DEKRA
      DEKRA: Navigating AI Governance — EU AI Act & ISO 42001:2023
      https://www.dekra.com/en/the-european-ai-act-iso-42001-2023-certification/
      retrieved 2026-11-06T22:39:24Z
      verification: search result / reference lead - page not fully verified
  WEB-04  SGS
      SGS: ISO/IEC 42001 AI Management System certification
      https://www.sgsgroup.com.cn/en-cn/services/iso-iec-42001-certification-artificial-intelligence-ai-management-system
      retrieved 2026-11-06T22:39:24Z
      verification: search result / reference lead - page not fully verified
  WEB-05  ScienceDirect
      ScienceDirect Topics: Telemanagement Forum (eTOM / SID / TAM)
      https://www.sciencedirect.com/topics/computer-science/telemanagement-forum
      retrieved 2026-11-06T22:39:24Z
      verification: search result / reference lead - page not fully verified
  WEB-06  Virtusa
      Virtusa: Modernizing BSS/OSS with TM Forum eTOM, ODA, SID, TAM
      https://www.virtusa.com/insights/whitepaper/modernizing-bss-oss
      retrieved 2026-11-06T22:39:24Z
      verification: search result / reference lead - page not fully verified
  WEB-07  third-party blog (summary of ITU-T E.800)
      ITU-T E.800 QoS terminology (third-party summary)
      https://www.cnblogs.com/leixiaohua1020/p/3901987.html
      retrieved 2026-11-06T22:39:24Z
      verification: search result / reference lead - page not fully verified
  WEB-08  Jumio
      Jumio: Trusted identity solutions for telcos / SIM swap fraud
      https://www.jumio.com/industries/telcos/
      retrieved 2026-11-06T22:39:24Z
      verification: search result / reference lead - page not fully verified
  WEB-09  Group-IB
      Group-IB: The evolution of SIM swapping fraud
      https://www.group-ib.com/blog/the-evolution-of-sim-swapping-fraud-how-fraudsters-bypass-security-layers/
      retrieved 2026-11-06T22:39:24Z
      verification: search result / reference lead - page not fully verified
  WEB-10  Mitratech
      Mitratech: AI third-party risk management under global AI regulations
      https://mitratech.com/es-la/centro-de-recursos/blog/global-ai-regulations-and-tprm/
      retrieved 2026-11-06T22:39:24Z
      verification: search result / reference lead - page not fully verified
  WEB-11  Baidu Baike
      Baidu Baike: ISO/IEC 42001 (PDCA, GB/T 45081-2024)
      https://baike.baidu.com/item/ISO%2FIEC%2042001/67441065
      retrieved 2026-11-06T22:39:24Z
      verification: search result / reference lead - page not fully verified
  WEB-12  TM Forum
      TM Forum Inform — AI in customer experience operations
      https://inform.tmforum.org/
      retrieved 2026-11-06T22:39:24Z
      verification: search result / reference lead - page not fully verified
  WEB-13  ISO (official)
      ISO: ISO/IEC 42001 explained (official AIMS guidance)
      https://www.iso.org/home/insights-news/resources/iso-42001-explained-what-it-is.html
      retrieved 2026-11-06T22:39:24Z
      verification: direct fetch - full page read

HONESTY BOUNDARY
----------------
  Simulated real-life operational data grounded in REAL published standards fetched from the web
  (ITU-T, TM Forum, ISO/IEC 42001, EU AI Act). Web sources are reference material only, NOT
  customer data. All operational rows are simulated and must be replaced with genuine system
  exports before any real signoff. The 6 files under uploaded/ are the user's actual records and
  are preserved row-for-row; no row was deleted or rewritten.

WHAT YOUR FILES CANNOT CLOSE (needs your organisation)
------------------------------------------------------
  No generated CSV/JSON can evidence the following. They require your engineering
  and security teams: 

  - Tenant isolation: Data/BSS segregation, per-tenant access control and cross-tenant leakage tests
  - Authenticated end-to-end flows: Real SSO/IAM, session handling and end-to-end auth traces
  - Hosted telemetry / escalation transport: Live message bus, hosted logging and escalation delivery
  - External security audit: Independent penetration test, certification and attestation
  - Billing integration: Live charging, invoicing, payments and revenue reconciliation

HONEST FINDINGS (preserved, not cleaned)
----------------------------------------
   1. [Labels] TKT-0061 references draft/retired procedure SOP-023 - not served to agents
   2. [Labels] TKT-0062 references draft/retired procedure SOP-023 - not served to agents
   3. [Labels] TKT-0063 references draft/retired procedure SOP-024 - not served to agents
   4. [Labels] TKT-0064 references draft/retired procedure SOP-024 - not served to agents
   5. [Reconciliation] ACC-1003: field mismatch: plan
   6. [Reconciliation] ACC-1007: field mismatch: status
   7. [Reconciliation] ACC-1012: field mismatch: customer_name
   8. [Reconciliation] key present only in system A - unmatched row preserved
   9. [Reconciliation] key present only in system A - unmatched row preserved
  10. [Reconciliation] key present only in system B - unmatched row preserved
  11. [Uploads] delivery_manifest.csv references 3 files that were not supplied (rolespec_export.csv, qa_review_export.csv, incident_sla_log.csv) - Createlee generated simulated versions under systems/
  12. [Evidence] training_records.csv uses status=Yes / completion_status=Completed; Signoff expects lowercase completed=yes - alias mapping required
  13. [Scope] Tenant isolation, authenticated E2E flows, hosted telemetry, external audit and billing integration are NOT closable by generated files

HOW TO EXTEND
-------------
  - Replace any CSV in place with your own export of the same name.
  - Add procedures to procedure_corpus.csv / .json (one document per row).
  - Add QA-labelled tickets to expected_outcome_labels.csv.
  - Re-run: python3.11 library.py --out /workspace/system_library --as-of 2026-11-06
  - In the app: type 'library' or 'library --as-of 2026-11-06', or POST /api/library.
  - No external organisational approval is needed to generate these internal exports;
    Createlee's own operator review gate still applies before the report is saved/emailed.
