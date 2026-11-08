# Requested files by project — Createlee hand-off packs

This is the definitive list of files Createlee must generate so that the
client can replace only their own rows and send them back for Signoff.

Generated: 2026-11-06T23:38:19Z (ISO-8601 UTC)

| Project | Generatable files | Org-only / not generatable |
|---|---|---|
| Signoff — 8 operational evidence exports | 8 | 0 |
| Helix-Codex (Helix-Prime) — nine production gates | 5 | 6 |
| live-support-assistant — corpus + expected-outcome labels | 3 | 6 |
| CompliProof — two reconciled exports + P0 evidence checklist | 2 | 7 |

## Per-project detail

### Signoff — 8 operational evidence exports

Input B for the Signoff gate. These 8 files are the evidence that unblocks the signed_production_evidence gate for Helix-Codex and supplies the ownership / on-call gates.

- `qa_reviews.csv` — Every AI-proposed QA action reviewed by a named human
- `ai_audit_log.csv` — Kill switch / access revocation / access review / retention / PII log checks
- `ai_approvals.csv` — AI-proposed decisions named by approver
- `escalations.csv` — Escalations go only to authorised supervisors
- `role_spec.csv` — Named accountable person + least-privilege roster
- `ai_inventory.csv` — AI provider inventory + signed no-training contract term
- `ai_training.csv` — Staff AI-training completed + verified
- `incident_notifications.csv` — Incident notifications within SLA with named owner

### Helix-Codex (Helix-Prime) — nine production gates

Each gate needs <gate>.evidence.json + .sig stored OUTSIDE the repo, scope production, signed with a key the audited system does not hold.

- `gate-evidence/signed_production_evidence.evidence.json` — A cryptographically signed evidence pack produced by an off-system key.
- `gate-evidence/certified_data_isolation.evidence.json` — Independent certification of tenant/data isolation at production scale.
- `gate-evidence/external_observer_audit.evidence.json` — Third-party audit of the control plane and audit chain.
- `gate-evidence/production_deployment_architecture.evidence.json` — Approved production deployment topology and review sign-off.
- `gate-evidence/disaster_recovery_evidence.evidence.json` — Validated DR / backup plan exercised against the production environment.
- `gate-evidence/operational_ownership.evidence.json` — Named production operations owner and rotation.
- `gate-evidence/incident_oncall_ownership.evidence.json` — Named production on-call and escalation contract.
- `gate-evidence/security_review.evidence.json` — Completed independent security review / penetration test.
- `gate-evidence/legal_privacy_review.evidence.json` — Legal and data-privacy review for the production jurisdiction.
- `operational_ownership.csv` — Named accountable person + least-privilege roster
- `incident_oncall_ownership.csv` — Incident/on-call ownership with named owner

**Not generatable / org-only:**

- certified_data_isolation — needs an appointed certification body
- external_observer_audit — needs an independent auditor
- production_deployment_architecture — needs an infrastructure review
- disaster_recovery_evidence — needs a real production DR test
- security_review — needs a signed independent security review
- legal_privacy_review — needs legal sign-off

### live-support-assistant — corpus + expected-outcome labels

The evidence that lets the assistant be evaluated against the client's own procedures and a labelled ticket sample.

- `procedure_corpus.csv` — The SOPs/knowledge base the assistant answers from
- `procedure_corpus.json` — Same corpus in JSON form (either form is accepted)
- `expected_outcome_labels.csv` — Labelled ticket outcomes for evaluation

**Not generatable / org-only:**

- Tenant isolation proof — needs an authenticated cross-tenant negative control
- Authenticated end-to-end flow evidence — needs a hosted runtime
- Hosted telemetry / escalation transport evidence
- External security audit
- Billing integration evidence
- Per-tenant threshold calibration record (0.18 is a starting point, not validated)

### CompliProof — two reconciled exports + P0 evidence checklist

Run the reconciliation command against the client's two systems. The 7 P0 production gates are infrastructure evidence, NOT CSVs.

- `system_a.csv` — System A side of the reconciliation
- `system_b.csv` — System B side of the reconciliation
- `reconciliation_report.csv` — Expected reconciliation shape (matched / A-only / B-only / mismatched)
- `P0_EVIDENCE_CHECKLIST.csv` — The 7 open P0 gates and exactly what closes each one

**Not generatable / org-only:**

- P0-1 Packaging / deployment — NO — needs a hosted CI run and a clean-runner install matrix
- P0-2 Evidence integrity — NO — needs an independent reviewer and a non-symmetric key lifecycle
- P0-3 Audit ledger — NO — needs an external timestamp anchor receipt (e.g. freetsa)
- P0-4 Reporting / reconciliation — PARTIAL — the two CSVs let you run the reconciliation; the served report and audit event must be produced by CompliProof itself
- P0-5 Server reporting — NO — needs routes, auth and a security scan
- P0-6 Authentication — NO — needs a real auth implementation and security review
- P0-7 Dashboard / UI security — NO — needs a browser acceptance test and route inventory
