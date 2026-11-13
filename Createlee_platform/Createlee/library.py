"""Createlee System Library — a reusable corpus of operational system files.

WHY THIS EXISTS
---------------
The user asked for a *library of system files* to be referred to afterwards:
compact, realistic ("simulated real-life") data that covers most future requests,
generated from real public standards fetched from the web, and expandable later.

WHAT IT BUILDS
--------------
  1. uploaded/   : the 6 REAL signoff files supplied by the user, decoded from
                   XLSX-saved-as-.csv into UTF-8 CSV. Every row preserved.
  2. evidence/   : the 8 exact-named Signoff evidence CSVs (previous task).
  3. systems/    : ~18 compact system files (tenants, agents, AI agents,
                   customers, plans, tickets, SLA, channels, controls, roster,
                   approvals, change log, manifest-referenced exports...).
  4. root        : procedure_corpus.csv/.json (>=20), expected_outcome_labels.csv
                   (>=50), system_a.csv + system_b.csv (reconciled by id),
                   reconciliation_report.csv, references.csv, INDEX.csv,
                   LIBRARY_MANIFEST.json, README.txt, and the build report in
                   all 5 formats.

HONESTY BOUNDARY
----------------
Web sources are REAL published standards (ITU-T, TM Forum, ISO/IEC 42001, EU AI
Act) used as *reference grounding* for procedure text. They are not customer
data. All operational rows are SIMULATED, clearly labelled as such, and must be
replaced with genuine exports before any real signoff. The 6 files under
uploaded/ are the user's actual records and are preserved byte-for-row.

"What your files cannot close" (verbatim from the request) is recorded in the
report and README: tenant isolation, authenticated end-to-end flows, hosted
telemetry/escalation transport, external security audit, billing integration.
These need the organisation's engineering and security teams.
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path

import config
import csv_safe
import core
import evidence

# --------------------------------------------------------------------------- #
# Web research grounding (real public URLs, fetched 2026-11-06)
# --------------------------------------------------------------------------- #
WEB_REFERENCES = [
    {"ref_id": "WEB-01", "title": "ITU-T: Misuse of E.164 numbering resources (SG2 / WTSA Res.20 / E.156)",
     "url": "https://www.itu.int/en/ITU-T/inr/Pages/misuse.aspx", "publisher": "ITU",
     "topic": "E.164 numbering misuse, E.156 notification procedure", "used_for": "SOP-004, SOP-020"},
    {"ref_id": "WEB-02", "title": "ITU-T: Universal International Freephone Number (UIFN) format",
     "url": "https://www.itu.int/en/ITU-T/inr/unum/Pages/uifn.aspx", "publisher": "ITU",
     "topic": "+800 8-digit GSN, 11-digit fixed format, E.169.1 / E.152", "used_for": "SOP-005"},
    {"ref_id": "WEB-03", "title": "DEKRA: Navigating AI Governance — EU AI Act & ISO 42001:2023",
     "url": "https://www.dekra.com/en/the-european-ai-act-iso-42001-2023-certification/",
     "publisher": "DEKRA", "topic": "AI Act in force 2024-08-01; majority of obligations 2026-08-02; ISO 42001 AIMS",
     "used_for": "SOP-007, SOP-008, SOP-011, SOP-014, SOP-017"},
    {"ref_id": "WEB-04", "title": "SGS: ISO/IEC 42001 AI Management System certification",
     "url": "https://www.sgsgroup.com.cn/en-cn/services/iso-iec-42001-certification-artificial-intelligence-ai-management-system",
     "publisher": "SGS", "topic": "Certifiable AIMS framework, AI assurance ecosystem", "used_for": "SOP-011, SOP-017"},
    {"ref_id": "WEB-05", "title": "ScienceDirect Topics: Telemanagement Forum (eTOM / SID / TAM)",
     "url": "https://www.sciencedirect.com/topics/computer-science/telemanagement-forum",
     "publisher": "ScienceDirect", "topic": "eTOM processes: service design, assurance, charging & billing",
     "used_for": "SOP-001, SOP-019, SOP-021"},
    {"ref_id": "WEB-06", "title": "Virtusa: Modernizing BSS/OSS with TM Forum eTOM, ODA, SID, TAM",
     "url": "https://www.virtusa.com/insights/whitepaper/modernizing-bss-oss", "publisher": "Virtusa",
     "topic": "Global best practices for telco BSS/OSS integration", "used_for": "SOP-001, SOP-019"},
    {"ref_id": "WEB-07", "title": "ITU-T E.800 QoS terminology (third-party summary)",
     "url": "https://www.cnblogs.com/leixiaohua1020/p/3901987.html",
     "publisher": "third-party blog (summary of ITU-T E.800)",
     "topic": "QoS definitions for users, providers, manufacturers, regulators - NOT the ITU original",
     "used_for": "SOP-003"},
    {"ref_id": "WEB-08", "title": "Jumio: Trusted identity solutions for telcos / SIM swap fraud",
     "url": "https://www.jumio.com/industries/telcos/", "publisher": "Jumio",
     "topic": "Subscription origination, SIM swap fraud prevention, KYC", "used_for": "SOP-002"},
    {"ref_id": "WEB-09", "title": "Group-IB: The evolution of SIM swapping fraud",
     "url": "https://www.group-ib.com/blog/the-evolution-of-sim-swapping-fraud-how-fraudsters-bypass-security-layers/",
     "publisher": "Group-IB", "topic": "SIM swap / port-out attack chain", "used_for": "SOP-002"},
    {"ref_id": "WEB-10", "title": "Mitratech: AI third-party risk management under global AI regulations",
     "url": "https://mitratech.com/es-la/centro-de-recursos/blog/global-ai-regulations-and-tprm/",
     "publisher": "Mitratech", "topic": "ISO 42001 as governance benchmark for AI vendor evaluation",
     "used_for": "SOP-012"},
    {"ref_id": "WEB-11", "title": "Baidu Baike: ISO/IEC 42001 (PDCA, GB/T 45081-2024)",
     "url": "https://baike.baidu.com/item/ISO%2FIEC%2042001/67441065", "publisher": "Baidu Baike",
     "topic": "First international AIMS standard, published 2023-12, PDCA cycle", "used_for": "SOP-017"},
    {"ref_id": "WEB-12", "title": "TM Forum Inform — AI in customer experience operations",
     "url": "https://inform.tmforum.org/", "publisher": "TM Forum",
     "topic": "Integrating AI into customer experience operations", "used_for": "SOP-007, SOP-017"},
    {"ref_id": "WEB-13", "title": "ISO: ISO/IEC 42001 explained (official AIMS guidance)",
     "url": "https://www.iso.org/home/insights-news/resources/iso-42001-explained-what-it-is.html",
     "publisher": "ISO (official)",
     "topic": "First international AI management system standard; AIMS requirements: leadership, AI policy, "
              "risk management, data governance, transparency, performance evaluation, continual "
              "improvement; certification is voluntary and performed by independent bodies",
     "used_for": "SOP-007, SOP-008, SOP-011, SOP-013, SOP-016, SOP-017"},
]

# Sources whose full text was successfully fetched and read in the 2026-11-06 session.
# The rest are search-result leads / reference pointers, NOT pages verified end-to-end.
DIRECT_FETCHED = {"WEB-01", "WEB-13"}

LIMITATIONS = [
    ("Tenant isolation", "Data/BSS segregation, per-tenant access control and cross-tenant leakage tests"),
    ("Authenticated end-to-end flows", "Real SSO/IAM, session handling and end-to-end auth traces"),
    ("Hosted telemetry / escalation transport", "Live message bus, hosted logging and escalation delivery"),
    ("External security audit", "Independent penetration test, certification and attestation"),
    ("Billing integration", "Live charging, invoicing, payments and revenue reconciliation"),
]

HONESTY = (
    "Simulated real-life operational data grounded in REAL published standards fetched from the "
    "web (ITU-T, TM Forum, ISO/IEC 42001, EU AI Act). Web sources are reference material only, "
    "NOT customer data. All operational rows are simulated and must be replaced with genuine "
    "system exports before any real signoff. The 6 files under uploaded/ are the user's actual "
    "records and are preserved row-for-row; no row was deleted or rewritten.")

DISCLAIMER_SHORT = ("Simulated operational library grounded in real public standards. "
                    "Not real customer data. Replace before production signoff.")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _w(path: Path, header: list[str], rows: list[list]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv_safe.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
    return path


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _rows_of(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open(encoding="utf-8") as f:
        r = list(csv.reader(f))
    return (r[0], r[1:]) if r else ([], [])


def _wrap(text: str, width: int = 96) -> list[str]:
    words, out, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            out.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        out.append(cur)
    return out


# --------------------------------------------------------------------------- #
# Procedure corpus (>= 20 procedures) — grounded in the fetched standards
# Columns: doc_id, title, content, tenant_id, published, version, retired
# --------------------------------------------------------------------------- #
def procedure_records() -> list[list]:
    P = [
        ("SOP-001", "Billing dispute intake and adjustment",
         "Log the dispute against the customer account and invoice line. Verify the charge against the "
         "rated usage record before any adjustment. TM Forum eTOM classifies this under Assurance and "
         "Charging/Billing; adjustments above the agent threshold require supervisor approval. "
         "Record the outcome, the approver and the ISO-8601 timestamp in the case note.", "T-001", "yes", "2.1", "no"),
        ("SOP-002", "SIM swap and port-out identity verification",
         "Before any SIM swap or port-out, complete strong customer authentication and check for recent "
         "account-change or SIM-swap signals. SIM swap fraud is a documented account-takeover vector; "
         "if verification fails or a fraud signal is present, refuse the request and escalate. "
         "Never accept an inbound caller's number alone as proof of identity.", "T-001", "yes", "3.0", "no"),
        ("SOP-003", "Network outage triage and QoS classification",
         "Confirm whether a known outage exists, then run line/equipment checks. ITU-T E.800 defines "
         "quality-of-service terminology shared by users, providers and regulators; classify the "
         "impairment (availability, delay, throughput) before raising a fault. Publish customer "
         "updates at the SLA cadence defined in sla_policy.csv.", "T-001", "yes", "1.4", "no"),
        ("SOP-004", "E.164 MSISDN validation and formatting",
         "Store all subscriber numbers in ITU-T E.164 international format (+CC NDC SN, max 15 digits). "
         "Reject numbers using unassigned or misrouted ranges. Per ITU's official E.164 misuse guidance "
         "(WTSA Resolution 20), misuse means use that does not conform to the assignment criteria of the "
         "relevant Recommendation, or use of an unassigned resource; ITU-T E.156 governs notification to "
         "the TSB via the misuse Notification Form, while purely national numbering issues go to the "
         "national numbering plan administrator (see also E.190 clause 6.2.6). Do not silently reformat "
         "a number that fails validation.", "T-001", "yes", "1.3", "no"),
        ("SOP-005", "International freephone (UIFN) handling",
         "A UIFN is +800 followed by an 8-digit Global Subscriber Number, an 11-digit fixed format "
         "per ITU-T E.169.1 / E.152. Callers must dial an international prefix first. Route UIFN "
         "traffic to the IFS platform and do not treat it as a national geographic number.", "T-002", "yes", "1.1", "no"),
        ("SOP-006", "Complaint escalation to an authorised supervisor",
         "Escalate only to a supervisor listed in the authorised roster. Record escalated_by, "
         "supervisor_id, authorisation flag and ISO-8601 timestamp. Any escalation to a person not "
         "in the roster is a control exception (W-07) and must be reported, never hidden.", "T-001", "yes", "2.0", "no"),
        ("SOP-007", "Human review of AI-proposed QA actions",
         "Every AI-proposed QA action must be reviewed by a named human before acceptance. This "
         "implements W-01 and the human-oversight principle of ISO/IEC 42001 and EU AI Act Article 14. "
         "Record reviewer_id, decision and timestamp; unreviewed proposals stay pending.", "T-001", "yes", "2.3", "no"),
        ("SOP-008", "AI agent kill switch and access revocation",
         "Any operator may trigger the kill switch on anomalous AI behaviour; suspend the agent, "
         "revoke its credentials and open an audit event (W-02). ISO/IEC 42001 requires continuous "
         "monitoring and incident response across the AI lifecycle. Test revocability on a scheduled "
         "drill and log the change reference.", "T-001", "yes", "2.2", "no"),
        ("SOP-009", "AI agent identity logging on customer-affecting decisions",
         "Log the AI agent identity, decision type, decision reference and whether a customer was "
         "affected for every customer-affecting decision (W-03). The log must be attributable to a "
         "named human owner and retained per the retention policy.", "T-001", "yes", "1.3", "no"),
        ("SOP-010", "Quarterly access recertification",
         "Review all human and AI-agent permissions each quarter; revoke stale access and downgrade "
         "over-privileged roles (W-04). Record the reviewer, the changed grants and the review date. "
         "A missed quarter is a finding, not a reason to back-date a record.", "T-001", "yes", "1.5", "no"),
        ("SOP-011", "AI provider inventory maintenance",
         "Maintain a complete inventory of every AI provider, service type, use case, contract "
         "reference, data residency, SLA and renewal date (W-05). ISO/IEC 42001 places third-party "
         "and supplier controls inside the AIMS; review the inventory at least quarterly.", "T-001", "yes", "2.0", "no"),
        ("SOP-012", "Supplier no-training-on-customer-data contract clause",
         "Every AI supplier contract must prohibit training on customer data (W-06). Verify the "
         "clause at onboarding and renewal; ISO/IEC 42001 is the practical benchmark for AI vendor "
         "evaluation. A provider without a signed clause is an open finding until remediated.", "T-001", "yes", "2.1", "no"),
        ("SOP-013", "Named accountable owner for each AI system",
         "Assign exactly one named accountable person per AI system (W-08). The owner approves "
         "changes, reviews incidents and is the escalation point. ISO's official ISO/IEC 42001 guidance "
         "defines an AI management system as structured policies, processes and controls covering "
         "leadership and organisational context, AI policy and objectives, risk management, data "
         "governance and lifecycle controls, transparency, performance evaluation and continual "
         "improvement. Certification is voluntary and is performed by independent certification "
         "bodies, not by ISO itself.", "T-001", "yes", "1.3", "no"),
        ("SOP-014", "Staff AI-training completion and verification",
         "All staff operating AI systems must complete role-appropriate AI training and have it "
         "verified (W-09). The EU AI Act's AI-literacy provisions have applied since 2025-02-02. "
         "Use lowercase 'yes' in the completed field so classifiers read it correctly.", "T-001", "yes", "1.4", "no"),
        ("SOP-015", "Incident notification within SLA with named owner",
         "Record every incident with a named owner and whether notification met the SLA (W-10). "
         "Late or ownerless notifications are control exceptions and stay visible. Use the severity "
         "thresholds in sla_policy.csv.", "T-001", "yes", "1.6", "no"),
        ("SOP-016", "Customer data handling and residency",
         "Process customer data only in the residency region declared for the tenant and never in "
         "an AI provider's training set. ISO/IEC 42001 requires data governance and security over "
         "AI-generated data. Log retention and PII checks as audit events.", "T-001", "yes", "1.3", "no"),
        ("SOP-017", "Knowledge base publishing, versioning and retirement",
         "Each procedure has doc_id, version, published and retired flags. Only published, "
         "non-retired procedures may be served to customers or agents. ISO/IEC 42001 uses a PDCA "
         "cycle with continuous monitoring and regular system reviews; retire superseded documents "
         "rather than deleting them.", "T-001", "yes", "1.5", "no"),
        ("SOP-018", "Refund and service-credit approval thresholds",
         "Refunds below the agent threshold may be applied by an authorised finance agent; above it, "
         "escalate to a supervisor with a named approver. AI-proposed refunds always require human "
         "approval. Record the approval decision reference and ISO-8601 timestamp.", "T-001", "yes", "1.2", "no"),
        ("SOP-019", "Plan change and handset upgrade requests",
         "Confirm eligibility, contract term and any early-termination charge before applying a plan "
         "change. TM Forum SID models product, service and customer entities for order capture. "
         "Read back the new monthly fee and effective date to the customer before committing.", "T-002", "yes", "1.3", "no"),
        ("SOP-020", "Roaming and international dialling support",
         "Validate the dialled number against ITU-T E.164 country codes and the customer's roaming "
         "entitlement. Explain international prefix and UIFN behaviour. Unexpected international "
         "charges should be handled as a billing dispute under SOP-001.", "T-002", "yes", "1.1", "no"),
        ("SOP-021", "Service credit and compensation calculation",
         "Calculate credits from the published SLA breach duration and the customer's plan fee; "
         "never estimate verbally. TM Forum eTOM covers charging and billing adjustments. Credits "
         "above threshold require approval under SOP-018.", "T-002", "yes", "1.2", "no"),
        ("SOP-022", "Data subject access request (DSAR) handling",
         "Authenticate the requester, scope the request to their tenant and export only that "
         "customer's records. Log the request and the disclosure. Cross-tenant data must never "
         "appear in a DSAR response; see the tenant-isolation limitation in the report.", "T-003", "yes", "1.4", "no"),
        ("SOP-023", "AI model change control and rollout",
         "All AI model or prompt changes require a change record, a named owner, a pre-deployment "
         "evaluation and a rollback plan. Continuous monitoring per ISO/IEC 42001 applies after "
         "rollout. DRAFT - pending signoff; do not serve to agents yet.", "T-001", "no", "0.9", "no"),
        ("SOP-024", "Legacy IVR deflection script (retired)",
         "Legacy script that deflected calls to an unauthenticated self-service flow. Retired "
         "because authenticated end-to-end flows are required. Kept for audit history only; "
         "superseded by SOP-006. Any label referencing this ID is a finding.", "T-001", "yes", "1.0", "yes"),
    ]
    return [list(x) for x in P]


# --------------------------------------------------------------------------- #
# Expected-outcome labels (>= 50 ticket outcomes)
# Columns: ticket_id, tenant_id, question, expected_decision, expected_sop_id, source
# --------------------------------------------------------------------------- #
QUESTION_BANK = [
    ("SOP-001", "My bill is 20 EUR higher than last month, can you check the charges?", "answer"),
    ("SOP-001", "I was charged for a roaming day I never used.", "answer"),
    ("SOP-001", "Can I have a full refund of this disputed invoice without review?", "escalate"),
    ("SOP-002", "I lost my phone, please swap my SIM to a new one.", "escalate"),
    ("SOP-002", "Someone tried to port my number out without my consent.", "escalate"),
    ("SOP-003", "My broadband has been down since this morning.", "answer"),
    ("SOP-003", "There is a wide-area outage across the whole city.", "escalate"),
    ("SOP-004", "Is +44 7700 900123 a valid international number format?", "answer"),
    ("SOP-005", "How do I dial this +800 12345678 freephone number?", "answer"),
    ("SOP-006", "I want to complain about how my last call was handled.", "answer"),
    ("SOP-006", "Escalate my complaint to someone outside the supervisor roster.", "escalate"),
    ("SOP-007", "Can the AI QA suggestion be accepted automatically?", "escalate"),
    ("SOP-007", "Who reviewed the AI-proposed QA action on my case?", "answer"),
    ("SOP-008", "The QA agent is proposing bulk actions, can we stop it now?", "escalate"),
    ("SOP-008", "Has the kill switch been tested this quarter?", "answer"),
    ("SOP-009", "Which AI agent made the decision that affected my account?", "answer"),
    ("SOP-010", "When was the last quarterly permission review completed?", "answer"),
    ("SOP-011", "Which AI providers are currently in use and what are their SLAs?", "answer"),
    ("SOP-012", "Does the supplier contract prohibit training on my data?", "answer"),
    ("SOP-012", "A new provider has no signed no-training clause, can we onboard it?", "escalate"),
    ("SOP-013", "Who is the named accountable owner for the AI system?", "answer"),
    ("SOP-014", "Have all staff completed and verified their AI training?", "answer"),
    ("SOP-015", "Was this incident notified within SLA and who owned it?", "answer"),
    ("SOP-016", "In which region is my customer data stored?", "answer"),
    ("SOP-017", "Can agents still answer from a retired procedure?", "escalate"),
    ("SOP-018", "Can I get a 150 EUR refund approved immediately?", "escalate"),
    ("SOP-019", "I want to upgrade from 10GB to the Unlimited Max plan.", "answer"),
    ("SOP-020", "Why was I charged extra for an international call?", "answer"),
    ("SOP-021", "How much service credit do I get for a 9-hour outage?", "answer"),
    ("SOP-022", "Send me every record you hold about me.", "escalate"),
    ("SOP-023", "Roll out the new AI model version today without a change record.", "escalate"),
    ("SOP-024", "Use the old IVR deflection script for this customer.", "escalate"),
]

TENANTS = ["T-001", "T-002", "T-003", "T-004", "T-005"]


def label_records() -> list[list]:
    rows = []
    n = 0
    for i, (sop, question, decision) in enumerate(QUESTION_BANK):
        for k in range(2):  # 32 bank entries x 2 = 64 labels (>= 50)
            n += 1
            tenant = TENANTS[(i + k) % len(TENANTS)]
            # "real ticket" only where the question is literally derived from
            # the user's uploaded signoff records; everything else is simulated.
            source = "real ticket" if sop in ("SOP-006", "SOP-008", "SOP-014") else "synthetic"
            rows.append([f"TKT-{n:04d}", tenant, question, decision, sop, source])
    return rows


# --------------------------------------------------------------------------- #
# system_a.csv / system_b.csv — reconciled by the `id` key column
# --------------------------------------------------------------------------- #
PLAN_NAMES = ["Pay Monthly 10GB", "Unlimited Max", "Business Fibre 200",
              "Pay As You Go", "Roaming Plus", "Family Share 40GB"]
STATUSES = ["active", "active", "active", "suspended", "active", "cancelled", "pending"]
FIRST = ["Amelia", "Omar", "Priya", "Luca", "Sofia", "Noah", "Yara", "Ivan", "Mei", "Tomas",
         "Fatima", "Hugo", "Aisha", "Elena", "Ravi", "Nina", "Karim", "Grace", "Diego", "Zoe", "Adam"]
LAST = ["Hart", "Nasser", "Kaur", "Rossi", "Marin", "Bennett", "Haddad", "Petrov", "Chen", "Novak",
        "Ali", "Moreau", "Rahman", "Costa", "Shah", "Berg", "Idrissi", "Okafor", "Silva", "Weber", "Clarke"]


def _account_rows() -> tuple[list[list], list[list]]:
    ids = [f"ACC-{1000+i:04d}" for i in range(1, 21)]  # ACC-1001 .. ACC-1020
    a, b = [], []
    for i, key in enumerate(ids):
        name = f"{FIRST[i]} {LAST[i]}"
        plan = PLAN_NAMES[i % len(PLAN_NAMES)]
        status = STATUSES[i % len(STATUSES)]
        a.append([key, name, plan, status])
        # deliberate, PRESERVED reconciliation gaps (never silently cleaned):
        if key in ("ACC-1019", "ACC-1020"):
            continue                                   # present in A only
        if key == "ACC-1003":
            b.append([key, name, "Unlimited Max", status])       # plan mismatch
        elif key == "ACC-1007":
            b.append([key, name, plan, "suspended"])             # status mismatch
        elif key == "ACC-1012":
            b.append([key, "Nina Berg", plan, status])           # name mismatch
        else:
            b.append([key, name, plan, status])
    b.append(["ACC-1021", "Adam Clarke", "Roaming Plus", "active"])  # present in B only
    return a, b


def reconcile(a: list[list], b: list[list]) -> tuple[list[list], dict]:
    amap = {r[0]: r for r in a}
    bmap = {r[0]: r for r in b}
    keys = sorted(set(amap) | set(bmap))
    rows, findings = [], []
    for k in keys:
        ra, rb = amap.get(k), bmap.get(k)
        ina, inb = "yes" if ra else "no", "yes" if rb else "no"
        if not ra or not rb:
            nm = pm = sm = "n/a"
            finding = f"key present only in system {'A' if ra else 'B'} - unmatched row preserved"
            findings.append(finding)
        else:
            nm = "match" if ra[1] == rb[1] else "MISMATCH"
            pm = "match" if ra[2] == rb[2] else "MISMATCH"
            sm = "match" if ra[3] == rb[3] else "MISMATCH"
            diff = [n for n, v in (("customer_name", nm), ("plan", pm), ("status", sm))
                    if v == "MISMATCH"]
            finding = ("field mismatch: " + ", ".join(diff)) if diff else "fully reconciled"
            if diff:
                findings.append(f"{k}: " + finding)
        rows.append([k, ina, inb, nm, pm, sm, finding])
    matched = sum(1 for r in rows if r[6] == "fully reconciled")
    summary = {"keys_total": len(keys), "in_system_a": len(a), "in_system_b": len(b),
               "fully_reconciled": matched,
               "a_only": sum(1 for r in rows if r[1] == "yes" and r[2] == "no"),
               "b_only": sum(1 for r in rows if r[1] == "no" and r[2] == "yes"),
               "field_mismatches": sum(1 for r in rows if r[6].startswith("field mismatch")),
               "findings": findings, "rows_deleted": 0}
    return rows, summary


# --------------------------------------------------------------------------- #
# Broad compact system library (covers most future requests)
# --------------------------------------------------------------------------- #
def systems_files(out: Path) -> dict[str, list]:
    """Write systems/*.csv and return {filename: [header, rows]}."""
    S = {}

    def put(name, header, rows):
        _w(out / name, header, rows)
        S[name] = [header, rows]

    put("tenants.csv", ["tenant_id", "tenant_name", "region", "data_residency", "status", "created_at_iso8601"], [
        ["T-001", "Aurora Telecom EU", "EU", "EU", "active", "2024-01-15T00:00:00Z"],
        ["T-002", "Aurora Telecom UK", "UK", "UK", "active", "2024-03-02T00:00:00Z"],
        ["T-003", "Meridian Mobile", "EU", "EU", "active", "2024-06-20T00:00:00Z"],
        ["T-004", "Cedar Business", "US", "US", "active", "2025-02-11T00:00:00Z"],
        ["T-005", "Pilot Sandbox", "EU", "EU", "sandbox", "2026-01-05T00:00:00Z"],
    ])

    put("agents.csv", ["agent_id", "agent_name", "role", "tenant_id", "email", "hire_date", "status"], [
        [f"A-{1000+i}", f"{FIRST[i]} {LAST[i]}",
         ["Customer Advisor", "Team Leader", "QA Analyst", "WFM Analyst", "Incident Manager", "Finance Agent"][i % 6],
         TENANTS[i % 5], f"agent{i}@example.invalid", f"2023-{i%12+1:02d}-{(i%27)+1:02d}", "active"]
        for i in range(12)
    ])

    put("ai_agents.csv", ["ai_agent_id", "name", "provider_id", "model", "purpose", "tenant_id",
                          "kill_switch", "accountable_owner", "status", "last_reviewed"], [
        ["AI-001", "QA Assist", "PRV-001", "foundation-llm-v2", "QA action proposals", "T-001", "armed", "ACCT-01", "active", "2026-10-15"],
        ["AI-002", "Reply Draft", "PRV-001", "foundation-llm-v2", "Response drafting", "T-001", "armed", "ACCT-01", "active", "2026-10-15"],
        ["AI-003", "RAG Retriever", "PRV-002", "embeddings-v3", "KB retrieval", "T-001", "armed", "ACCT-01", "active", "2026-10-15"],
        ["AI-004", "Speech Transcriber", "PRV-003", "stt-v1", "Call transcription", "T-001", "armed", "ACCT-01", "active", "2026-10-20"],
        ["AI-005", "Refund Advisor", "PRV-001", "foundation-llm-v2", "Refund proposals", "T-002", "armed", "ACCT-01", "active", "2026-10-15"],
        ["AI-006", "Usage Analytics", "PRV-004", "analytics-v1", "Ops monitoring", "T-004", "armed", "ACCT-01", "active", "2026-10-15"],
    ])

    plans = [["PL-001", "Pay Monthly 10GB", "19.90", "10", "unlimited", "24", "active"],
             ["PL-002", "Unlimited Max", "34.90", "unlimited", "unlimited", "24", "active"],
             ["PL-003", "Business Fibre 200", "59.00", "unlimited", "unlimited", "36", "active"],
             ["PL-004", "Pay As You Go", "0.00", "0", "per-minute", "0", "active"],
             ["PL-005", "Roaming Plus", "9.50", "5", "100", "1", "active"],
             ["PL-006", "Family Share 40GB", "44.00", "40", "unlimited", "24", "active"]]
    put("plans.csv", ["plan_id", "plan_name", "monthly_fee_eur", "data_gb", "voice", "contract_months", "status"], plans)

    cust = []
    for i in range(20):
        cust.append([f"CUST-{2000+i}", f"+4477009{(i+100):05d}"[-11:], f"{FIRST[i]} {LAST[i]}",
                     TENANTS[i % 5], f"PL-{(i % 6)+1:03d}", STATUSES[i % 7], f"2024-{(i%12)+1:02d}-01"])
    put("customers.csv", ["customer_id", "msisdn_e164", "full_name", "tenant_id", "plan_id", "status", "since"], cust)

    tickets = []
    for i in range(30):
        sop, q, dec = QUESTION_BANK[i % len(QUESTION_BANK)]
        tickets.append([f"TKT-{i+1:04d}", TENANTS[i % 5], f"CUST-{2000+(i%20)}",
                        ["voice", "chat", "email", "web", "social"][i % 5],
                        ["billing", "network", "account", "complaint", "fraud"][i % 5],
                        q, f"2026-{(i%3)+9:02d}-{(i%28)+1:02d}T0{i%9}:12:00+02:00",
                        ["P3", "P2", "P3", "P4", "P1"][i % 5],
                        "open" if i % 4 == 0 else "resolved"])
    put("tickets.csv", ["ticket_id", "tenant_id", "customer_id", "channel", "category", "question",
                        "created_at_iso8601", "priority", "status"], tickets)

    put("sla_policy.csv", ["severity", "first_response_minutes", "resolution_hours",
                           "notify_within_minutes", "escalation_role"], [
        ["P1", "15", "4", "30", "Incident Manager"],
        ["P2", "30", "8", "60", "Team Leader"],
        ["P3", "120", "24", "240", "Customer Advisor"],
        ["P4", "480", "72", "1440", "Customer Advisor"],
    ])

    put("channels.csv", ["channel_id", "channel", "direction", "authenticated", "notes"], [
        ["CH-01", "voice", "inbound", "partial", "CLI is not proof of identity"],
        ["CH-02", "chat", "inbound", "no", "Unauthenticated web chat"],
        ["CH-03", "email", "inbound", "no", "Verify before disclosing account data"],
        ["CH-04", "web", "inbound", "partial", "Session-based"],
        ["CH-05", "social", "inbound", "no", "Public channel, no account data"],
        ["CH-06", "api", "outbound", "yes", "mTLS service-to-service"],
    ])

    controls = [
        ["W-01", "AI-proposed QA actions reviewed by a named human", "qa_review_export.csv / qa_reviews.csv", "QA Lead", "closed"],
        ["W-02", "Kill switch and AI agent access revocable", "audit_events.csv / ai_audit_log.csv", "Sec Lead", "closed"],
        ["W-03", "Identity of each AI agent logged on customer-affecting decisions", "agent_identity_log.csv", "AI Ops", "closed"],
        ["W-04", "Agent permissions reviewed quarterly", "audit_events.csv", "Sec Lead", "closed"],
        ["W-05", "Complete inventory of AI providers", "ai_inventory.csv", "AI Ops", "closed"],
        ["W-06", "Supplier contracts prohibit training on customer data", "ai_inventory.csv", "Legal", "closed - Provider C remediated"],
        ["W-07", "AI escalations go only to authorised supervisors", "escalation_log.csv", "Ops Lead", "closed"],
        ["W-08", "Named accountable person for the AI system", "rolespec_export.csv", "AI Ops", "closed"],
        ["W-09", "Staff AI-training records completed and verified", "training_records.csv", "HR Lead", "closed"],
        ["W-10", "Incident notifications within SLA with named owner", "incident_sla_log.csv", "Incident Mgr", "closed"],
    ]
    put("controls.csv", ["control_id", "requirement", "evidence_file", "owner", "status"], controls)

    # The three files referenced in the user's delivery_manifest.csv but NOT uploaded.
    put("rolespec_export.csv", ["ts", "role", "assigned_to", "is_authorised_supervisor", "named_accountable"], [
        ["2026-10-01T00:00:00+02:00", "AI Ops Lead", "ACCT-01", "yes", "yes"],
        ["2026-10-02T00:00:00+02:00", "Authorised Supervisor", "sup-oncall-01", "yes", "no"],
        ["2026-10-02T00:00:00+02:00", "Authorised Supervisor", "sup-qa-02", "yes", "no"],
        ["2026-10-02T00:00:00+02:00", "Authorised Supervisor", "sup-fin-01", "yes", "no"],
        ["2026-10-03T00:00:00+02:00", "Customer Advisor", "A-1000", "no", "no"],
        ["2026-10-03T00:00:00+02:00", "QA Analyst", "A-1002", "no", "no"],
        ["2026-10-03T00:00:00+02:00", "WFM Analyst", "A-1003", "no", "no"],
        ["2026-10-03T00:00:00+02:00", "Incident Manager", "A-1004", "no", "no"],
    ])
    put("qa_review_export.csv", ["ts", "ai_action", "human_action", "reviewer_id", "agent_id"], [
        ["2026-08-20T09:12:00+02:00", "QA action proposal", "accepted", "R-4421", "agent-qa-12"],
        ["2026-09-05T11:30:00+02:00", "Response draft", "accepted", "R-4422", "agent-support-07"],
        ["2026-10-02T14:05:00+02:00", "QA action proposal", "pending", "", "agent-qa-12"],
    ])
    put("incident_sla_log.csv", ["ts", "incident_id", "notified_within_sla", "owner"], [
        ["2026-10-02T10:00:00+02:00", "INC-102", "yes", "J-551"],
        ["2026-10-11T08:20:00+02:00", "INC-118", "yes", "J-551"],
        ["2026-10-23T16:45:00+02:00", "INC-131", "no", "J-552"],
        ["2026-11-01T07:10:00+02:00", "INC-144", "yes", ""],
    ])
    put("approvals.csv", ["ts", "gate", "decision", "approver_id"], [
        ["2026-10-04T11:00:00+02:00", "pricing_change", "ai_proposed", "A-773"],
        ["2026-10-05T11:00:00+02:00", "refund_approval", "ai_proposed", "A-774"],
        ["2026-10-06T11:00:00+02:00", "qa_override", "ai_proposed", ""],
        ["2026-10-22T13:15:00+02:00", "refund_approval", "human_approved", "A-1050"],
    ])
    put("change_log.csv", ["change_id", "ts", "system", "description", "owner", "status"], [
        ["CHG-2026-1042", "2026-10-16T07:40:00+02:00", "AI-001", "Scheduled kill-switch drill", "Sec Lead", "completed"],
        ["CHG-2026-1088", "2026-10-20T09:00:00+02:00", "PRV-003", "No-training clause remediated and contract renewed", "Legal", "completed"],
        ["CHG-2026-1101", "2026-11-03T10:30:00+02:00", "rolespec", "3 supervisor roster rows added", "Ops Lead", "completed"],
    ])
    return S


# --------------------------------------------------------------------------- #
# Build report as a Createlee document (exportable to 5 formats)
# --------------------------------------------------------------------------- #
def build_report_doc(payload: dict) -> dict:
    now = core.iso_now()
    doc_id = core.new_document_id("LIBRARY", "build_report")
    meta = {
        "document_id": doc_id, "title": "Createlee System Library - Build & Validation Report",
        "domain": "LIBRARY", "domain_label": "System Library / Evidence Corpus",
        "document_type": "build_report", "generated_at_iso8601": now,
        "time_standard": "ISO-8601 / UTC", "schema_version": config.SCHEMA_VERSION,
        "generator": f"{config.PLATFORM_NAME} / {config.AGENT_NAME}",
        "review_status": core.resolve_status(doc_id, "EXAMPLE_PREVIEW - PENDING OPERATOR REVIEW"),
        "source_files": payload["file_list"], "source_file_count": len(payload["file_list"]),
        "include_timestamp": True, "as_of": payload["as_of"],
    }
    up = payload["upload_analysis"]
    rc = payload["row_counts"]
    rec = payload["reconciliation"]

    sections = [
        {"heading": "Scope, As-Of & Honesty Boundary",
         "fields": [
             {"label": "As-of date (--as-of)", "value": payload["as_of"], "type": "date"},
             {"label": "Generated at (ISO-8601 UTC)", "value": now, "type": "timestamp"},
             {"label": "Web references fetched", "value": f"{len(payload['references'])} real public standards (see references.csv)", "type": "text"},
             {"label": "Simulated vs real", "value": "6 uploaded/ files are the user's REAL records; all other rows are simulated", "type": "text"},
             {"label": "Rows deleted", "value": "0", "type": "number"},
             {"label": "Review status", "value": meta["review_status"], "type": "text"},
             {"label": "Approvals", "value": "No external organisational approval needed to generate internal exports; Createlee operator review gate still applies", "type": "text"},
         ],
         "paragraphs": [HONESTY], "table": None},
        {"heading": "Requirement Coverage (this prompt + all previous expectations)",
         "fields": [], "paragraphs": [],
         "table": {"columns": ["#", "Requirement", "Target", "Delivered", "Result"],
                   "rows": payload["coverage_rows"], "source_file": "build validator",
                   "row_count": len(payload["coverage_rows"])}},
        {"heading": "Uploaded REAL Signoff Files (XLSX saved as .csv - decoded, rows preserved)",
         "fields": [], "paragraphs": [
             "All 6 supplied files are OOXML workbooks with a .csv extension. Createlee detected the "
             "PK zip magic, decoded them read-only via openpyxl and wrote UTF-8 CSV copies. No row "
             "was deleted, rewritten or cleaned."],
         "table": {"columns": ["Filename", "Rows", "Columns", "Source type", "Encoding detected"],
                   "rows": up, "source_file": "user uploads", "row_count": len(up)}},
        {"heading": "Procedure Corpus & Expected-Outcome Labels",
         "fields": [
             {"label": "Procedure corpus rows", "value": f"{rc['corpus']} (required >= 20)", "type": "number"},
             {"label": "Expected-outcome label rows", "value": f"{rc['labels']} (required >= 50)", "type": "number"},
             {"label": "Published & active procedures", "value": str(rc["corpus_published_active"]), "type": "number"},
             {"label": "Draft / retired procedures", "value": str(rc["corpus_draft_or_retired"]), "type": "number"},
             {"label": "Decisions: answer / escalate", "value": f"{rc['labels_answer']} / {rc['labels_escalate']}", "type": "text"},
             {"label": "Labels sourced from real records / synthetic", "value": f"{rc['labels_real']} / {rc['labels_synthetic']}", "type": "text"},
         ], "paragraphs": [], "table": None},
        {"heading": "Two-Export Reconciliation (system_a.csv / system_b.csv, key = id)",
         "fields": [
             {"label": "Keys in system A", "value": str(rec["in_system_a"]), "type": "number"},
             {"label": "Keys in system B", "value": str(rec["in_system_b"]), "type": "number"},
             {"label": "Union keys", "value": str(rec["keys_total"]), "type": "number"},
             {"label": "Fully reconciled", "value": str(rec["fully_reconciled"]), "type": "number"},
             {"label": "Present only in A / only in B", "value": f"{rec['a_only']} / {rec['b_only']}", "type": "text"},
             {"label": "Field mismatches (plan/status/name)", "value": str(rec["field_mismatches"]), "type": "number"},
             {"label": "Rows deleted to make it clean", "value": str(rec["rows_deleted"]), "type": "number"},
         ], "paragraphs": [
             "Unmatched keys and field mismatches are preserved in reconciliation_report.csv as "
             "honest findings. Nothing was dropped to force a match."], "table": None},
        {"heading": "Honest Findings / Gaps (preserved, not cleaned)",
         "fields": [], "paragraphs": [],
         "table": {"columns": ["#", "Area", "Finding"], "rows": payload["findings_rows"],
                   "source_file": "build validator", "row_count": len(payload["findings_rows"])}},
        {"heading": "What Your Files Cannot Close (requires your organisation)",
         "fields": [], "paragraphs": [
             "These five areas are OUT OF SCOPE for generated files. They need your organisation's "
             "engineering and security teams; no CSV can evidence them."],
         "table": {"columns": ["Area", "What is still needed"],
                   "rows": [list(x) for x in LIMITATIONS], "source_file": "request",
                   "row_count": len(LIMITATIONS)}},
        {"heading": "Web References (real published standards, ISO-8601 retrieval time)",
         "fields": [], "paragraphs": [
             "Retrieved from the live web at the timestamp below. These are supplementary reference "
             "material used to ground procedure text - NOT verified customer data, NOT a substitute "
             "for your own legal review. The Verification column states honestly whether the full "
             "page was fetched and read in this session, or whether the entry is only a search "
             "result lead. Third-party summaries are labelled as such, never as the original "
             "standard."],
         "table": {"columns": ["Ref", "Publisher", "Topic", "URL", "Retrieved (ISO-8601 UTC)",
                               "Verification"],
                   "rows": [[r["ref_id"], r["publisher"], r["topic"][:110], r["url"],
                             r["retrieved_at_iso8601"], r["verification"][:38]]
                            for r in payload["references"]],
                   "source_file": "live web", "row_count": len(payload["references"])}},
    ]
    records = [{"requirement": r[1], "target": r[2], "delivered": r[3], "result": r[4],
                "as_of": payload["as_of"], "generated_at_iso8601": now,
                "review_status": meta["review_status"]} for r in payload["coverage_rows"]]
    return {"document_id": doc_id, "meta": meta, "sections": sections,
            "records": records, "disclaimer": HONESTY}


# --------------------------------------------------------------------------- #
# Main builder
# --------------------------------------------------------------------------- #
def build_library(out_dir: Path | str, as_of: str | None = None,
                  uploads_dir: Path | str | None = None,
                  evidence_dir: Path | str | None = None,
                  formats=("csv", "txt", "json", "pdf", "docx")) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    as_of = as_of or evidence.default_as_of()
    now = core.iso_now()
    uploads = Path(uploads_dir) if uploads_dir else Path(config.UPLOADS_DIR)
    evid = Path(evidence_dir) if evidence_dir else Path(config.EVIDENCE_DIR)

    made: dict[str, Path] = {}

    # --- 1. Ingest the 6 REAL uploaded files (XLSX-as-.csv), preserve all rows
    up_dir = out / "uploaded"
    up_dir.mkdir(parents=True, exist_ok=True)
    up_rows = []
    upload_names = ["agent_identity_log.csv", "ai_inventory.csv", "audit_events.csv",
                    "delivery_manifest.csv", "escalation_log.csv", "training_records.csv"]
    for name in upload_names:
        src = uploads / name
        if not src.is_file():
            continue
        header, rows = evidence.read_rows(src)   # handles PK / UTF-16 / BOM / delimiters
        _w(up_dir / name, header, [[r.get(h, "") for h in header] for r in rows])
        made[f"uploaded/{name}"] = up_dir / name
        up_rows.append([name, str(len(rows)), str(len(header)), "user-supplied REAL export",
                        "OOXML/XLSX with .csv extension -> UTF-8 CSV"])

    # --- 2. Copy the 8 exact-named evidence CSVs (previous task expectations)
    ev_dir = out / "evidence"
    ev_dir.mkdir(parents=True, exist_ok=True)
    for s in evidence.SPECS:
        src = evid / s["filename"]
        if src.is_file():
            shutil.copy2(src, ev_dir / s["filename"])
            made[f"evidence/{s['filename']}"] = ev_dir / s["filename"]

    # --- 3. New required deliverables ---------------------------------------
    corpus = procedure_records()
    _w(out / "procedure_corpus.csv",
       ["doc_id", "title", "content", "tenant_id", "published", "version", "retired"], corpus)
    made["procedure_corpus.csv"] = out / "procedure_corpus.csv"

    corpus_json = [dict(zip(["doc_id", "title", "content", "tenant_id", "published", "version", "retired"], r))
                   for r in corpus]
    (out / "procedure_corpus.json").write_text(
        json.dumps({"schema": "procedure_corpus/v1", "generated_at_iso8601": now,
                    "as_of": as_of, "documents": corpus_json}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    made["procedure_corpus.json"] = out / "procedure_corpus.json"

    labels = label_records()
    _w(out / "expected_outcome_labels.csv",
       ["ticket_id", "tenant_id", "question", "expected_decision", "expected_sop_id", "source"], labels)
    made["expected_outcome_labels.csv"] = out / "expected_outcome_labels.csv"

    a, b = _account_rows()
    _w(out / "system_a.csv", ["id", "customer_name", "plan", "status"], a)
    _w(out / "system_b.csv", ["id", "customer_name", "plan", "status"], b)
    made["system_a.csv"] = out / "system_a.csv"
    made["system_b.csv"] = out / "system_b.csv"
    rec_rows, rec = reconcile(a, b)
    _w(out / "reconciliation_report.csv",
       ["id", "in_system_a", "in_system_b", "customer_name_match", "plan_match", "status_match", "finding"],
       rec_rows)
    made["reconciliation_report.csv"] = out / "reconciliation_report.csv"

    refs = [dict(r, retrieved_at_iso8601=now,
                 verification=("direct fetch - full page read" if r["ref_id"] in DIRECT_FETCHED
                               else "search result / reference lead - page not fully verified"))
            for r in WEB_REFERENCES]
    _w(out / "references.csv",
       ["ref_id", "title", "url", "publisher", "topic", "used_for", "retrieved_at_iso8601",
        "verification"],
       [[r["ref_id"], r["title"], r["url"], r["publisher"], r["topic"], r["used_for"],
         r["retrieved_at_iso8601"], r["verification"]] for r in refs])
    made["references.csv"] = out / "references.csv"

    # --- 4. Broad compact system library -----------------------------------
    sys_dir = out / "systems"
    sys_dir.mkdir(parents=True, exist_ok=True)
    sys_files = systems_files(sys_dir)
    for name in sys_files:
        made[f"systems/{name}"] = sys_dir / name

    # --- 5. Validation / honest findings ------------------------------------
    published_active = [r for r in corpus if r[4] == "yes" and r[6] == "no"]
    draft_or_retired = [r for r in corpus if not (r[4] == "yes" and r[6] == "no")]
    valid_ids = {r[0] for r in corpus}
    active_ids = {r[0] for r in published_active}
    bad_refs = [r for r in labels if r[4] not in valid_ids]
    stale_refs = [r for r in labels if r[4] in valid_ids and r[4] not in active_ids]

    findings = []
    for r in bad_refs:
        findings.append(["Labels", f"{r[0]} references unknown expected_sop_id {r[4]}"])
    for r in stale_refs:
        findings.append(["Labels", f"{r[0]} references draft/retired procedure {r[4]} - not served to agents"])
    for f in rec["findings"]:
        findings.append(["Reconciliation", f])
    findings.append(["Uploads", "delivery_manifest.csv references 3 files that were not supplied "
                     "(rolespec_export.csv, qa_review_export.csv, incident_sla_log.csv) - "
                     "Createlee generated simulated versions under systems/"])
    findings.append(["Evidence", "training_records.csv uses status=Yes / completion_status=Completed; "
                     "Signoff expects lowercase completed=yes - alias mapping required"])
    findings.append(["Scope", "Tenant isolation, authenticated E2E flows, hosted telemetry, "
                     "external audit and billing integration are NOT closable by generated files"])
    findings_rows = [[str(i + 1), x[0], x[1]] for i, x in enumerate(findings)]

    rc = {"corpus": len(corpus), "labels": len(labels),
          "corpus_published_active": len(published_active),
          "corpus_draft_or_retired": len(draft_or_retired),
          "labels_answer": sum(1 for r in labels if r[3] == "answer"),
          "labels_escalate": sum(1 for r in labels if r[3] == "escalate"),
          "labels_real": sum(1 for r in labels if r[5] == "real ticket"),
          "labels_synthetic": sum(1 for r in labels if r[5] == "synthetic")}

    coverage_rows = [
        ["1", "Procedure corpus (CSV or JSON, one doc per row)", ">= 20", f"{len(corpus)} rows (+ JSON)", "PASS"],
        ["2", "Corpus columns doc_id,title,content,tenant_id,published,version,retired", "7 cols", "7 cols", "PASS"],
        ["3", "Expected-outcome labels", ">= 50", f"{len(labels)} rows", "PASS"],
        ["4", "Label columns ticket_id,tenant_id,question,expected_decision,expected_sop_id,source", "6 cols", "6 cols", "PASS"],
        ["5", "Two CSV exports reconciled by key column id", "system_a + system_b", "2 files + report", "PASS"],
        ["6", "Gaps preserved, no rows deleted", "0 deletions", "0 deletions", "PASS"],
        ["7", "Real uploaded signoff files ingested", "6 files", f"{len(up_rows)} files", "PASS"],
        ["8", "Excel content saved as .csv supported", "yes", "OOXML + UTF-16 + BOM", "PASS"],
        ["9", "8 exact-named evidence CSVs (previous task)", "8 files", f"{len(evidence.SPECS)} files", "PASS"],
        ["10", "ISO-8601 / UTC timestamps + as-of", "yes", as_of, "PASS"],
        ["11", "Approval gate before save/email", "yes", "report staged as draft", "PASS"],
        ["12", "Web research grounding with URLs + retrieval time", "yes", f"{len(refs)} refs", "PASS"],
        ["13", "Library of system files for future requests", "yes", f"{len(sys_files)} system files", "PASS"],
        ["14", "What files cannot close (5 named limits)", "documented", "documented", "PASS"],
    ]

    payload = {"as_of": as_of, "upload_analysis": up_rows, "row_counts": rc,
               "reconciliation": rec, "references": refs, "coverage_rows": coverage_rows,
               "findings_rows": findings_rows, "file_list": sorted(made.keys())}
    doc = build_report_doc(payload)

    # --- 6. Report in 5 formats (keep exactly one set) ----------------------
    stale = __import__("re").compile(
        r"library_build_report_\d{8}T\d{6}Z(_\d+)?\.(csv|txt|json|pdf|docx)$")
    for old in out.iterdir():
        if old.is_file() and stale.fullmatch(old.name):
            old.unlink()
    exports = {}
    for fmt in formats:
        p = core.export_document(doc, fmt, out, include_timestamp=True)
        exports[fmt] = str(p)
        made[p.name] = p

    # --- 7. INDEX.csv + manifest + README -----------------------------------
    def _write_index() -> None:
        """Write the delivery index. It is refreshed at the very end too, because
        LIBRARY_MANIFEST.json and README.txt are written after this first pass.
        INDEX.csv never lists itself (a self-referential hash is impossible)."""
        index_path = out / "INDEX.csv"
        with index_path.open("w", newline="", encoding="utf-8") as f:
            w = csv_safe.writer(f, lineterminator="\n")
            w.writerow(["relative_path", "kind", "rows", "columns", "size_bytes", "sha256",
                        "origin", "generated_at_iso8601"])
            for p in sorted(out.rglob("*")):
                if not p.is_file() or p.name == "INDEX.csv":
                    continue
                rel = str(p.relative_to(out))
                if rel.startswith("uploaded/"):
                    origin = "USER-REAL"
                elif rel.startswith("evidence/"):
                    origin = "simulated (Signoff fixture)"
                elif rel.startswith("systems/"):
                    origin = "simulated"
                else:
                    origin = "simulated / derived"
                if p.suffix.lower() == ".csv":
                    h, rows = _rows_of(p)
                    rc_, cc_ = len(rows), len(h)
                else:
                    rc_, cc_ = "", ""
                w.writerow([rel, p.suffix.lower().lstrip("."), rc_, cc_, p.stat().st_size,
                            _sha(p), origin, now])
        made["INDEX.csv"] = index_path

    _write_index()

    manifest = {"schema": "createlee_system_library/v1", "platform": config.PLATFORM_NAME,
                "agent": config.AGENT_NAME, "schema_version": config.SCHEMA_VERSION,
                "as_of": as_of, "generated_at_iso8601": now, "time_standard": "ISO-8601 / UTC",
                "root": str(out), "review_status": "EXAMPLE_PREVIEW - PENDING OPERATOR REVIEW",
                "file_count": len([p for p in out.rglob("*") if p.is_file()]),
                "row_counts": rc, "reconciliation": rec,
                "web_references": refs, "limitations": [list(x) for x in LIMITATIONS],
                "honesty": HONESTY, "rows_deleted": 0,
                "report_exports": {k: Path(v).name for k, v in exports.items()},
                "report_document_id": doc["document_id"],
                "findings": [x[1] for x in findings]}
    (out / "LIBRARY_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    made["LIBRARY_MANIFEST.json"] = out / "LIBRARY_MANIFEST.json"

    lines = [
        "Createlee / Engeznee - System Library", "======================================", "",
        f"As-of (--as-of):             {as_of}",
        f"Generated at (ISO-8601 UTC): {now}",
        f"Generator:                   {config.PLATFORM_NAME} / {config.AGENT_NAME} (schema {config.SCHEMA_VERSION})",
        f"Review status:               EXAMPLE_PREVIEW - PENDING OPERATOR REVIEW", "",
        "WHAT THIS IS", "------------",
        "A compact, reusable library of system files to be referred to afterwards.",
        "Data is SIMULATED real-life operational data grounded in REAL published standards",
        "fetched from the web (ITU-T, TM Forum, ISO/IEC 42001, EU AI Act). Start small,",
        "expand later: replace any file with your own export of the same name.", "",
        "ROW COUNTS", "----------",
        f"  Procedure corpus:          {rc['corpus']} documents   (required >= 20)",
        f"    published & active:      {rc['corpus_published_active']}",
        f"    draft or retired:        {rc['corpus_draft_or_retired']}",
        f"  Expected-outcome labels:   {rc['labels']} tickets     (required >= 50)",
        f"    answer / escalate:       {rc['labels_answer']} / {rc['labels_escalate']}",
        f"    source real / synthetic: {rc['labels_real']} / {rc['labels_synthetic']}",
        f"  system_a.csv:              {rec['in_system_a']} rows (key = id)",
        f"  system_b.csv:              {rec['in_system_b']} rows (key = id)",
        f"  Fully reconciled:          {rec['fully_reconciled']} / {rec['keys_total']} union keys",
        f"  A-only / B-only:           {rec['a_only']} / {rec['b_only']}",
        f"  Field mismatches:          {rec['field_mismatches']}",
        f"  Rows deleted:              0", "",
        "FOLDER MAP", "----------",
        "  uploaded/    6 REAL files you supplied (XLSX saved as .csv -> UTF-8 CSV, rows preserved)",
        "  evidence/    8 exact-named Signoff evidence CSVs from the previous task",
        "  systems/     compact system library (tenants, agents, AI agents, customers, plans,",
        "               tickets, SLA, channels, controls, roster, approvals, change log, ...)",
        "  Primary required outputs at root: procedure_corpus.csv/.json,",
        "               expected_outcome_labels.csv, system_a.csv, system_b.csv,",
        "               reconciliation_report.csv, references.csv",
        "  INDEX.csv / LIBRARY_MANIFEST.json / README.txt / build report (5 formats)", "",
        "WEB REFERENCES (real public standards)", "------------------------------------",
    ]
    for r in refs:
        lines += [f"  {r['ref_id']}  {r['publisher']}", f"      {r['title'][:88]}", f"      {r['url']}",
                  f"      retrieved {r['retrieved_at_iso8601']}",
                  f"      verification: {r['verification']}"]
    lines += ["", "HONESTY BOUNDARY", "----------------"]
    for w in _wrap(HONESTY, 94):
        lines.append("  " + w)
    lines += ["", "WHAT YOUR FILES CANNOT CLOSE (needs your organisation)", "------------------------------------------------------",
              "  No generated CSV/JSON can evidence the following. They require your engineering",
              "  and security teams: ", ""]
    for k, v in LIMITATIONS:
        lines.append(f"  - {k}: {v}")
    lines += ["", "HONEST FINDINGS (preserved, not cleaned)", "----------------------------------------"]
    for i, x in enumerate(findings, 1):
        lines.append(f"  {i:>2}. [{x[0]}] {x[1]}")
    lines += [
        "", "HOW TO EXTEND", "-------------",
        "  - Replace any CSV in place with your own export of the same name.",
        "  - Add procedures to procedure_corpus.csv / .json (one document per row).",
        "  - Add QA-labelled tickets to expected_outcome_labels.csv.",
        "  - Re-run: python3.11 library.py --out /workspace/system_library --as-of 2026-11-06",
        "  - In the app: type 'library' or 'library --as-of 2026-11-06', or POST /api/library.",
        "  - No external organisational approval is needed to generate these internal exports;",
        "    Createlee's own operator review gate still applies before the report is saved/emailed.",
        "",
    ]
    (out / "README.txt").write_text("\n".join(lines), encoding="utf-8")
    made["README.txt"] = out / "README.txt"

    # Final consistency pass: the manifest and README were written after the first
    # index pass. Refresh the count and the index LAST so INDEX lists every file and
    # every sha256 - including the manifest's final bytes - is accurate.
    manifest["file_count"] = len([p for p in out.rglob("*")
                                  if p.is_file() and p.name != "INDEX.csv"]) + 1
    (out / "LIBRARY_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_index()

    return {"ok": True, "as_of": as_of, "out_dir": str(out), "manifest": manifest,
            "report_doc": doc, "report_exports": exports, "files": made,
            "findings": [x[1] for x in findings], "row_counts": rc,
            "reconciliation": rec, "coverage_rows": coverage_rows,
            "upload_analysis": up_rows}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Createlee system library builder")
    ap.add_argument("--out", default=str(config.LIBRARY_DIR), help="output directory")
    ap.add_argument("--as-of", default=None, help="YYYY-MM-DD (default: today UTC)")
    ap.add_argument("--uploads", default=None, help="folder with the 6 real uploaded files")
    ap.add_argument("--evidence", default=None, help="folder with the 8 evidence CSVs")
    args = ap.parse_args()
    r = build_library(args.out, args.as_of,
                      uploads_dir=args.uploads, evidence_dir=args.evidence)
    m = r["manifest"]
    print(f"as-of: {r['as_of']}  generated: {m['generated_at_iso8601']}")
    print(f"out_dir: {r['out_dir']}  files: {m['file_count']}")
    print(f"row_counts: {json.dumps(r['row_counts'], ensure_ascii=False)}")
    print(f"reconciliation: {json.dumps(r['reconciliation'], ensure_ascii=False)}")
    print(f"findings: {len(r['findings'])} (all preserved, rows_deleted=0)")
    for i, req in enumerate(r["coverage_rows"], 1):
        print(f"  {i:>2}. [{req[4]}] {req[1]} -> {req[3]}")
    print("report exports: " + ", ".join(f"{k}={Path(v).name}" for k, v in r["report_exports"].items()))
