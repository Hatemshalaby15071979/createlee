# Changelog

All notable changes to CreateLee are recorded here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

CreateLee is a rehearsal library, not a released product: it carries no version tags and
closes no release gate. Entries are grouped by the date the change landed on `master`,
with the commit that carries it.

## 2026-11-27

### Added

- `tools/check_root_docs.py` — the root-document hygiene gate from GOVERNANCE.md
  section 2, checked in both directions (the documented root documents are present, and
  no unlisted `.md`/`.txt` sits at the root). Wired into CI, with a self-test that proves
  the gate fails closed.

### Fixed

- `CHANGELOG.md` itself: the GOVERNANCE.md section 2 table lists it and no such file
  existed.

## 2026-11-26

### Changed

- Unified governance set (`4f7e2af`): added `AGENTS.md` (agent charter and ledger),
  `CONSTITUTION.md` and `GOVERNANCE.md`; rewrote `README.md` in the house style with the
  `docs-sync` markers intact.
- Five one-off reports moved out of the root into `docs/archive/`
  (`Createlee_SELF_ASSESSMENT_2026-11-07.md`, `Createlee_deep_verification_report.txt`,
  `Createlee_verification_report.txt`, `HISTORY_REWRITE_AUTHORIZATION.md`,
  `REQUESTED-FILES-AND-GAPS.md`).

## 2026-11-22

### Changed

- `README.md`: the canonical Helix Solutions logo in the header, a "by Helix Solutions"
  line, and a house-style version tag (`deabfe0`, `068cf5c`, `730021e`, `e448090`,
  `12d46b6`).

## 2026-11-13

### Added

- Security baseline: gitleaks secret scanning and CodeQL analysis workflows, with the
  synthetic upload CSVs allowlisted (`6bd939c`, `dbb4c2b`, `25b604c`, `c175e27`,
  `dafd0ba`).
- Duplicate-file and committed-manifest checks wired into CI (`b988ff3`).

### Fixed

- Documentation and CI claims made honest: the audit-ledger findings were addressed and
  unsupported claims removed (`9e2f9b7`, `b988ff3`, `64cb0b2`).

## 2026-11-11

### Fixed

- CI now runs the real Signoff CSV validator over the golden examples, and a second step
  proves the validator fails closed on a directory that does not exist (`48af797`).
- Licence and provenance hand-off restored (`48af797`).

## 2026-11-10

### Added

- The `docs-sync` documentation engine, so the README's status block cannot drift from
  the repository state (`d5030e8`).

### Changed

- Visitor-facing docs simplified — same facts, friendlier and shorter (`ecac918`).

### Fixed

- `email_client_package` referenced an undefined `st` (`5996bc8`).
