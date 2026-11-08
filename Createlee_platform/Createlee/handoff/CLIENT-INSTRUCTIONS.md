CLIENT INSTRUCTIONS — how to fill these files
=============================================

WHAT WE ARE ASKING YOU TO DO
----------------------------
Every file in this folder is a real, working example with simulated rows. It is
already in the exact format the verification tool expects. Replace ONLY the data
rows with your own rows. Keep everything else identical.

RULES — do not break these
--------------------------
1. DO NOT change the header row. Column names, order and spelling must match
   exactly. If a column does not apply to you, leave it in place and put a value
   (or an empty value where the column allows it) — never delete the column.
2. DO NOT add or remove columns.
3. Replace the example rows with your rows. A file must keep at least the
   minimum row count shown in REQUEST_LIST.md.
4. Use lowercase `yes` / `no` for boolean columns. Not "Yes", not "Completed",
   not "TRUE".
5. Timestamps must be ISO-8601 with a timezone offset, e.g.
   2026-10-05T09:12:00+02:00. Do not use Excel date serials.
6. DO NOT delete rows to make a gap disappear. Gaps are reported as honest
   findings, and a missing row is itself a finding.
7. Keep the exact filename. Do not rename to `qa_reviews (1).csv`.
8. Save as UTF-8 CSV. If your system exports Excel content with a `.csv`
   extension we can read that too — do not "fix" the encoding yourself.

WHAT WE WILL DO WITH THE FILES
------------------------------
We run the verification tool against them. It reports, per question:
  - Yes, with evidence
  - Gap (what is missing and why)
  - Not applicable (no events in the window)
Nothing is edited on your behalf and no row is ever deleted. The result is a
signed pack that records exactly what was evidenced and what was not.

PRIVACY
-------
Your name and organisation will not appear in any public document. Files stay
outside the source repository and are never committed.

WHAT THESE FILES CANNOT PROVE
-----------------------------
Some production gates are organisational, not data: tenant-isolation
certification, external audit, deployment architecture review, disaster-recovery
testing, security review and legal/privacy review. No CSV can close those. They
are listed per project in REQUEST_LIST.md and will be reported as open until the
relevant signed document exists.
