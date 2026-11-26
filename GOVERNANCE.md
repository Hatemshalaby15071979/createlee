# GOVERNANCE.md — Operating Policy & Repo Map for CreateLee

> Companion to `CONSTITUTION.md` (the *why* — philosophy and clean-code policy, which
> this file enforces operationally) and `AGENTS.md` (the agent charter + ledger).
> Read all three before acting. This file may be updated by any agent **as a logged
> governance change** to keep the map and policy truthful; the CONSTITUTION itself is
> owner-only.

## 1. Repository map

Authoritative directory map for **CreateLee**. Any file you add, move, rename, or
delete gets reflected here in the same landing.

| Path | Purpose (one line) |
|---|---|
| `opencode_next_step_kit/` | The golden acceptance examples, the CSV validator, provenance records, and the Signoff hand-off files. |
| `opencode_next_step_kit/golden_examples/` | The ACCEPTABLE reference set — point every run here. |
| `Createlee_platform/` | The CreateLee platform app (local Flask service, loopback-only) and its own tests. |
| `Createlee_system_library/` | The older rehearsal library (labeled NOT ACCEPTABLE — 4 of 8 files fail the validator). |
| `external docs for clients/` | A failed model-output copy of the eight exports (7 of 8 FAIL) — kept labelled, not hidden. |
| `tools/` | Maintenance scripts: duplicate check, index regeneration, agent-instruction-file (ME-15) guard. |
| `docs/` | Standing docs (nothing yet). |
| `docs/archive/` | Dated one-off reports: self-assessment, deep/local verification reports, history-rewrite authorization, requested-files gaps. |
| `index.html` | House-style landing page (mirrors the README; `docs-sync` blocks engine-managed). |
| `.github/` | CI, CodeQL, secret scan, dependabot, and the release-triggered docs-sync workflow. |
| `_docs_profile.json` | The docs-sync profile (status template + facts the engine rewrites on release). |
| `environment.yml` | Conda environment for local development. |
| `SECURITY.md` | Threat model and vulnerability reporting. |
| `LICENSE` | MIT. |
| `.gitignore`, `.gitleaks.toml` | Ignore list and secret-scan rules. |

Note: `Createlee_platform/Createlee/CREATELEE_CONSTITUTION.md` is *application data*
(loaded by the app and guarded by `tools/verify_agent_instruction_files.py`), not a
governance document — it stays where the app expects it.

## 2. Documentation policy (what belongs where)

**Root holds only the requested set** — nothing else:

| File | State | Purpose |
|---|---|---|
| `README.md` | required | The single source of truth: what this is, why it's here, how to use it — in simple English for a professional reader. Carries the Helix Solutions logo. |
| `AGENTS.md` | required | Agent charter + sign-in/out ledger. |
| `CONSTITUTION.md` | required | The owner's engineering philosophy and clean-code policy (unified across every repo). |
| `GOVERNANCE.md` | required | This file: repo map, documentation policy, sync policy, archiving rules. |
| `CHANGELOG.md` | standard | Dated user-visible changes. |
| `LICENSE` / `LICENSE.md` | standard | MIT, unless the repo states otherwise. |
| `SECURITY.md` | standard | Threat model, vulnerability reporting, secret handling. |

**Everything else lives in `docs/`** — reports, audit logs, execution plans, research
notes, ADRs, runbooks, anything dated or one-off. No stray `.md`/`.txt` at the root.
If a document at the root is not in the table above, move it to `docs/` (or
`docs/archive/` if it is historical) and record the move in the `AGENTS.md` ledger.

## 3. Synchronization & harmony policy

The owner's rule: **the repository's actual status must match its README at all times,
locally and remotely.**

1. `README.md` is the canonical account. Landing pages (`index.html`) and dashboards
   mirror it; they never fork it.
2. When reality changes, update `README.md` **first**, then mirror it to the pages.
3. Every sanctioned change is committed **and pushed** to the default branch, so the
   GitHub copy, the local working copy, and any local platform that reads the repo
   all show the same truth.
4. A number published anywhere (README, page, badge) must be reproducible from this
   repository. A stale figure is removed, not left to rot.
5. The workspace tool `readme-sync/` (in `Repos_Readmes`) verifies that every public
   repo's README matches its local clone. Keep this repo's README in a state it reports
   as matching.

## 4. Archiving rule

- Archive (move to `docs/archive/`), never delete: historical reports, superseded plans,
  dated audits, and one-off execution logs.
- Delete outright only regenerable artifacts: caches, build output, coverage files.
- Record every move in the `AGENTS.md` ledger with date and time.

## 5. Engineering philosophy & clean-code policy (operational summary)

The full text is `CONSTITUTION.md`. The operational reminders, enforced here:

- **Fail closed.** Missing input or missing authority is a refusal, never a default.
- **Evidence before claims.** Published numbers carry a command, a date, and an artifact.
- **No duplicates, no temp files, one file one job, every file explains itself.**
- **Secrets never enter the tree.**
- **Simple English** in code, docs, and UI, so a non-technical professional reader
  (recruiter, partner) can follow.
- **One brand mark:** the Helix Solutions logo, everywhere.

## 6. Definition of done

It works; it has a test or a documented manual check; the `AGENTS.md` ledger has an
entry; the docs reflect the new reality; no temporary file was left behind; and every
published number can be re-run to reproduce itself.
