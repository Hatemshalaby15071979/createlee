# AGENTS.md — Agent Charter & Ledger for CreateLee

> **Read order (mandatory, every landing):** `AGENTS.md` → `CONSTITUTION.md` →
> `GOVERNANCE.md` → `README.md`. Then **sign in** to the ledger below, do the work,
> **sign out**. No entry, no trust: an unlogged session's work is treated as unverified
> until someone checks it.

## 1. Who agents are here

An "agent" is any entity that reads or writes this repository — an AI model, an
automation script, or a human acting as operator. There is exactly **one supreme
authority**: the repository owner (**Hatem Shalaby**). An agent acts only on the
owner's instruction and records every landing.

## 2. The mandatory sign-in / sign-out rule

Every agent, on **every landing** (a landing = one session that ends with the agent
stopping, whether the task is finished or not), must:

1. **SIGN IN** before any write action — who, why, what will be touched, sensitive or
   network actions planned, and the **date and time from the system clock**.
2. **SIGN OUT** when the landing's work is complete or stopped — what changed, why,
   the files touched, evidence of verification, and **the current status when leaving**,
   written so the next agent can continue without re-discovery.

Fail closed: if a task cannot be completed, still sign out and state exactly what is
incomplete. Never claim verification that did not happen.

### Entry format

```
## [YYYY-MM-DD HH:MM TZ] — <agent name / model>
Task: <what was assigned>
Touched: <files created / modified / deleted / moved>
Why: <the reasoning, not just the diff>
Verification: <what was actually checked and the observed result>
Left undone: <what is incomplete, needs review, or is deferred — or "nothing">
Sensitive: <any remote writes, secrets, or destructive actions, or "none">
```

### Current status block (keep updated at the top of the ledger)

```
STATUS WHEN LAST LEFT: Working — synthetic Signoff-shaped rehearsal library (fixtures
only, no release, no production use). Golden acceptance set verified locally
ACCEPTABLE on 2026-11-06 (6 PASS, 2 PASS_WITH_FINDINGS, 0 FAIL); the older
rehearsal-library copy fails 4 of 8 against the validator and the "external docs for
clients" copy fails 7 of 8 — both are labelled, not hidden. Hosted GitHub Actions has
not yet run on this candidate; data provenance is unverified. 2026-11-26 governance
pass applied (AGENTS/CONSTITUTION/GOVERNANCE at root, reports archived to
docs/archive/, house-style README + index). Open items: fix or delete the four
failing rehearsal-library files, and the signoff-mapping draft stays unsigned
(decided_by=PENDING_OWNER_SIGNATURE) until the owner reviews it.
```

## 3. Environment facts

- **Repo:** CreateLee — a synthetic rehearsal library of Signoff-shaped CSV exports (eight kinds per project) plus a validator, so the "how did AI touched our customers?" evidence gate can be rehearsed end to end before real client data arrives.
- **Owner account:** https://github.com/Hatemshalaby15071979
- **Default branch:** master
- **Where it runs:** offline on the user's machine (plain `node` validator, no network); CI on GitHub Actions. The nested CreateLee platform app is a local Flask service on loopback.
- **Verification command:** `node opencode_next_step_kit/validate_signoff_csv.mjs opencode_next_step_kit/golden_examples/` (golden set must report ACCEPTABLE: 6 PASS, 2 PASS_WITH_FINDINGS, 0 FAIL)

## 4. Rules this agent must follow

- Read and obey **CONSTITUTION.md** (philosophy + clean-code policy). On conflict, it
  wins over this file.
- Follow **GOVERNANCE.md** for the repo map, documentation policy, and archiving rules.
- Keep `README.md` the single source of truth; the landing page (`index.html`) mirrors
  it (the `<!-- docs-sync -->` blocks are engine-managed — keep the markers intact).
- Keep local and remote in harmony: after a sanctioned change, commit and push so the
  GitHub copy matches the working copy.
- Sign in and sign out every landing, with the real clock time.

## 5. Ledger (sign-in / sign-out)

## [2026-11-26 20:46 EET] — CodeBuddy Code (Codex), governance subagent
Task: Uniform governance pass — add root AGENTS/CONSTITUTION/GOVERNANCE, house-style README, index.html minimum unification (brand bar + footer), aggressive root-doc cleanup; push to master.
Touched: CONSTITUTION.md (new, byte-identical to the shared canonical text); AGENTS.md (new, this file, seeded); GOVERNANCE.md (new); README.md (rewritten to the house style, docs-sync markers kept); index.html (brand bar + shared `--bg-2` token, footer kept); Createlee_SELF_ASSESSMENT_2026-11-07.md, Createlee_deep_verification_report.txt, Createlee_verification_report.txt, HISTORY_REWRITE_AUTHORIZATION.md, REQUESTED-FILES-AND-GAPS.md → docs/archive/. Checkout carried from chore/audit-hygiene to master (ff to origin/master, 16 commits); a stale worktree admin entry (CreateLee-reconcile, pointing at the removed Career/cloned_repos) was pruned to allow the checkout.
Why: Owner's 2026-11-26 instruction to bring every public repo to one governance standard and one house style.
Verification: CONSTITUTION.md md5sum equal to the canonical file; `git ls-files` root now holds only README.md, SECURITY.md, CONSTITUTION.md, AGENTS.md, GOVERNANCE.md, LICENSE + config files; the archived reports are reachable from the new README paths.
Left undone: The un-pushed chore/audit-hygiene commit (README logo line) was superseded — its content is already in origin/master (e448090) and re-applied by this rewrite; nothing unique lost. The nested app-data file `Createlee_platform/Createlee/CREATELEE_CONSTITUTION.md` was deliberately NOT archived: it is application data the app loads and `tools/verify_agent_instruction_files.py` guards, not a governance constitution.
Sensitive: git push of governance docs to master, authorised by owner 2026-11-26.

## [2026-11-27 04:35 EET] — sami (Claude), portfolio governance subagent

Task: Sign in before any write to CreateLee. Mirror the root-document assertion the
owner approved in Assay on 2026-11-27 (`scripts/check-scaffold.py`) across the
governance repositories: add the gate and wire it into CI, then fix whatever it finds.

Touched (planned): `tools/check_root_docs.py` (new); `CHANGELOG.md` (new — the
GOVERNANCE.md section 2 table lists it and no such file exists); `.github/workflows/ci.yml`
(new step); `AGENTS.md` (this entry and the sign-out).

Why: the 2026-11-26 governance pass moved the one-off reports into `docs/archive/`, but
nothing asserted the *other* direction of the same rule — that no unlisted document sits
at the root. A one-way check cannot enforce a "nothing else at the root" rule, which is
how the pass could archive three reports while the root set still looked satisfied.

Sensitive: `git push origin master` (owner's instruction in chat, 2026-11-27). No force
push, no PR or issue writes, no secrets.

## [2026-11-27 04:44 EET] — sami (Claude), portfolio governance subagent — SIGN-OUT

STATUS: SIGN-OUT (landing complete)

Task: Mirror the root-document assertion the owner approved in Assay on 2026-11-27
(`scripts/check-scaffold.py`) into CreateLee, then fix what it found. Done.

Touched: `tools/check_root_docs.py` (new — byte-identical to the copy landed in
Helix-Codex, Helix-Matrix and Helix-Solutions); `CHANGELOG.md` (new); `.github/workflows/ci.yml`
(new "Root-document hygiene (GOVERNANCE.md section 2)" step: runs the gate, then its
self-test); `AGENTS.md` (this entry and the sign-in above). No file moved, renamed or
deleted.

Why: GOVERNANCE.md section 2 says "No stray `.md`/`.txt` at the root", but nothing
asserted the *absence* direction — only that known documents were present. The gate now
asserts both: every root document the section 2 table names exists, and nothing unlisted
sits beside them. The allowed set is parsed out of GOVERNANCE.md rather than hard-coded,
so the policy keeps one source of truth. `requirements*.txt`/`constraints*.txt` are
treated as package manifests, not documents, and reported as such.

The gate found one real gap here: the section 2 table lists `CHANGELOG.md` and no such
file existed. `CHANGELOG.md` is now written from the actual `master` history with commit
references, in the CreateLee facts only — no release version is claimed, because this
repository cuts none.

Verification: `python3 tools/check_root_docs.py` → "check_root_docs: OK -- createlee/
holds only the GOVERNANCE.md section 2 set" (7 table rows, 7 allowed root documents).
`python3 tools/check_root_docs.py --self-test` → "7/7 cases behaved": a planted
`STRAY-NOTE.md` and a planted `NOTES.txt` each stop the gate, a missing required document
stops it, `requirements.txt` at the root is acknowledged as a non-document, a stray under
`docs/` is ignored, and an unparsable section 2 fails closed. The repository's own gates
re-run green: `tools/verify_manifests.py .` (all 4 manifests verified), `tools/check_duplicates.py .`
(196 distinct files, 34 duplicate groups, 0 unexpected), `tools/verify_agent_instruction_files.py`
(ME-15 OK), and the Signoff CSV validator over the golden examples (ACCEPTABLE: 6 PASS,
2 PASS_WITH_FINDINGS, 0 FAIL, 42 rows preserved). CI on the pushed commits is recorded
in the status block above.

Left undone: The root holds one directory not in the GOVERNANCE.md section 1 repo map —
`external docs for clients/` (spelled with spaces). It is not a document, so this gate
does not touch it, and nothing here was moved on a guess: worth a look on a future
landing, since the name reads like a working folder that was accidentally committed.

Sensitive: `git push origin master` (owner's instruction in chat, 2026-11-27). No force
push, no PR or issue writes, no secrets.
