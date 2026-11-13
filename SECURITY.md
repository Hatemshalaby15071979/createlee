# Security Policy

## Scope

This repository contains a synthetic rehearsal library for the Signoff evidence
gate: export-shaped CSV fixtures, a validator, and golden acceptance examples.
The data is simulated. It is not client records and not production evidence.

## Reporting a vulnerability

Please do **not** open a public issue for a security problem.

Use GitHub's private reporting flow for this repository:

1. Open the **Security** tab.
2. Choose **Report a vulnerability** (GitHub Security Advisories).
3. Describe the issue, the affected path or workflow, and the steps to
   reproduce it.

The report is visible only to the maintainers. You will get a reply in the
advisory thread once the report has been triaged.

## Supported versions

The default branch (`master`) is the only supported line. Fixes land there;
older branches are not maintained.

## What is already in place

- CodeQL static analysis on pull requests, on `master`, and weekly.
- gitleaks secret scanning on pull requests, on `master`, daily over full
  history.
- Dependabot updates for pip and GitHub Actions.
- Workflow actions pinned to commit SHAs.

## Out of scope

- Findings that require a secret or credential that is already committed. Those
  are handled as history remediation, not as a vulnerability report.
- The synthetic fixtures themselves. They contain no real personal data.
