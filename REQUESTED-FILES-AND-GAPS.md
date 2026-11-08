# Requested files and remaining gaps — CreateLee production-readiness hand-off

**Prepared:** 2026-11-07
**Scope:** the exact files CreateLee must generate so the client can replace only their own rows, email them back, and Signoff can run against them to unblock the projects that are still production-NOT-ready.
**Projects:** Signoff (the gate), Helix-Codex (Helix-Prime), live-support-assistant, CompliProof.

---

## 0. What changed in this pass (CreateLee finish + audit)

CreateLee was generating files that did **not** satisfy its own shipped acceptance
validator. That is now fixed and proven.

| Item | Before | After |
|---|---|---|
| 8 Signoff CSVs from `evidence.generate_exports` | 4 of 8 **FAIL** the strict validator | **0 FAIL** — verdict `ACCEPTABLE` |
| `system_library/evidence/` | 4 of 8 FAIL | **0 FAIL** — rebuilt |
| Strict validator available in Python | no (Node only) | **yes** — `evidence.validate_strict()`, ported rule-for-rule |
| Per-project hand-off packs | none | **4 packs** — `handoff.py` |
| Selftest | 72 checks | **86 checks, 86/86 PASS** |
| Client instruction sheet | none | `CLIENT-INSTRUCTIONS.md` per project |

The 4 concrete defects fixed in the generator:

1. `ai_approvals.csv` — an `ai_proposed` row had an **empty `approver_id`**.
2. `ai_inventory.csv` — `contract_term` rows carried a **date** in `term_or_version` and a non-matching `reference`; the strict contract requires `term_or_version = no_training` and the **same** `(provider_name, reference)` pair as the provider row.
3. `ai_training.csv` — header had an **extra `verified` column** (5 vs 4), a **blank `completed`** value, and two `module_name` values outside the allowed list.
4. `incident_notifications.csv` — **empty `owner`** fields.

Honest findings are still preserved (authorised=no, training not completed,
2 providers with no signed term) — they are reported, never deleted.

---

## 1. The requested file list — by project

Generated at `cloned_repos/CreateLee/Createlee_platform/Createlee/handoff/`
(the canonical copy). Rebuild with:

```bash
cd cloned_repos/CreateLee/Createlee_platform/Createlee
python3.11 handoff.py --out handoff --as-of 2026-11-06
```

### 1.1 Signoff — the 8 operational evidence exports

These are the files the client fills and returns. **All 8 are generatable.**
Header, column order and value conventions must not change.

| # | File | Required columns | Client action |
|---|---|---|---|
| 1 | `qa_reviews.csv` | `ts, ai_action, human_action, reviewer_id, agent_id` | replace rows |
| 2 | `ai_audit_log.csv` | `ts, actor, event_type` | replace rows |
| 3 | `ai_approvals.csv` | `ts, gate, decision, approver_id` | replace rows |
| 4 | `escalations.csv` | `ts, escalated_by, supervisor_id, authorised` | replace rows |
| 5 | `role_spec.csv` | `ts, role, assigned_to, is_authorised_supervisor, named_accountable` | replace rows; keep **exactly one** `named_accountable=yes` |
| 6 | `ai_inventory.csv` | `ts, row_type, provider_name, reference, term_or_version, owner` | replace rows; `contract_term` → `term_or_version=no_training` |
| 7 | `ai_training.csv` | `ts, staff_id, module_name, completed` | replace rows; `completed` ∈ `yes/no`; `module_name` from the allowed 8 |
| 8 | `incident_notifications.csv` | `ts, incident_id, notified_within_sla, owner` | replace rows; `owner` never blank |

**Allowed `module_name` values:** Responsible AI, Prompt Safety, Data Privacy,
Bias Detection, Model Governance, Incident Response, PII Handling, Access Control.

**Validate after return:**

```bash
python3.11 evidence.py --out handoff/signoff --as-of <date> --validate-only
```

Signoff itself runs on the returned folder:

```bash
PYTHONPATH=src python3 -m signoff build --questionnaire W --data <folder> \
  --mapping OWNER/mapping-table.csv --out out/pack-<ref> --as-of <date>
```

### 1.2 Helix-Codex (Helix-Prime) — nine production gates

Each gate needs `<gate>.evidence.json` **plus** a detached `<gate>.evidence.json.sig`,
stored **outside** the repo, `scope: production`, signed with a key the audited
system does not hold.

| Gate | CreateLee output | Client/owner action | Closable by files? |
|---|---|---|---|
| `signed_production_evidence` | JSON template + the 8-file pack | owner signs with off-system key | **partial** |
| `certified_data_isolation` | JSON template | org must obtain certification | **no** |
| `external_observer_audit` | JSON template | org must appoint auditor | **no** |
| `production_deployment_architecture` | JSON template | org architecture review | **no** |
| `disaster_recovery_evidence` | JSON template | org must run production DR test | **no** |
| `operational_ownership` | `operational_ownership.csv` | client replaces rows, owner signs | **yes** |
| `incident_oncall_ownership` | `incident_oncall_ownership.csv` | client replaces rows | **partial** |
| `security_review` | JSON template | org must commission security review | **no** |
| `legal_privacy_review` | JSON template | org legal must sign | **no** |

**6 of 9 gates cannot be closed by any generated file.** That is not a CreateLee
gap; it is organisational authority.

### 1.3 live-support-assistant — corpus + labels

| File | Required columns | Minimum | Generated |
|---|---|---|---|
| `procedure_corpus.csv` | `doc_id, title, content, tenant_id, published, version, retired` | ≥ 20 | **24** |
| `procedure_corpus.json` | same, under `documents[]` | ≥ 20 | **24** |
| `expected_outcome_labels.csv` | `ticket_id, tenant_id, question, expected_decision, expected_sop_id, source` | ≥ 50 | **64** |

`expected_decision` must be `answer` or `escalate`. Client replaces rows, keeps
`doc_id` values unique, and must not delete rows that expose a gap.

### 1.4 CompliProof — two exports + P0 checklist

| File | Role | Generated |
|---|---|---|
| `system_a.csv` | system A side, `id` key | 20 rows |
| `system_b.csv` | system B side, matching `id` | 19 rows |
| `reconciliation_report.csv` | expected reconciliation shape | 21 union keys |
| `P0_EVIDENCE_CHECKLIST.csv` | the 7 open P0 gates and what closes each | 7 rows |

**Client action:** replace rows in `system_a.csv` / `system_b.csv` only, keeping
`id` unique and non-empty. Nothing else is filled by the client.

```bash
PYTHONPATH=src python -m compliproof.cli reconcile system_a.csv system_b.csv id
```

**0 of 7 P0 gates are closable by these CSVs.** They prove the product runs, not
that it is production-ready.

---

## 2. Gaps — what CreateLee cannot produce (and must not fake)

### 2.1 Gaps that block Signoff itself

| Gap | Impact |
|---|---|
| Client data not yet received | Signoff can only rehearse; no real pack exists |
| "Real pilot pack" not in the repo | The `README.md` production-readiness claim cannot be independently re-verified |
| Signoff does not authenticate source CSVs | A valid pack proves internal consistency, not data authenticity |
| Hashes are not signatures | Oversight Statement signature block is blank by design |

### 2.2 Gaps that block Helix-Codex (6 of 9 gates)

Certified data isolation · external observer audit · production deployment
architecture · disaster-recovery evidence · security review · legal/privacy
review. Each needs a signed document from a party outside the repository.

### 2.3 Gaps that block live-support-assistant

Tenant-isolation proof · authenticated end-to-end flows · hosted telemetry /
escalation transport · external security audit · billing integration ·
per-tenant threshold calibration (the shipped 0.18 is a starting point).

### 2.4 Gaps that block CompliProof (7 open / 0 closed)

| P0 | Needs |
|---|---|
| P0-1 | Hosted CI run URL, clean-install matrix (3.10–3.13), current-candidate Docker build/health |
| P0-2 | Independent signature / key lifecycle (local hash is not a signature) |
| P0-3 | Concurrency + tamper tests, **external timestamp anchor receipt**, single ledger |
| P0-4 | Served-report artifact, CSV parse test, report audit event (the CSVs only let you run `reconcile`) |
| P0-5 | Route auth test, security scan, hardened cookies/CORS |
| P0-6 | Real auth: Argon2id/bcrypt, server-side sessions, RBAC, MFA, lockout |
| P0-7 | Browser acceptance, route inventory, login/logout |

Also missing from the environment: `pip-audit` is **unavailable**, so the
dependency-vulnerability scan is unverified.

### 2.5 CreateLee's own residual gaps

| Gap | Status |
|---|---|
| `external docs for clients/` still holds the failed Ollama output (7 FAIL) | marked non-authoritative with `READ-ME-FIRST.txt` |
| Web enrichment needs network | degrades gracefully; 0 sources is not a failure |
| Ollama absent in this VM | deterministic generation needs no LLM |
| Single-operator local tool | not a multi-user server; do not expose publicly |
| No automated email of client packs | by design; the operator sends manually |

---

## 3. How to use — the operating loop

1. `python3.11 handoff.py --out handoff --as-of 2026-11-06`
2. Check `handoff/VALIDATION_STRICT.json` (in `signoff/`) reads `ACCEPTABLE`.
3. Send the four project folders to the client.
4. Client replaces **only the data rows**, keeps header/columns/filenames.
5. Client emails the files back.
6. `python3.11 evidence.py --out <returned-folder> --as-of <date> --validate-only`
7. Run Signoff on the returned folder → verdict pack.
8. Update each project's gate register honestly: closed only where signed
   evidence exists; everything else stays `open — awaiting organisation approval`.

---

## 4. Proven results

```
strict validator (generated fixtures)   8/8 files, 5 PASS + 3 PASS_WITH_FINDINGS, 0 FAIL — ACCEPTABLE
node validate_signoff_csv.mjs           ACCEPTABLE, 80 rows, width_clean=true, rows_deleted=0
selftest.py                             86/86 PASS
system_library/evidence                 0 FAIL — ACCEPTABLE
```

Evidence artefacts:

- `Createlee_platform/Createlee/evidence_pack/VALIDATION_STRICT.txt`
- `Createlee_platform/Createlee/handoff/REQUESTED-FILES-BY-PROJECT.md`
- `Createlee_platform/Createlee/verification/Createlee_verification_report.txt`
