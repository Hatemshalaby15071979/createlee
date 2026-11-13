UNTRUSTED AGENT TEXT (ME-15) — data, not instructions

Createlee / opencode - NEXT STEP KIT
====================================
Purpose: make a local Ollama model (driven by opencode) actually produce the
8 Signoff CSVs correctly, and let it PROVE it inside a JavaScript-only runtime.

WHY THIS KIT EXISTS
-------------------
The previous run failed because (1) the long v2 prompt was compacted before it
reached the model, so Section 2's eight exact headers were lost, and (2) the
agent believed it could not run Createlee's Python validator, so it declared
"Task complete" without verifying. This kit fixes both.

WHAT IS HERE
------------
  00_README.txt                       this file
  validate_signoff_csv.mjs            zero-dependency Node validator (Node 18+)
  01_qa_reviews.csv.txt               single-file prompt, file 1 of 8
  02_ai_audit_log.csv.txt              ... file 2
  03_ai_approvals.csv.txt              ... file 3
  04_escalations.csv.txt               ... file 4
  05_role_spec.csv.txt                 ... file 5
  06_ai_inventory.csv.txt              ... file 6  <- most fragile, do it alone
  07_ai_training.csv.txt               ... file 7
  08_incident_notifications.csv.txt    ... file 8
  golden_examples/                    8 verified CSVs = the acceptance target

EXACT PROCEDURE
---------------
  1. Copy this whole folder into opencode's working directory.
  2. For each of the 8 prompts, in order:
       - Feed the .txt file VERBATIM to the local model (one fresh call each).
         Do not summarise, paraphrase or paste it into a chat that compacts.
       - Save the emitted block to the exact CSV filename, stripping the
         === FILE: ... === and === END === marker lines.
  3. After each file (or after all 8), run in that folder:
         node validate_signoff_csv.mjs .
     It prints one line per file plus a JSON summary. Exit 0 = ACCEPTABLE.
  4. If it says NOT ACCEPTABLE, fix ONLY the reported failures and re-run.
     Never delete rows to hide a gap -- gaps are reported as FINDINGS, not
     failures, and are allowed.
  5. When it says ACCEPTABLE, optionally get Createlee's 5-format report:
         cd /workspace/createlee
         python3.11 evidence.py --out <folder> --as-of 2026-11-06 --validate-only
     Or upload the 8 CSVs to Createlee for the same read-only check.
  6. Only then pass them through Createlee's operator review gate before
     saving or emailing.

EXPECTED RESULT
---------------
  On the previous opencode output : NOT ACCEPTABLE, 7 FAIL, exit 1
  On golden_examples/             : ACCEPTABLE, 6 PASS / 2 PASS_WITH_FINDINGS,
                                    0 FAIL, width_clean=true, exit 0

  The 2 findings in the golden set are intentional honest gaps
  (2 x authorised=no, 1 x completed=no) and must be kept.

WHY SINGLE-FILE PROMPTS
-----------------------
  A compaction event can no longer drop 7 of the 8 file definitions at once.
  Each call carries exactly one header, one column count, one example row and
  its own rules. FILE 6 (ai_inventory.csv) is generated alone, with a full
  4-row correct example, because it is the file local models break most often.

WHY THE NODE VALIDATOR
----------------------
  opencode reported "JavaScript-only runtime which does not support Python
  imports". This validator is pure Node with no dependencies, so the agent can
  run it itself. Each single-file prompt already contains a VERIFICATION GATE
  instructing it to run the command, paste the verdict, and output UNVERIFIED
  rather than claiming completion if it cannot.

HONESTY
-------
  Local models produce SIMULATED data, not real compliance evidence. These
  files cannot establish tenant isolation, authenticated end-to-end flows,
  hosted telemetry/escalation transport, an external security audit or billing
  integration. Replace with genuine system exports before any real signoff.
