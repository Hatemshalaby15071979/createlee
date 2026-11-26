<div align="center">

<img src="https://raw.githubusercontent.com/Hatemshalaby15071979/Helix-Solutions/main/assets/helix-solutions-logo.png"
     alt="Helix Solutions" width="72" height="72">

# CreateLee

CreateLee is a practice library of *synthetic* (fake, clearly labelled) CSV exports —
the eight kinds a contact-centre project hands to the Signoff evidence gate — plus the
validator that checks their shape. It lets you rehearse the "how did AI touch our
customers?" audit end to end before any real client data arrives.

*by Helix Solutions*

</div>

## What this is and why it's here

Signoff (a sibling project that answers *"how did AI touch our customers?"* with an
evidence pack) needs realistic data to prove it works — but real client exports carry
secrets and cannot be shared freely. So CreateLee exists as the rehearsal ground: eight
kinds of CSV exports per project (QA reviews, audit events, approvals, escalations, role
specs, AI inventory, training records, incident notifications), a validator, and a set
of golden examples that show what "good" looks like.

Every row here is simulated. Nothing in this repository is a client record, and it
closes no production gate. The value is the shape and the discipline, not the data.

<!-- docs-sync:start -->
**CreateLee — Signoff rehearsal library (synthetic fixtures, no release).** No hosted
Actions result exists for this candidate; this checkout contains the Signoff rehearsal
library and its validator only. The golden acceptance set is ACCEPTABLE (6 PASS,
2 PASS_WITH_FINDINGS) while the rehearsal-library copy fails 4 of 8 against the
validator. @DOCS_SYNC_CI@, and data provenance is unverified.
<!-- docs-sync:end -->

## What you get

- **The golden examples** — an ACCEPTABLE reference set (verified locally 2026-11-06:
  6 PASS, 2 PASS_WITH_FINDINGS, 0 FAIL). Point every future run at this.
- **A validator** — checks the export shapes file by file and reports PASS /
  PASS_WITH_FINDINGS / FAIL, so a format problem is caught before it reaches Signoff.
- **Honest warnings, kept visible** — an older rehearsal-library copy fails 4 of 8
  against the validator, and a failed model-output copy fails 7 of 8. Both are
  labelled, not hidden, so nobody mistakes them for a source of truth.
- **A provenance trail** — every golden file is declared synthetic, per file, with a
  SHA-256 in `opencode_next_step_kit/provenance.json`.
- **A clean hand-off to Signoff** — the 12-question questionnaire and a *draft*
  question→evidence mapping. The mapping stays unsigned (`decided_by=PENDING_OWNER_SIGNATURE`)
  on purpose: Signoff refuses to build a pack from an unsigned mapping, because a
  machine must not sign a human's accountability statement.

## How to use it

1. **Run the validator on the golden examples** — this should come back ACCEPTABLE:

   ```bash
   node opencode_next_step_kit/validate_signoff_csv.mjs opencode_next_step_kit/golden_examples/
   ```

   What it does for you: proves the target set is structurally sound on your machine,
   in seconds, with no network.

2. **Run it on the older rehearsal library** — 4 FAILs are *expected*; the labels, not
   the pass, are the point:

   ```bash
   node opencode_next_step_kit/validate_signoff_csv.mjs Createlee_system_library/evidence/
   ```

   What it does for you: shows what a failing copy looks like, so the difference is
   obvious instead of argued about later.

3. **Read the hand-off pair before any real sign-off** — the questions the pack must
   answer, and the draft mapping that a named person must sign:

   - `opencode_next_step_kit/questionnaire.csv`
   - `opencode_next_step_kit/signoff-mapping.draft.csv`

   What it does for you: the rehearsal ends with a real, owner-signed step — never an
   automated one.

CI runs the validator on every push (`.github/workflows/ci.yml`) and also proves the
validator fails closed when its input folder is missing.

## The rules we build by

CreateLee obeys `CONSTITUTION.md`: **fail closed** (the validator refuses a missing or
malformed input instead of guessing), **honest about limits** (every row is tagged
`simulated`; rehearsal data is labelled rehearsal), and **a human is always in charge**
(the sign-off mapping stays unsigned until a named owner signs it). Details live in
`CONSTITUTION.md`.

## Current status

**As of 2026-11-06** (local verification on `master`): the golden acceptance set is
ACCEPTABLE (6 PASS, 2 PASS_WITH_FINDINGS, 0 FAIL); the rehearsal-library copy fails 4
of 8 and the external-docs copy fails 7 of 8 — both labelled. Hosted GitHub Actions has
not yet run on this candidate, and data provenance is unverified. Everything here is
synthetic and closes no production gate.

## Where things live

- `opencode_next_step_kit/golden_examples/` — the golden acceptance set (the target to beat).
- `opencode_next_step_kit/provenance.json` — per-file synthetic declarations with SHA-256.
- `opencode_next_step_kit/questionnaire.csv` + `signoff-mapping.draft.csv` — the Signoff hand-off (unsigned by design).
- `Createlee_system_library/` and `external docs for clients/` — the two non-golden copies, labelled NOT ACCEPTABLE.
- `tools/` — maintenance and guard scripts (duplicate check, index regeneration, ME-15 agent-file guard).
- `docs/archive/` — the dated verification reports and self-assessment behind the status above.

## Licence & contact

MIT. Built by Hatem Shalaby — Contact Centre Operations & AI Implementation Lead |
WFM & CX Transformation.

- **GitHub:** [github.com/Hatemshalaby15071979](https://github.com/Hatemshalaby15071979)
- **LinkedIn:** [linkedin.com/in/hatem-shalaby-202902127](https://www.linkedin.com/in/hatem-shalaby-202902127/)
- **Related work:** [Signoff — evidence-pack builder](https://github.com/Hatemshalaby15071979/Sign-off)
