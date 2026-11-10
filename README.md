<div align="center">

# CreateLee

<!-- badges:start -->

![licence](https://img.shields.io/badge/licence-MIT-blue)
![local verification](https://img.shields.io/badge/local%20verification-format%20rehearsal-blue)

*Local verification measured 2026-11-06 on `master`; every `INDEX.csv` row is tagged `simulated`. This repository includes rehearsal data with unverified provenance; it is not evidence of production use.*

<!-- badges:end -->

**Signoff rehearsal library — synthetic fixtures for rehearsing the Signoff evidence gate end to end.**

![Status](https://img.shields.io/badge/status-synthetic%20fixtures-yellow)
![Licence](https://img.shields.io/badge/licence-MIT-blue)
![Python](https://img.shields.io/badge/python-validator-3776ab)

</div>

## GitHub shipment status (2026-11-07)

<!-- docs-sync:start -->
**CreateLee — Signoff rehearsal library (synthetic fixtures, no release).** No hosted Actions result exists for this candidate; this checkout contains the Signoff rehearsal library and its validator only. The golden acceptance set is ACCEPTABLE (6 PASS, 2 PASS_WITH_FINDINGS) while the rehearsal-library copy fails 4 of 8 against the validator. Hosted GitHub Actions has not yet run on this candidate, and data provenance is unverified.
<!-- docs-sync:end -->

The intended public repository is [Hatemshalaby15071979/createlee](https://github.com/Hatemshalaby15071979/createlee). No hosted Actions result exists for this candidate; this checkout contains the Signoff rehearsal library and its validator only. Local checks are recorded in [`Createlee_deep_verification_report.txt`](Createlee_deep_verification_report.txt) and [`Createlee_verification_report.txt`](Createlee_verification_report.txt). This is rehearsal data with unverified provenance; it closes no production gate and authenticates nothing.

## One-line identity

CreateLee is the synthetic rehearsal library for the Signoff evidence gate: eight export-shaped CSVs per project (QA reviews, audit events, approvals, escalations, role spec, AI inventory, training records, incident notifications), a CSV validator, and golden acceptance examples — used to rehearse, demo, and format-check the Signoff pack before real client exports arrive.

> [!IMPORTANT]
> **Positioning.** Synthetic fixtures only. Every `INDEX.csv` row is tagged `origin = simulated (Signoff fixture)` / `simulated / derived`. CreateLee cannot close any authenticity, infrastructure, or production gate for Helix-Codex, live-support-assistant, or CompliProof — it rehearses the *shape* of the evidence path, not the substance.

> [!NOTE]
> **Operating principle.** Signoff answers "how did AI touch our customers?" with a signed, decision-by-decision evidence pack built offline from the customer's own CSV exports. CreateLee supplies *simulated-shaped* exports so the gate can be rehearsed end to end before the client's authentic exports are available. The machine never guesses, never paraphrases, never auto-signs, and never classifies anyone's system as high-risk; unmapped questions are reported as `UNMAPPED`, never answered.

## What it does

CreateLee holds three copies of the same eight Signoff export filenames. They are **not equivalent**:

| Set | Path | Validator verdict |
| --- | --- | --- |
| Golden acceptance target | `opencode_next_step_kit/golden_examples/` | **ACCEPTABLE** — 6 PASS, 2 PASS_WITH_FINDINGS, 0 FAIL |
| Rehearsal library | `Createlee_system_library/evidence/` | **NOT ACCEPTABLE** — 3 PASS, 1 PASS_WITH_FINDINGS, **4 FAIL** |
| Failed model output | `external docs for clients/` | **NOT ACCEPTABLE** — 1 PASS, **7 FAIL** |

Point every future run at `opencode_next_step_kit/golden_examples/`, not `Createlee_system_library/evidence/`. Fix or delete the four failing library files (`ai_approvals.csv`, `ai_inventory.csv`, `ai_training.csv`, `incident_notifications.csv`) to avoid a false source of truth.

The eight export shapes are:

1. `qa_reviews.csv` — `ts, ai_action, human_action, reviewer_id, agent_id`
2. `*audit*.csv` — `ts, actor, event_type`
3. `*approval*.csv` — `ts, gate, decision, approver_id`
4. `*escalation*.csv` — `ts, escalated_by, supervisor_id, authorised`
5. `role*spec*.csv` — `ts, role, assigned_to, is_authorised_supervisor` (+ exactly one `named_accountable=yes`)
6. `*ai*inventory*.csv` — `ts, row_type, provider_name` (+ one `no_training` contract term)
7. `*training*.csv` — `ts, staff_id, module_name, completed` (`yes` lowercase)
8. `*incident*.csv` — `ts, incident_id, notified_within_sla, owner`

## How it fits Helix Codex

CreateLee is part of the Helix Codex / Helix Prime body of work — the same author and the same design philosophy (offline, explainable, auditable, no generative model in the evidence path). It is an **independent repository with no shared codebase or runtime infrastructure** with Helix Prime, live-support-assistant, or CompliProof; portfolio membership, not technical integration.

It feeds the Signoff gate ([Hatemshalaby15071979/Sign-off](https://github.com/Hatemshalaby15071979/Sign-off)): the Signoff validator (`opencode_next_step_kit/validate_signoff_csv.mjs`) reads these export shapes and produces the pack verdicts that Helix-Codex's production gates consume as *content only* — the signature itself is an external, owner-supplied act and cannot be simulated here.

## Architecture

- `Createlee_platform/` — the Createlee platform code (library, sessions, uploads, verification).
- `Createlee_system_library/` — the "official" rehearsal library CSVs (the NOT ACCEPTABLE set above).
- `opencode_next_step_kit/` — the Signoff validator (`validate_signoff_csv.mjs`) and golden acceptance examples (the ACCEPTABLE set).
- `external docs for clients/` — failed model output (NOT ACCEPTABLE).
- `INDEX.csv` — every row tagged `simulated / derived`; the provenance register.
- `Createlee_deep_verification_report.txt` / `Createlee_verification_report.txt` — dated verification records.

## Production status & verification

> [!WARNING]
> This is a rehearsal library, not a production deployment. **Data provenance has not been independently verified. Do not infer that bundled material is synthetic, anonymized, or free of personal data. It is not production-proven.** No external security audit, certified data isolation, or signed installer is claimed. The operational rows "must be replaced with genuine system exports before any real signoff."

| Check | Result | Source |
| --- | --- | --- |
| Golden acceptance set | **ACCEPTABLE** — 6 PASS, 2 PASS_WITH_FINDINGS, 0 FAIL | `opencode_next_step_kit/validate_signoff_csv.mjs` |
| Rehearsal library (`Createlee_system_library/evidence/`) | **NOT ACCEPTABLE** — 3 PASS, 1 PASS_WITH_FINDINGS, 4 FAIL | `validate_signoff_csv.mjs` |
| Failed model output (`external docs for clients/`) | **NOT ACCEPTABLE** — 1 PASS, 7 FAIL | `validate_signoff_csv.mjs` |
| Deep verification report | `Createlee_deep_verification_report.txt` (72 checks test the Createlee platform, not the Signoff CSV acceptance contract) | repo root |

> [!CAUTION]
> **Two different things.** The deep report's 72 checks test the **Createlee platform**, not the Signoff CSV acceptance contract. Do not treat "72/72 PASS" as the library passing the validator — the library copy fails 4/8 against `validate_signoff_csv.mjs`.

## Run it

```bash
# Validate the golden acceptance set (ACCEPTABLE)
node opencode_next_step_kit/validate_signoff_csv.mjs \
  opencode_next_step_kit/golden_examples/

# Validate the rehearsal library (NOT ACCEPTABLE — 4 FAIL expected)
node opencode_next_step_kit/validate_signoff_csv.mjs \
  Createlee_system_library/evidence/
```

## Related work

- [Signoff — evidence-pack builder](https://github.com/Hatemshalaby15071979/Sign-off)
- [Portfolio and wider work](https://github.com/Hatemshalaby15071979)

## Author

Built by Hatem Shalaby, Contact Centre Operations & AI Implementation Lead | WFM & CX Transformation. Background: https://github.com/Hatemshalaby15071979

## Licence

MIT
