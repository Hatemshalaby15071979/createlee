<div align="center">
  
<img src="https://raw.githubusercontent.com/Hatemshalaby15071979/Helix-Solutions/main/assets/helix-solutions-logo.png" alt="Helix Solutions" width="72" height="72" style="margin-bottom:0.5rem">

# CreateLee

<!-- badges:start -->

![licence](https://img.shields.io/badge/licence-MIT-blue)
![local verification](https://img.shields.io/badge/local%20verification-format%20rehearsal-blue)

*Local verification measured 2026-11-06 on `master`; every `INDEX.csv` row is tagged `simulated`. This is a synthetic rehearsal library, not a client record and not production evidence.*

<!-- badges:end -->

</div>

<p float="left">
  <strong>CreateLee<br></strong><br>
  <span style="font-size:0.9em;color:#93aaa0">by Helix Solutions</span>
</p>

## What is this?

<!-- docs-sync:start -->
**CreateLee — Signoff rehearsal library (synthetic fixtures, no release).** No hosted Actions result exists for this candidate; this checkout contains the Signoff rehearsal library and its validator only. The golden acceptance set is ACCEPTABLE (6 PASS, 2 PASS_WITH_FINDINGS) while the rehearsal-library copy fails 4 of 8 against the validator. Hosted GitHub Actions has not yet run on this candidate, and data provenance is unverified.
<!-- docs-sync:end -->

CreateLee is the practice ground for [Signoff](https://github.com/Hatemshalaby15071979/Sign-off) — the tool that answers *"how did AI touch our customers?"* with an evidence pack.

Before real client exports arrive, you need realistic fake data to rehearse with. That's exactly what this is: **eight kinds of CSV exports per project** (QA reviews, audit events, approvals, escalations, role specs, AI inventory, training records, incident notifications), a validator, and a set of golden examples that show what "good" looks like.

**All of the data here is simulated.** Nothing in this repository is a client record, and it closes no production gate.

## Current status — read this first

Three copies of the same eight exports live here, and they are **not** equally good:

| Set | What it is | Validator verdict |
| --- | --- | --- |
| `opencode_next_step_kit/golden_examples/` | Golden acceptance target | **ACCEPTABLE** — 6 PASS, 2 PASS_WITH_FINDINGS, 0 FAIL |
| `Createlee_system_library/evidence/` | Older rehearsal library | **NOT ACCEPTABLE** — 4 files FAIL |
| `external docs for clients/` | Failed model output | **NOT ACCEPTABLE** — 7 of 8 FAIL |

**Point every run at the golden examples.** The older library fails four files (`ai_approvals.csv`, `ai_inventory.csv`, `ai_training.csv`, `incident_notifications.csv`) — fix or delete them so nobody mistakes them for a source of truth.

One more honest note: a separate "72/72 PASS" verification report exists in this repo, but those checks test the Createlee *platform*, not the CSV acceptance contract. Don't read it as the library passing the validator — it doesn't.

## Run it

```bash
# The golden examples (should be ACCEPTABLE)
node opencode_next_step_kit/validate_signoff_csv.mjs opencode_next_step_kit/golden_examples/

# The older rehearsal library (NOT ACCEPTABLE — 4 FAIL expected)
node opencode_next_step_kit/validate_signoff_csv.mjs Createlee_system_library/evidence/
```

CI runs this validator on every push (`.github/workflows/ci.yml`), and it also proves the validator fails closed on a missing folder. The local verdicts above (2026-11-06) are recorded in `Createlee_deep_verification_report.txt` and `Createlee_verification_report.txt`.

## Provenance and hand-off to Signoff

Every file in `opencode_next_step_kit/golden_examples/` is **synthetic** and is
declared so, per file and with a SHA-256, in
`opencode_next_step_kit/provenance.json`. Passing the validator is a structural
check on generated data; it is not compliance evidence.

The output is shaped for [Signoff](https://github.com/Hatemshalaby15071979/Sign-off)
as the readiness-attestation step. Two files make that hand-off explicit:

| File | Purpose |
| --- | --- |
| `opencode_next_step_kit/questionnaire.csv` | The 12 questions the pack answers |
| `opencode_next_step_kit/signoff-mapping.draft.csv` | Question → evidence-file mapping |

**The mapping is a DRAFT and every row says `verified=no`,
`decided_by=PENDING_OWNER_SIGNATURE`.** Signoff refuses to build a pack from an
unsigned mapping, and that refusal is the point: a machine must not sign a
human's accountability statement. The owner fills in `decided_by`, the date,
and `verified=yes` after reviewing the mapping.

## Related work

- [Signoff — evidence-pack builder](https://github.com/Hatemshalaby15071979/Sign-off)
- [Portfolio and wider work](https://github.com/Hatemshalaby15071979)

## Author

Built by Hatem Shalaby — Contact Centre Operations & AI Implementation Lead (WFM & CX transformation).

## Licence

MIT
