#!/usr/bin/env python3
"""Build the Helix-Codex external client pack from the REAL gate contract.

WHY THIS EXISTS
---------------
CreateLee's own `handoff.py` writes gate-evidence JSON in a shape it invented
(status / demand / generated_at_iso8601 / signature_instruction ...). Helix-Prime
does not read that shape. `release/production_evidence.py` reads exactly seven
fields and rejects everything else, so a pack built the old way gets filled,
signed, and returned by the client -- and still fails the gate. Verified
2026-11-09: 9 of 9 old templates rejected by the consumer.

This builder refuses to duplicate the contract (C18, one source of truth). It
delegates to Helix-Prime's own producer, `scripts/produce_production_evidence.py
template`, then re-checks every emitted document against the same
`validate_claims()` the gate uses. If Helix-Prime is not present it fails closed
instead of guessing.

USAGE
-----
    python3 helix-codex-build-pack.py --out helix-codex-production-pack \
        --helix /path/to/Helix-Prime \
        --template-source handoff/helix-codex
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

DEFAULT_HELIX = pathlib.Path(
    "[LOCAL_PATH]/[REDACTED_VOLUME]/Career/cloned_repos/Helix-Prime"
)

#: The gates the CLIENT's own organisation can close with real data + an
#: off-system signature. Everything else needs a named third party.
CLIENT_CLOSABLE = (
    "signed_production_evidence",
    "operational_ownership",
    "incident_oncall_ownership",
)

#: The eight operational evidence CSVs that make up the signed pack, in the
#: order `signed_production_evidence` declares them.
SIGNOFF_CSVS = (
    "qa_reviews.csv",
    "ai_audit_log.csv",
    "ai_approvals.csv",
    "escalations.csv",
    "role_spec.csv",
    "ai_inventory.csv",
    "ai_training.csv",
    "incident_notifications.csv",
)

#: Two ownership CSVs the client replaces rows in.
OWNERSHIP_CSVS = ("operational_ownership.csv", "incident_oncall_ownership.csv")

#: Sample payload per gate. Nothing here is an attestation: the payload is
#: deliberately unconstrained by the gate, and every field is a marked sample.
SAMPLE_PAYLOAD = {
    "signed_production_evidence": {
        "evidence_pack_id": "SIM-PACK-0001",
        "window_days": 90,
        "evidence_files": list(SIGNOFF_CSVS),
        "pack_sha256": "<64 hex -- computed by the operator after the CSVs return>",
    },
    "operational_ownership": {
        "owner_name": "SIM-OPS-01 (real name)",
        "role": "AI Ops Lead",
        "rotation": "weekly",
        "named_accountable": True,
    },
    "incident_oncall_ownership": {
        "oncall_owner": "SIM-NOC-01 (real name)",
        "escalation_path": "NOC duty manager -> AI Ops Lead -> GM Ops",
        "sla_minutes": 30,
        "contract_ref": "SIM-CONTRACT-0001",
    },
    "certified_data_isolation": {
        "certifying_body": "<name of the body that certified isolation>",
        "certification_id": "<their reference>",
        "test_method": "<how it was tested>",
        "production_scale_evidence": "<what scale was covered>",
    },
    "external_observer_audit": {
        "auditor": "<independent auditor / firm>",
        "audit_id": "<engagement reference>",
        "scope": "<what was audited>",
        "findings": ["<one entry per finding>"],
        "opinion": "<the auditor's opinion>",
        "report_sha256": "<64 hex of the signed report>",
    },
    "production_deployment_architecture": {
        "topology_diagram_sha256": "<64 hex>",
        "network": "<how the app is networked>",
        "tls": "<TLS termination and certificates>",
        "ha": "<replicas / failover>",
        "secrets_management": "<where secrets live and who can read them>",
        "reviewer": "<the infrastructure owner who approved it>",
    },
    "disaster_recovery_evidence": {
        "dr_test_date": "<date the test actually ran>",
        "rpo_minutes": None,
        "rto_minutes": None,
        "restore_log_sha256": "<64 hex of the restore log>",
        "operator": "<who ran it>",
    },
    "security_review": {
        "reviewer": "<firm / person>",
        "review_id": "<engagement reference>",
        "scope": "<what was tested, what was not>",
        "findings": ["<one entry per finding>"],
        "remediation": "<what was fixed before release>",
        "report_sha256": "<64 hex of the report>",
    },
    "legal_privacy_review": {
        "jurisdiction": "<the production jurisdiction>",
        "lawful_basis": "<the basis relied on>",
        "dpa_ref": "<data processing agreement reference>",
        "reviewer": "<counsel who signed it>",
    },
}

#: Who has to supply each gate, so nobody reads a gate as "just fill this in".
WHO_SUPPLIES = {
    "signed_production_evidence": "you + the operator (operator computes pack_sha256, you sign)",
    "operational_ownership": "you (name your accountable owner, then sign)",
    "incident_oncall_ownership": "you (name your on-call and escalation, then sign)",
    "certified_data_isolation": "a certification body you appoint -- no CSV closes this",
    "external_observer_audit": "an independent auditor you appoint -- no CSV closes this",
    "production_deployment_architecture": "your infrastructure owner -- no CSV closes this",
    "disaster_recovery_evidence": "a real DR test against production -- no CSV closes this",
    "security_review": "an independent security reviewer -- no CSV closes this",
    "legal_privacy_review": "your legal counsel -- no CSV closes this",
}


def run(producer: pathlib.Path, python: pathlib.Path, *args: str) -> str:
    """Run Helix-Prime's producer and return stdout, or raise with its stderr."""
    cmd = [str(python), str(producer), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"producer failed: {' '.join(cmd)}\n{proc.stdout}\n{proc.stderr}")
    return proc.stdout


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="pack folder to create")
    ap.add_argument("--helix", default=str(DEFAULT_HELIX), help="Helix-Prime checkout")
    ap.add_argument("--as-of", default=None, help="ISO date stamped into the manifest")
    ap.add_argument(
        "--template-source",
        default=None,
        help="existing handoff/helix-codex folder to copy the client CSVs from",
    )
    args = ap.parse_args()

    helix = pathlib.Path(args.helix).resolve()
    producer = helix / "scripts" / "produce_production_evidence.py"
    release_pkg = helix / "release" / "production_evidence.py"
    if not producer.is_file() or not release_pkg.is_file():
        raise SystemExit(
            f"FAIL CLOSED: Helix-Prime not found at {helix}\n"
            "This builder will not guess the gate contract. Pass --helix <path>."
        )

    python = pathlib.Path(sys.executable)
    out = pathlib.Path(args.out).resolve()
    as_of = args.as_of or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    if out.exists():
        shutil.rmtree(out)
    (out / "gate-evidence").mkdir(parents=True)

    # 1. Gate documents come from Helix-Prime's own producer -- never restated here.
    sys.path.insert(0, str(helix))
    from release import production_evidence as pe  # noqa: E402

    gates = sorted(pe.REQUIRED_EVIDENCE)
    manifest_gates = []
    for gate in gates:
        doc = out / "gate-evidence" / f"{gate}.evidence.json"
        run(producer, python, "template", "--gate", gate, "--out", str(doc))
        claims = json.loads(doc.read_text(encoding="utf-8"))
        claims["payload"] = SAMPLE_PAYLOAD[gate]
        doc.write_text(json.dumps(claims, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        ok, reason = pe.validate_claims(gate, claims)
        if ok:
            raise SystemExit(f"BUG: an unfilled sample template passed the gate contract: {reason}")
        reason = reason.strip()
        manifest_gates.append(
            {
                "gate": gate,
                "evidence_type": pe.REQUIRED_EVIDENCE[gate],
                "file": f"gate-evidence/{gate}.evidence.json",
                "sha256": sha256(doc),
                "closable_by_client_files": gate in CLIENT_CLOSABLE,
                "who_supplies": WHO_SUPPLIES[gate],
                "unfilled_sample_refused_because": reason,
                "expected_fields": sorted(claims),
            }
        )

    # 2. Carry the client CSVs over from CreateLee's handoff, if available.
    copied_csvs = []
    src = pathlib.Path(args.template_source).resolve() if args.template_source else None
    if src and src.is_dir():
        (out / "signoff-inputs").mkdir(exist_ok=True)
        for name in SIGNOFF_CSVS:
            f = src / "signoff-inputs" / name
            if f.is_file():
                shutil.copy2(f, out / "signoff-inputs" / name)
                copied_csvs.append(f"signoff-inputs/{name}")
        for name in OWNERSHIP_CSVS:
            f = src / name
            if f.is_file():
                shutil.copy2(f, out / name)
                copied_csvs.append(name)

    manifest = {
        "pack": "helix-codex-production-pack",
        "as_of": as_of,
        "contract_source": str(release_pkg),
        "contract_fields_required_by_the_gate": [
            "gate",
            "evidence_type",
            "scope",
            "issuer",
            "issued_at",
            "expires_at",
            "payload",
        ],
        "gates": manifest_gates,
        "client_csvs_included": copied_csvs,
        "honesty_boundary": (
            "Every value in this pack is simulated. Passing the form check means "
            "'the gate would read this', never 'this is true'. Three of nine gates "
            "can be closed by client data plus an off-system signature; the other "
            "six require a named third party and stay open until that document exists."
        ),
    }
    (out / "PACK_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    closable = sum(1 for g in manifest_gates if g["closable_by_client_files"])
    print(f"pack            : {out}")
    print(f"gate documents  : {len(manifest_gates)} (all emitted by Helix-Prime's producer)")
    print(f"client-closable : {closable}/{len(manifest_gates)}")
    print(f"CSVs carried    : {len(copied_csvs)}")
    print("unfilled samples are refused by the gate contract -- by design")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())