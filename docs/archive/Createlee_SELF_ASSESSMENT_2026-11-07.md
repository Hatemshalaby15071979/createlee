# CreateLee — internal test & self-assessment report

**Date:** 2026-11-07
**Assessor:** agent (DeepSeek Harness) — internal self-assessment only; **NOT** an independent or external audit.
**Subject:** Is CreateLee able to generate the exact files each production-NOT-ready project needs, such that a client replaces only its rows and Signoff runs without reformatting?
**Self-assessment verdict:** internal checks pass with named residual gaps. This is not an external/independent audit and changes no project's production status. The gates it cannot close are organisational, not software.

---

## 1. Method

1. Read the generator, validator, library and server code.
2. Ran the project's own acceptance validator (`opencode_next_step_kit/validate_signoff_csv.mjs`) against every CSV set on disk.
3. Compared the Python validator in `evidence.py` with the JavaScript acceptance gate and found they enforce **different contracts**.
4. Fixed the generator, then re-ran both validators.
5. Added a Python port of the strict gate so the build cannot silently regress.
6. Built per-project hand-off packs and proved each one.
7. Ran the full regression suite (86 checks) and a live Flask route smoke.

---

## 2. Findings

### F-1 (Critical) — the shipped fixtures failed the project's own acceptance gate

`Createlee_system_library/evidence/` scored **3 PASS / 1 PASS_WITH_FINDINGS / 4 FAIL**.
The repository simultaneously claimed "72/72 PASS". Both were true: the 72 checks
test the *platform*, the 4 FAILs test the *Signoff CSV contract*. Two different
contracts, one of them not enforced anywhere in the build.

| File | Failure |
|---|---|
| `ai_approvals.csv` | `ai_proposed` row 5 has an empty `approver_id` |
| `ai_inventory.csv` | 6 `contract_term` rows carry a date in `term_or_version` instead of `no_training`, and their `reference` does not match the provider row |
| `ai_training.csv` | extra `verified` column (5 vs 4), a blank `completed`, 2 `module_name` values outside the allowed list |
| `incident_notifications.csv` | empty `owner` fields |

**Impact:** any client pack built from this set would have produced a gap-laden
Signoff verdict, and the operator would have blamed the client's data.

### F-2 (High) — no strict validator in the build path

`evidence.validate_all` accepts aliases, extra columns and blank fields (correct
for real client exports). Nothing enforced the stricter generator contract, so
F-1 could recur on any edit.

**Fix:** `evidence.validate_strict()` is a rule-for-rule Python port of
`validate_signoff_csv.mjs`, including `STRICT_HEADERS`, the allowed module list,
the `no_training` contract rule, exact-header and lowercase-boolean checks.
Every pack now writes `VALIDATION_STRICT.json` / `.txt`.

### F-3 (High) — no per-project hand-off artefact

The 8 Signoff CSVs existed, and the library happened to contain a corpus, labels
and a reconciliation pair, but nothing assembled them **per project** with
instructions, or named what could not be generated.

**Fix:** `handoff.py` builds four packs. Each has `REQUEST_LIST.md`,
`CLIENT-INSTRUCTIONS.md`, `request_manifest.json`, and a cross-project
`REQUESTED-FILES-BY-PROJECT.md`.

### F-4 (Medium) — a failed model output sat beside the good sets

`external docs for clients/` held the Ollama run that failed 7/8. Nothing marked
it as non-authoritative.

**Fix:** added `READ-ME-FIRST.txt` naming it as a failed run and pointing at the
validated sets.

### F-5 (Low) — selftest pinned a volatile number

`total_gaps_reported == 15` broke on any legitimate generator change.

**Fix:** assertion is now `>= 8` with `rows_deleted == 0`; the exact count is
printed as detail.

---

## 3. Fixes and proof

### 3.1 Generator (`evidence.generate_exports`)

Four targeted changes, no rows deleted, honest findings preserved:

| File | Change |
|---|---|
| `ai_approvals.csv` | every `ai_proposed` row carries an `approver_id` |
| `ai_inventory.csv` | `contract_term` rows reuse the provider's `(provider_name, reference)` and set `term_or_version=no_training`; two providers still have no term (finding) |
| `ai_training.csv` | 4-column header; `completed` always `yes`/`no`; modules from the allowed 8 |
| `incident_notifications.csv` | `owner` never blank; SLA misses stay as findings |

### 3.2 Proof — both validators agree

```
strict (Python):  8 files, 5 PASS + 3 PASS_WITH_FINDINGS, 0 FAIL — ACCEPTABLE
node (acceptance): 8 files, 5 PASS + 3 PASS_WITH_FINDINGS, 0 FAIL — ACCEPTABLE
                  80 rows preserved, width_clean=true, rows_deleted=0
```

Applied to `evidence_pack/`, `system_library/evidence/` and `handoff/signoff/`.

### 3.3 Regression suite

```
RESULT: 86/86 passed | all_passed=True
```

New checks cover: strict contract 0 FAIL, verdict ACCEPTABLE, `handoff` chat
command, `POST /api/handoff`, all four projects, 9 helix templates, 6 org-only
gates, corpus ≥ 20 / labels ≥ 50, 7 CompliProof P0s, bad-date 400, and the
presence of every per-project `REQUEST_LIST.md` + manifest.

### 3.4 Live route smoke

```
GET  /               200
GET  /api/status     200  formats=[csv, txt, json, pdf, docx]
POST /api/handoff    200  projects=[signoff, helix-codex, live-support-assistant, compliproof]
POST /api/evidence   200  files_found=8
```

---

## 4. What CreateLee now produces

| Project | Files | Strict |
|---|---|---|
| Signoff | 8 evidence CSVs + strict validation | **0 FAIL** |
| Helix-Codex | 9 gate JSON templates + 2 ownership CSVs | JSON valid, signature null |
| live-support-assistant | corpus CSV/JSON (24) + labels (64) | schema-valid |
| CompliProof | system_a (20) + system_b (19) + reconciliation (21) + P0 checklist (7) | reconciliation reproducible |

Cross-project: `REQUESTED-FILES-BY-PROJECT.md`, `CLIENT-INSTRUCTIONS.md`,
`INDEX.csv`, `handoff_manifest.json`.

---

## 5. Residual gaps (not software defects)

1. **Client data is still absent.** CreateLee produces format-exact *simulated* rows; it cannot produce the client's real rows.
2. **Helix-Codex: 6 of 9 gates** need signed documents from outside the repository (isolation certification, external audit, architecture review, DR test, security review, legal review). CreateLee ships the JSON template with `signature: null` and `ORG_MUST_COMPLETE`.
3. **CompliProof: 0 of 7 P0s** close on CSV. It needs hosted CI, a clean-install matrix, a current-candidate Docker build, a vulnerability scan (`pip-audit` is unavailable here), an external anchor receipt and independent key-lifecycle evidence.
4. **live-support-assistant:** corpus and labels enable evaluation, not release. Tenant isolation, transport and external audit remain open.
5. **Signoff does not authenticate source CSVs.** A valid pack proves internal consistency, not authenticity. Hashes are not signatures; the Oversight Statement signature block stays blank by design.
6. **CreateLee is single-operator and local.** No authentication; do not expose it publicly.

---

## 6. Recommendation

Send `handoff/` to the client as-is, but state plainly in the covering email:

- the rows are examples and must be replaced;
- the header, column order, filenames and lowercase `yes`/`no` must not change;
- gaps are findings, not failures — do not delete rows to hide them.

On return: run `evidence.py --validate-only`, then Signoff, then update each
project's gate register honestly. Closed means *signed evidence exists*; nothing
in this pass changes any project's production status.
