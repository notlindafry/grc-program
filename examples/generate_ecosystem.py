#!/usr/bin/env python3
"""Generate the v2 GRC-ecosystem corpus under ``data/`` (SPEC §2, §5).

This extends ``generate_corpus.py`` (which still writes the legacy risks /
exceptions / remediations / okrs the engine reads) with the new-model entities:
the enterprise anchor, the Tier-1 domains, Tier-2 named risks, Tier-3 scenarios,
the generalised issues floor (vulns + findings; exceptions stay in their own
directory and are read as ``type: exception``), the ISO 27001:2022 Annex A
control backbone, policies, evidence, KRIs, and the horizon watch list.

Day 1 scope: coherent, valid shapes that load, validate, and confirm the SPEC §3
cardinalities, with one populated example per entity. The fully designed corpus
that tells all ten SPEC §5 stories is Day-3 work; this is the foundation it
builds on. All data is synthetic (SPEC §11).

Run via ``python examples/generate_corpus.py`` (which calls ``build_ecosystem``),
or standalone with ``python examples/generate_ecosystem.py``.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SCN = DATA / "scenarios"
ISSUES = DATA / "issues"


# ---------------------------------------------------------------------------
# 1. Enterprise anchor (SPEC §2.1)
# ---------------------------------------------------------------------------

ENTERPRISE = """\
# The top-level appetite anchor (SPEC §2.1, §4). Two dollar figures:
#   capacity_materiality  -- the hard audit-materiality line the company cannot
#                            cross by choice (the binding, smaller number).
#   appetite (derived)    -- appetite_pct_of_revenue x revenue_annual, a
#                            revenue-percent figure set deliberately BENEATH
#                            capacity, that scales with the company and reads
#                            cleanly to a board.
# All figures synthetic.

revenue_annual: 2000000000          # $2B; the base for the appetite percentage
capacity_materiality: 15000000      # $15M hard line (audit materiality)
appetite_pct_of_revenue: 0.005      # 0.5% -> $10M declared appetite, set beneath capacity
green_band_floor: 0.75              # residual in the top quarter of tolerance reads green (SPEC §4)
"""


# ---------------------------------------------------------------------------
# 2. Domains -- Tier 1 (SPEC §1, §2.2)
# ---------------------------------------------------------------------------

DOMAINS = [
    ("TR-RESILIENCE", "Resilience", "down or cannot recover",
     "measured availability risk accepted to sustain launch velocity", "cro@company.com"),
    ("TR-DATA-INTEGRITY", "Data integrity", "data wrong, corrupted, or lost; includes analytics/ML input quality",
     "data-quality risk held low; correctness is a product promise", "cro@company.com"),
    ("TR-SECURITY", "Security", "adversarial compromise; unauthorized access or disclosure",
     "compromise tolerance kept tight; breaches are existential to trust", "ciso@company.com"),
    ("TR-PRIVACY", "Privacy", "misused regulated/personal data: residency, retention, consent, subprocessor governance",
     "regulated-data misuse held near zero; this is a licence-to-operate risk", "dpo@company.com"),
    ("TR-CHANGE", "Change & delivery", "shipping or rebuilding breaks things: change failure, migration/cutover, launch readiness, velocity-driven debt",
     "elevated change risk knowingly accepted during the rebuild window", "cto@company.com"),
    ("TR-THIRDPARTY", "Third-party", "an external dependency's failure becomes yours; concentration risk",
     "concentration risk monitored; single-provider dependence flagged", "ciso@company.com"),
    ("TR-COMPLIANCE", "Compliance", "pure obligation failure with no technical trigger: missed filings, lapsed certifications, failed audits/attestations",
     "obligation failures not tolerated; these are binary pass/fail", "gc@company.com"),
]

DOMAIN_YAML_HEAD = """\
# Tier 1 -- where the risk manifests (board / portfolio altitude, SPEC §1, §2.2).
# The appetite_statement is board-facing narrative ONLY, never tested against a
# number (SPEC §4). Governance metadata (sign-off, last reviewed) sits here.
# All data synthetic.

"""


def render_domains() -> str:
    out = [DOMAIN_YAML_HEAD]
    for did, title, desc, statement, signer in DOMAINS:
        out.append(
            f"{did}:\n"
            f"  title: {title}\n"
            f'  description: "{desc}"\n'
            f'  appetite_statement: "{statement}"\n'
            f"  appetite_signed_off_by: {signer}\n"
            f"  appetite_last_reviewed: 2026-05-01\n"
        )
    return "\n".join(out)


# ---------------------------------------------------------------------------
# 3. Policies -- the governance layer above controls (SPEC §2.7)
# ---------------------------------------------------------------------------

POLICIES = [
    ("POL-INFOSEC", "Information Security Policy", "ciso-office@company.com", "2026-02-01"),
    ("POL-ACCESS-CONTROL", "Access Control Policy", "ciso-office@company.com", "2026-02-01"),
    ("POL-CRYPTO", "Cryptography & Key Management Policy", "ciso-office@company.com", "2026-01-15"),
    ("POL-ASSET-MGMT", "Asset Management Policy", "it-office@company.com", "2025-11-10"),
    ("POL-DATA-CLASSIFICATION", "Data Classification & Handling Policy", "dpo@company.com", "2026-03-01"),
    ("POL-PRIVACY", "Privacy & Personal Data Policy", "dpo@company.com", "2026-03-01"),
    ("POL-SUPPLIER", "Supplier & Third-Party Security Policy", "procurement-office@company.com", "2025-12-05"),
    ("POL-INCIDENT", "Information Security Incident Management Policy", "ciso-office@company.com", "2026-02-20"),
    ("POL-BCP", "Business Continuity & ICT Readiness Policy", "resilience-office@company.com", "2026-01-30"),
    ("POL-HR-SECURITY", "Human Resources Security Policy", "people-office@company.com", "2025-10-12"),
    ("POL-PHYSICAL", "Physical & Environmental Security Policy", "facilities-office@company.com", "2025-09-20"),
    ("POL-SECURE-DEV", "Secure Development Policy", "eng-office@company.com", "2026-04-01"),
    ("POL-VULN-MGMT", "Technical Vulnerability Management Policy", "ciso-office@company.com", "2026-04-10"),
    ("POL-CHANGE-MGMT", "Change Management Policy", "eng-office@company.com", "2026-03-15"),
    ("POL-LOGGING-MONITORING", "Logging & Monitoring Policy", "soc-office@company.com", "2026-02-05"),
    ("POL-NETWORK", "Network Security Policy", "network-office@company.com", "2026-01-08"),
    ("POL-COMPLIANCE", "Legal & Regulatory Compliance Policy", "gc-office@company.com", "2026-02-28"),
]

POLICY_YAML_HEAD = """\
# The governance layer above controls (SPEC §2.7, thin). The coverage read is
# "every control traces up to a governing policy." Links are placeholders.
# All data synthetic.

"""


def render_policies() -> str:
    out = [POLICY_YAML_HEAD]
    for pid, title, owner, reviewed in POLICIES:
        slug = pid.lower().replace("pol-", "")
        out.append(
            f"{pid}:\n"
            f"  title: {title}\n"
            f"  owner: {owner}\n"
            f"  last_reviewed: {reviewed}\n"
            f"  link: https://policies.example.com/{slug}\n"
        )
    return "\n".join(out)


# ---------------------------------------------------------------------------
# 4. Controls -- the ISO 27001:2022 Annex A backbone, all 93 (SPEC §2.6)
# ---------------------------------------------------------------------------
# Four themes: Organizational (A.5.1-A.5.37, 37), People (A.6.1-A.6.8, 8),
# Physical (A.7.1-A.7.14, 14), Technological (A.8.1-A.8.34, 34) = 93.

ANNEX_A = {
    "Organizational": [
        "Policies for information security",
        "Information security roles and responsibilities",
        "Segregation of duties",
        "Management responsibilities",
        "Contact with authorities",
        "Contact with special interest groups",
        "Threat intelligence",
        "Information security in project management",
        "Inventory of information and other associated assets",
        "Acceptable use of information and other associated assets",
        "Return of assets",
        "Classification of information",
        "Labelling of information",
        "Information transfer",
        "Access control",
        "Identity management",
        "Authentication information",
        "Access rights",
        "Information security in supplier relationships",
        "Addressing information security within supplier agreements",
        "Managing information security in the ICT supply chain",
        "Monitoring, review and change management of supplier services",
        "Information security for use of cloud services",
        "Information security incident management planning and preparation",
        "Assessment and decision on information security events",
        "Response to information security incidents",
        "Learning from information security incidents",
        "Collection of evidence",
        "Information security during disruption",
        "ICT readiness for business continuity",
        "Legal, statutory, regulatory and contractual requirements",
        "Intellectual property rights",
        "Protection of records",
        "Privacy and protection of personal identifiable information (PII)",
        "Independent review of information security",
        "Compliance with policies, rules and standards for information security",
        "Documented operating procedures",
    ],
    "People": [
        "Screening",
        "Terms and conditions of employment",
        "Information security awareness, education and training",
        "Disciplinary process",
        "Responsibilities after termination or change of employment",
        "Confidentiality or non-disclosure agreements",
        "Remote working",
        "Information security event reporting",
    ],
    "Physical": [
        "Physical security perimeters",
        "Physical entry",
        "Securing offices, rooms and facilities",
        "Physical security monitoring",
        "Protecting against physical and environmental threats",
        "Working in secure areas",
        "Clear desk and clear screen",
        "Equipment siting and protection",
        "Security of assets off-premises",
        "Storage media",
        "Supporting utilities",
        "Cabling security",
        "Equipment maintenance",
        "Secure disposal or re-use of equipment",
    ],
    "Technological": [
        "User endpoint devices",
        "Privileged access rights",
        "Information access restriction",
        "Access to source code",
        "Secure authentication",
        "Capacity management",
        "Protection against malware",
        "Management of technical vulnerabilities",
        "Configuration management",
        "Information deletion",
        "Data masking",
        "Data leakage prevention",
        "Information backup",
        "Redundancy of information processing facilities",
        "Logging",
        "Monitoring activities",
        "Clock synchronization",
        "Use of privileged utility programs",
        "Installation of software on operational systems",
        "Networks security",
        "Security of network services",
        "Segregation of networks",
        "Web filtering",
        "Use of cryptography",
        "Secure development life cycle",
        "Application security requirements",
        "Secure system architecture and engineering principles",
        "Secure coding",
        "Security testing in development and acceptance",
        "Outsourced development",
        "Separation of development, test and production environments",
        "Change management",
        "Test information",
        "Protection of information systems during audit testing",
    ],
}
_THEME_CLAUSE = {"Organizational": 5, "People": 6, "Physical": 7, "Technological": 8}

# Governing policy per Annex A reference (SPEC §2.7 coverage: every control ->
# exactly one policy). Anything unlisted falls back to POL-INFOSEC.
CONTROL_POLICY = {
    "A.5.1": "POL-INFOSEC", "A.5.2": "POL-INFOSEC", "A.5.3": "POL-ACCESS-CONTROL",
    "A.5.4": "POL-INFOSEC", "A.5.5": "POL-COMPLIANCE", "A.5.6": "POL-INFOSEC",
    "A.5.7": "POL-LOGGING-MONITORING", "A.5.8": "POL-SECURE-DEV",
    "A.5.9": "POL-ASSET-MGMT", "A.5.10": "POL-ASSET-MGMT", "A.5.11": "POL-ASSET-MGMT",
    "A.5.12": "POL-DATA-CLASSIFICATION", "A.5.13": "POL-DATA-CLASSIFICATION",
    "A.5.14": "POL-DATA-CLASSIFICATION", "A.5.15": "POL-ACCESS-CONTROL",
    "A.5.16": "POL-ACCESS-CONTROL", "A.5.17": "POL-ACCESS-CONTROL", "A.5.18": "POL-ACCESS-CONTROL",
    "A.5.19": "POL-SUPPLIER", "A.5.20": "POL-SUPPLIER", "A.5.21": "POL-SUPPLIER",
    "A.5.22": "POL-SUPPLIER", "A.5.23": "POL-SUPPLIER",
    "A.5.24": "POL-INCIDENT", "A.5.25": "POL-INCIDENT", "A.5.26": "POL-INCIDENT",
    "A.5.27": "POL-INCIDENT", "A.5.28": "POL-INCIDENT",
    "A.5.29": "POL-BCP", "A.5.30": "POL-BCP",
    "A.5.31": "POL-COMPLIANCE", "A.5.32": "POL-COMPLIANCE", "A.5.33": "POL-COMPLIANCE",
    "A.5.34": "POL-PRIVACY", "A.5.35": "POL-INFOSEC", "A.5.36": "POL-COMPLIANCE",
    "A.5.37": "POL-INFOSEC",
    "A.6.1": "POL-HR-SECURITY", "A.6.2": "POL-HR-SECURITY", "A.6.3": "POL-HR-SECURITY",
    "A.6.4": "POL-HR-SECURITY", "A.6.5": "POL-HR-SECURITY", "A.6.6": "POL-HR-SECURITY",
    "A.6.7": "POL-HR-SECURITY", "A.6.8": "POL-INCIDENT",
    "A.7.1": "POL-PHYSICAL", "A.7.2": "POL-PHYSICAL", "A.7.3": "POL-PHYSICAL",
    "A.7.4": "POL-PHYSICAL", "A.7.5": "POL-PHYSICAL", "A.7.6": "POL-PHYSICAL",
    "A.7.7": "POL-PHYSICAL", "A.7.8": "POL-PHYSICAL", "A.7.9": "POL-PHYSICAL",
    "A.7.10": "POL-ASSET-MGMT", "A.7.11": "POL-PHYSICAL", "A.7.12": "POL-PHYSICAL",
    "A.7.13": "POL-PHYSICAL", "A.7.14": "POL-ASSET-MGMT",
    "A.8.1": "POL-ACCESS-CONTROL", "A.8.2": "POL-ACCESS-CONTROL", "A.8.3": "POL-ACCESS-CONTROL",
    "A.8.4": "POL-SECURE-DEV", "A.8.5": "POL-ACCESS-CONTROL", "A.8.6": "POL-BCP",
    "A.8.7": "POL-INFOSEC", "A.8.8": "POL-VULN-MGMT", "A.8.9": "POL-CHANGE-MGMT",
    "A.8.10": "POL-DATA-CLASSIFICATION", "A.8.11": "POL-PRIVACY", "A.8.12": "POL-DATA-CLASSIFICATION",
    "A.8.13": "POL-BCP", "A.8.14": "POL-BCP", "A.8.15": "POL-LOGGING-MONITORING",
    "A.8.16": "POL-LOGGING-MONITORING", "A.8.17": "POL-LOGGING-MONITORING", "A.8.18": "POL-ACCESS-CONTROL",
    "A.8.19": "POL-CHANGE-MGMT", "A.8.20": "POL-NETWORK", "A.8.21": "POL-NETWORK",
    "A.8.22": "POL-NETWORK", "A.8.23": "POL-NETWORK", "A.8.24": "POL-CRYPTO",
    "A.8.25": "POL-SECURE-DEV", "A.8.26": "POL-SECURE-DEV", "A.8.27": "POL-SECURE-DEV",
    "A.8.28": "POL-SECURE-DEV", "A.8.29": "POL-SECURE-DEV", "A.8.30": "POL-SUPPLIER",
    "A.8.31": "POL-CHANGE-MGMT", "A.8.32": "POL-CHANGE-MGMT", "A.8.33": "POL-SECURE-DEV",
    "A.8.34": "POL-COMPLIANCE",
}

# Named-risk mappings per control (SPEC §2.6, M2M). A meaningful subset -- a
# control mapping to no named risk is left deliberately for a few (e.g. IP
# rights, supporting utilities) so the "why do we do this?" flag is demonstrated.
CONTROL_NAMED_RISKS = {
    "A.5.7": ["NR-PROD-COMPROMISE"],
    "A.5.14": ["NR-DATA-EXFIL"],
    "A.5.15": ["NR-PROD-COMPROMISE"], "A.5.16": ["NR-PROD-COMPROMISE"],
    "A.5.17": ["NR-PROD-COMPROMISE"], "A.5.18": ["NR-PROD-COMPROMISE", "NR-VENDOR-ACCESS"],
    "A.5.19": ["NR-VENDOR-ACCESS"], "A.5.20": ["NR-VENDOR-ACCESS"],
    "A.5.21": ["NR-MODEL-SUPPLY", "NR-VENDOR-ACCESS"], "A.5.22": ["NR-VENDOR-ACCESS"],
    "A.5.23": ["NR-PLATFORM-OUTAGE", "NR-VENDOR-ACCESS"],
    "A.5.24": ["NR-PLATFORM-OUTAGE"], "A.5.26": ["NR-PROD-COMPROMISE"],
    "A.5.29": ["NR-PLATFORM-OUTAGE", "NR-DATA-AVAILABILITY"],
    "A.5.30": ["NR-PLATFORM-OUTAGE"],
    "A.5.31": ["NR-REG-FILINGS", "NR-PCI-SCOPE"], "A.5.33": ["NR-REG-FILINGS"],
    "A.5.34": ["NR-DATA-RESIDENCY", "NR-SUBPROCESSOR-GOV"],
    "A.5.36": ["NR-PCI-SCOPE", "NR-REG-FILINGS"],
    "A.6.3": ["NR-ENDPOINT-MALWARE"], "A.6.7": ["NR-ENDPOINT-MALWARE"],
    "A.8.1": ["NR-ENDPOINT-MALWARE"], "A.8.2": ["NR-PROD-COMPROMISE"],
    "A.8.3": ["NR-DATA-EXFIL", "NR-PROD-COMPROMISE"], "A.8.4": ["NR-MIGRATION-DATAINTEGRITY"],
    "A.8.5": ["NR-PROD-COMPROMISE"], "A.8.6": ["NR-PLATFORM-OUTAGE", "NR-DATA-AVAILABILITY"],
    "A.8.7": ["NR-ENDPOINT-MALWARE"], "A.8.8": ["NR-PROD-COMPROMISE", "NR-ENDPOINT-MALWARE"],
    "A.8.9": ["NR-MIGRATION-AVAILABILITY"], "A.8.11": ["NR-DATA-RESIDENCY", "NR-DATA-EXFIL"],
    "A.8.12": ["NR-DATA-EXFIL"], "A.8.13": ["NR-DATA-AVAILABILITY", "NR-MIGRATION-DATAINTEGRITY"],
    "A.8.14": ["NR-PLATFORM-OUTAGE"], "A.8.15": ["NR-ABUSE-DETECTION", "NR-PROD-COMPROMISE"],
    "A.8.16": ["NR-ABUSE-DETECTION", "NR-CARD-TESTING"], "A.8.20": ["NR-PROD-COMPROMISE"],
    "A.8.21": ["NR-PLATFORM-OUTAGE"], "A.8.22": ["NR-PROD-COMPROMISE"],
    "A.8.23": ["NR-ENDPOINT-MALWARE"], "A.8.24": ["NR-DATA-EXFIL", "NR-DATA-RESIDENCY"],
    "A.8.25": ["NR-MIGRATION-DATAINTEGRITY"], "A.8.26": ["NR-CARD-TESTING"],
    "A.8.28": ["NR-MIGRATION-DATAINTEGRITY"], "A.8.29": ["NR-MIGRATION-AVAILABILITY"],
    "A.8.30": ["NR-MODEL-SUPPLY"], "A.8.31": ["NR-MIGRATION-AVAILABILITY"],
    "A.8.32": ["NR-MIGRATION-AVAILABILITY", "NR-MIGRATION-DATAINTEGRITY"],
    "A.8.33": ["NR-DATA-QUALITY"], "A.8.34": ["NR-PCI-SCOPE"],
    # Data-quality / pipeline integrity controls:
    "A.5.12": ["NR-DATA-QUALITY"], "A.8.10": ["NR-DATA-RESIDENCY"],
}

# A small, deliberate set of controls left mapping to NO named risk, so the
# "why do we do this?" flag (SPEC §2.6) is demonstrated as a rare, meaningful
# signal rather than blanket noise. These are genuinely weak fits for a pure-
# software fintech's tech-risk taxonomy.
ORPHAN_CONTROLS = {"A.5.6", "A.5.32", "A.7.11"}  # special-interest groups, IP rights, supporting utilities

# Theme fallback for controls without a specific mapping: the named risk that
# theme's controls broadly support. Keeps the SoA coverage read honest without
# fabricating pinpoint mappings for every Annex A line.
THEME_DEFAULT_RISK = {
    "Organizational": "NR-PROD-COMPROMISE",
    "People": "NR-ENDPOINT-MALWARE",
    "Physical": "NR-ENDPOINT-MALWARE",
    "Technological": "NR-PROD-COMPROMISE",
}


def named_risks_for(ref: str, theme: str) -> list[str]:
    """Named risks a control mitigates: explicit map, then orphan, then theme default."""
    if ref in CONTROL_NAMED_RISKS:
        return CONTROL_NAMED_RISKS[ref]
    if ref in ORPHAN_CONTROLS:
        return []
    return [THEME_DEFAULT_RISK[theme]]

CONTROL_YAML_HEAD = """\
# The ISO/IEC 27001:2022 Annex A control backbone -- all 93 controls across the
# four themes (Organizational A.5, People A.6, Physical A.7, Technological A.8;
# 37/8/14/34). Keyed by Annex A reference so the full set is unambiguously
# seeded (SPEC §2.6). Each control names its governing policy (the "traces up to
# a policy" coverage read) and the named risks it mitigates (M2M). A control
# mapping to no named risk is a "why do we do this?" signal, surfaced by
# validation. Control HEALTH is derived at build time (SPEC §4), never stored.
# All data synthetic.

"""


def render_controls() -> str:
    out = [CONTROL_YAML_HEAD]
    for theme, titles in ANNEX_A.items():
        clause = _THEME_CLAUSE[theme]
        out.append(f"# --- {theme} (A.{clause}.1-A.{clause}.{len(titles)}, {len(titles)}) ---\n")
        for i, title in enumerate(titles, start=1):
            ref = f"A.{clause}.{i}"
            policy = CONTROL_POLICY.get(ref, "POL-INFOSEC")
            risks = named_risks_for(ref, theme)
            risks_render = "[" + ", ".join(risks) + "]" if risks else "[]"
            out.append(
                f'"{ref}":\n'
                f"  title: {title}\n"
                f"  theme: {theme}\n"
                f"  policy: {policy}\n"
                f"  mapped_named_risks: {risks_render}\n"
            )
        out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# 5. Named risks -- Tier 2 (SPEC §2.3). One per legacy risk + a few new.
# ---------------------------------------------------------------------------
# (id, title, domain, owner, appetite_threshold, threatens_okrs)

NAMED_RISKS = [
    ("NR-PROD-COMPROMISE", "Compromise of production systems via credential or access failure",
     "TR-SECURITY", "security-eng-lead@company.com", 5000000, ["gcloud-migration"]),
    ("NR-DATA-EXFIL", "Exfiltration of regulated data from an analytics or export path",
     "TR-SECURITY", "security-eng-lead@company.com", 6000000, ["data-platform"]),
    ("NR-PAYMENT-FRAUD", "Fraudulent transactions against the payments platform",
     "TR-SECURITY", "payments-lead@company.com", 30000000, ["payments-launch"]),
    ("NR-PCI-SCOPE", "PCI scope expansion / cardholder data handling gap",
     "TR-COMPLIANCE", "payments-lead@company.com", 25000000, ["payments-launch"]),
    ("NR-DATA-QUALITY", "Corrupted or unvalidated data feeding downstream decisions",
     "TR-DATA-INTEGRITY", "data-platform-lead@company.com", 15000000, ["data-platform"]),
    ("NR-DATA-AVAILABILITY", "Loss of availability of a core data platform service",
     "TR-RESILIENCE", "data-platform-lead@company.com", 15000000, ["data-platform"]),
    ("NR-ABUSE-ESCALATION", "Unmitigated abuse escalating on the platform",
     "TR-SECURITY", "tns-lead@company.com", 15000000, ["trust-and-safety"]),
    ("NR-ABUSE-DETECTION", "Gaps in automated detection of policy-violating content",
     "TR-SECURITY", "tns-lead@company.com", 15000000, ["trust-and-safety"]),
    ("NR-MIGRATION-AVAILABILITY", "Availability regressions introduced by the migration",
     "TR-CHANGE", "platform-lead@company.com", 10000000, ["gcloud-migration"]),
    ("NR-MIGRATION-DATAINTEGRITY", "Data integrity loss during monolith-to-microservices cutover",
     "TR-CHANGE", "platform-lead@company.com", 10000000, ["gcloud-migration"]),
    ("NR-VENDOR-ACCESS", "Excessive third-party vendor access to internal systems",
     "TR-THIRDPARTY", "ciso-office@company.com", 8000000, ["mobile-app", "internal-tools"]),
    ("NR-ENDPOINT-MALWARE", "Malware on a corporate endpoint leading to lateral movement",
     "TR-SECURITY", "it-lead@company.com", 10000000, ["internal-tools"]),
    ("NR-PLATFORM-OUTAGE", "Customer-facing outage of a core platform service",
     "TR-RESILIENCE", "platform-lead@company.com", 15000000, ["core-platform"]),
    ("NR-DATA-RESIDENCY", "Regulated data leaving its required residency region",
     "TR-PRIVACY", "dpo@company.com", 14000000, ["data-platform"]),
    ("NR-CARD-TESTING", "Automated card-testing against the public checkout flow",
     "TR-SECURITY", "payments-lead@company.com", 12000000, ["payments-launch"]),
    ("NR-PIPELINE-INTEGRITY", "Schema-invalid or corrupted writes entering the data pipeline",
     "TR-DATA-INTEGRITY", "data-platform-lead@company.com", 8000000, ["data-platform"]),
    # --- New named risks beyond the migrated legacy set ---
    ("NR-REG-FILINGS", "Missed regulatory filing or lapsed certification",
     "TR-COMPLIANCE", "compliance-lead@company.com", 8000000, ["run-the-business"]),
    ("NR-SUBPROCESSOR-GOV", "Ungoverned subprocessor handling of regulated data",
     "TR-PRIVACY", "dpo@company.com", 9000000, ["data-platform"]),
    ("NR-AI-AGENT-AUTONOMY", "Autonomous agents taking unsafe action in production",
     "TR-CHANGE", "ai-platform-lead@company.com", 6000000, ["core-platform"]),
    ("NR-MODEL-SUPPLY", "Concentration on a single external model provider",
     "TR-THIRDPARTY", "ai-platform-lead@company.com", 7000000, ["data-platform"]),
]

NAMED_RISK_YAML_HEAD = """\
# Tier 2 -- the owned, appetite-bearing risk (executive / VP altitude, SPEC §2.3).
# Each names its Tier-1 domain (many-to-one), the accountable owner in the mgmt
# hierarchy, the bottom-up per-risk dollar appetite, and the OKRs it threatens
# (M2M, SPEC §2.12). All data synthetic.

"""


def render_named_risks() -> str:
    out = [NAMED_RISK_YAML_HEAD]
    for nid, title, domain, owner, appetite, okrs in NAMED_RISKS:
        okr_render = "[" + ", ".join(okrs) + "]"
        out.append(
            f"{nid}:\n"
            f"  title: {title}\n"
            f"  domain: {domain}\n"
            f"  owner: {owner}\n"
            f"  appetite_threshold: {appetite}\n"
            f"  threatens_okrs: {okr_render}\n"
        )
    return "\n".join(out)


# ---------------------------------------------------------------------------
# 6. Scenarios -- Tier 3 (SPEC §2.4). The baseline the Monte Carlo runs on.
# ---------------------------------------------------------------------------
# (id, title, named_risk, OF, PoR, LM, impact, vectors, lifecycle, trajectory,
#  legacy_risk). The first 17 carry the legacy baselines and bridge the existing
#  exceptions via legacy_risk; the rest are new managed + emerging scenarios.

SCENARIOS = [
    ("SCN-2026-0001", "Account takeover of an internal admin console", "NR-PROD-COMPROMISE",
     [10, 40], [0.005, 0.02], [2000000, 5000000], ["financial", "individual_harm"],
     ["adversarial"], "managed", "stable", "RISK-ACCT-TAKEOVER"),
    ("SCN-2026-0002", "Exfiltration of regulated data via an analytics export path", "NR-DATA-EXFIL",
     [20, 80], [0.01, 0.04], [1000000, 3000000], ["financial", "individual_harm", "regulatory"],
     ["adversarial"], "managed", "stable", "RISK-DATA-EXFIL"),
    ("SCN-2026-0003", "Fraudulent transactions against the payments platform", "NR-PAYMENT-FRAUD",
     [15, 50], [0.02, 0.06], [1200000, 3000000], ["financial", "public_market_harm"],
     ["adversarial"], "managed", "stable", "RISK-PAYMENT-FRAUD"),
    ("SCN-2026-0004", "Cardholder data handling gap expands PCI scope", "NR-PCI-SCOPE",
     [5, 20], [0.01, 0.04], [2000000, 7000000], ["financial", "regulatory"],
     [], "managed", "stable", "RISK-PCI-SCOPE"),
    ("SCN-2026-0005", "Corrupted or unvalidated data feeds a downstream decision", "NR-DATA-QUALITY",
     [10, 50], [0.02, 0.10], [500000, 2000000], ["financial", "individual_harm"],
     [], "managed", "stable", "RISK-DATA-QUALITY"),
    ("SCN-2026-0006", "Loss of availability of a core data platform service", "NR-DATA-AVAILABILITY",
     [10, 40], [0.02, 0.08], [800000, 2500000], ["financial"],
     [], "managed", "stable", "RISK-DATA-AVAILABILITY"),
    ("SCN-2026-0007", "Unmitigated abuse escalating on the platform", "NR-ABUSE-ESCALATION",
     [20, 80], [0.03, 0.10], [400000, 1500000], ["individual_harm", "reputational"],
     ["adversarial"], "managed", "stable", "RISK-ABUSE-ESCALATION"),
    ("SCN-2026-0008", "Detection model misses policy-violating content at scale", "NR-ABUSE-DETECTION",
     [20, 70], [0.02, 0.08], [500000, 1800000], ["individual_harm", "public_market_harm"],
     ["adversarial"], "managed", "stable", "RISK-ABUSE-DETECTION"),
    ("SCN-2026-0009", "Availability regression introduced by the migration", "NR-MIGRATION-AVAILABILITY",
     [10, 40], [0.02, 0.08], [600000, 2000000], ["financial"],
     [], "managed", "rising", "RISK-MIGRATION-AVAILABILITY"),
    ("SCN-2026-0010", "Data integrity loss during monolith-to-microservices cutover", "NR-MIGRATION-DATAINTEGRITY",
     [5, 20], [0.01, 0.05], [1000000, 4000000], ["financial", "individual_harm"],
     [], "managed", "rising", "RISK-MIGRATION-DATAINTEGRITY"),
    ("SCN-2026-0011", "Excessive third-party vendor access to internal systems", "NR-VENDOR-ACCESS",
     [5, 20], [0.01, 0.04], [800000, 3000000], ["financial", "individual_harm"],
     ["third_party"], "managed", "stable", "RISK-VENDOR-ACCESS"),
    ("SCN-2026-0012", "Malware on a corporate endpoint leads to lateral movement", "NR-ENDPOINT-MALWARE",
     [30, 100], [0.02, 0.08], [300000, 1200000], ["financial"],
     ["adversarial"], "managed", "stable", "RISK-ENDPOINT-MALWARE"),
    ("SCN-2026-0013", "Customer-facing outage of a core platform service", "NR-PLATFORM-OUTAGE",
     [20, 60], [0.01, 0.04], [1500000, 8000000], ["financial", "public_market_harm"],
     [], "managed", "stable", "RISK-PLATFORM-OUTAGE"),
    ("SCN-2026-0014", "Regulated data leaves its required residency region", "NR-DATA-RESIDENCY",
     [10, 18], [0.06, 0.11], [5000000, 9000000], ["regulatory", "individual_harm"],
     [], "managed", "stable", "RISK-DATA-RESIDENCY"),
    ("SCN-2026-0015", "Automated card-testing lands fraudulent charges at checkout", "NR-CARD-TESTING",
     [20, 60], [0.015, 0.05], [800000, 2500000], ["financial", "individual_harm"],
     ["adversarial"], "managed", "stable", "RISK-CARD-TESTING"),
    ("SCN-2026-0016", "Schema-invalid writes corrupt a downstream pipeline decision", "NR-PIPELINE-INTEGRITY",
     [6, 20], [0.02, 0.08], [600000, 2000000], ["financial"],
     [], "managed", "stable", "RISK-PIPELINE-INTEGRITY"),
    # --- New managed scenarios (no legacy bridge) ---
    ("SCN-2026-0017", "Missed quarterly regulatory filing triggers a penalty", "NR-REG-FILINGS",
     [2, 6], [0.05, 0.15], [1000000, 4000000], ["regulatory", "financial"],
     [], "managed", "stable", ""),
    ("SCN-2026-0018", "Subprocessor mishandles regulated data without a governed DPA", "NR-SUBPROCESSOR-GOV",
     [4, 12], [0.03, 0.09], [2000000, 6000000], ["regulatory", "individual_harm"],
     ["third_party"], "managed", "stable", ""),
    ("SCN-2026-0019", "Second admin-console takeover path via unrotated service accounts", "NR-PROD-COMPROMISE",
     [8, 30], [0.006, 0.02], [1500000, 4000000], ["financial", "individual_harm"],
     ["adversarial"], "managed", "stable", ""),
    # --- Emerging scenarios: wide, moving intervals, AI vector (SPEC §4) ---
    ("SCN-2026-0031", "Confidently-wrong automated decisioning at scale on a single model provider", "NR-MODEL-SUPPLY",
     [5, 60], [0.02, 0.30], [500000, 12000000], ["financial", "individual_harm", "public_market_harm"],
     ["ai", "third_party"], "emerging", "rising", ""),
    ("SCN-2026-0032", "Autonomous agent triggers an unsafe production action", "NR-AI-AGENT-AUTONOMY",
     [3, 40], [0.01, 0.25], [400000, 9000000], ["financial", "individual_harm"],
     ["ai"], "emerging", "rising", ""),
    ("SCN-2026-0033", "Silent training-data drift degrades the abuse-detection model", "NR-ABUSE-DETECTION",
     [10, 90], [0.02, 0.28], [300000, 5000000], ["individual_harm", "public_market_harm"],
     ["ai"], "emerging", "rising", ""),
]

# One scenario carries the offline AI incident->scenario mapping seam (SPEC §8,
# §5 story 8), stored as data so the dashboard shows an incident-linked scenario
# as if the pipeline ran. The live generation is Day-3 work; this is the shape.
SCENARIO_INCIDENTS = {
    "SCN-2026-0019": {
        "ticket_id": "INC-2026-0442",
        "description": "Migrated batch workloads authenticated with long-lived service "
                       "accounts that were never rotated; one leaked in a repo and granted "
                       "console-adjacent access before revocation.",
        "suggested_domain": "TR-SECURITY",
        "suggested_named_risk": "NR-PROD-COMPROMISE",
        "suggested_factor": "probability_of_realization",
        "suggested_band": "at appetite",
        "mapped_by": "offline-ai-incident-mapper",
        "mapped_on": "2026-06-10",
        "note": "Synthetic; produced once offline by the corpus generator seam (SPEC §8).",
    }
}

SCENARIO_HEAD = """\
# Tier 3 -- the quantified loss event the Monte Carlo runs on (SPEC §2.4). The
# baseline OF/PoR/LM lives here (it moved down from the legacy risks.yaml). Each
# scenario names its Tier-2 named_risk (many-to-one), carries cross-cutting
# impact + vector tags, and a lifecycle_state (managed | emerging) with a
# trajectory. `legacy_risk`, when present, bridges the migrated exceptions (which
# still name a mapped_risk) to this scenario during graph assembly. All synthetic.
"""


def render_scenario(spec) -> str:
    sid, title, nr, of, por, lm, impact, vectors, lifecycle, trajectory, legacy = spec
    impact_render = "[" + ", ".join(impact) + "]"
    vectors_render = "[" + ", ".join(vectors) + "]" if vectors else "[]"
    lines = [
        SCENARIO_HEAD,
        f"id: {sid}",
        f"title: {title}",
        f"named_risk: {nr}",
        "baseline:",
        f"  opportunity_frequency_90ci: [{of[0]}, {of[1]}]",
        f"  probability_of_realization_90ci: [{por[0]}, {por[1]}]",
        f"  loss_magnitude_90ci: [{lm[0]}, {lm[1]}]",
        f"impact: {impact_render}",
        f"vectors: {vectors_render}",
        f"lifecycle_state: {lifecycle}",
        f"trajectory: {trajectory}",
    ]
    if legacy:
        lines.append(f"legacy_risk: {legacy}")
    incident = SCENARIO_INCIDENTS.get(sid)
    if incident:
        lines.append("incident:")
        for k, v in incident.items():
            if k == "description" or k == "note":
                lines.append(f'  {k}: "{v}"')
            else:
                lines.append(f"  {k}: {v}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7. New issues -- vulns + findings (SPEC §2.5). Exceptions stay under
#    exceptions/ and are read as type: exception.
# ---------------------------------------------------------------------------

VULNS = [
    # (id, title, owner, mapped_scenarios, controls, moves, with_acceptance_90ci,
    #  estimated_by, estimated_on, asset, expires_on, filed_on)
    ("VULN-2026-0001", "Accepted out-of-SLA RCE on a migrated jobs runner",
     "platform-lead@company.com", ["SCN-2026-0001"], ["A.8.8"], "probability_of_realization",
     [0.02, 0.06], "r.chen@company.com", "2026-05-18", "legacy-jobs-runner", "2026-08-15", "2026-05-18"),
    ("VULN-2026-0002", "Unpatched privilege-escalation CVE accepted on endpoint fleet",
     "it-lead@company.com", ["SCN-2026-0012"], ["A.8.8", "A.8.7"], "probability_of_realization",
     [0.03, 0.09], "j.okafor@company.com", "2026-05-22", "corp-endpoint-fleet", "2026-09-30", "2026-05-22"),
    ("VULN-2026-0003", "Deferred dependency patch on the checkout service",
     "payments-lead@company.com", ["SCN-2026-0015"], ["A.8.8"], "probability_of_realization",
     [0.02, 0.055], "p.nguyen@company.com", "2026-06-01", "checkout-service", "2026-08-31", "2026-06-01"),
]

FINDINGS = [
    # (id, title, owner, source, severity, mapped_scenarios, controls, filed_on)
    # A cluster of findings on A.8.5 (secure auth) -> poor control health (SPEC §5.4).
    ("FND-2026-0001", "Audit: legacy consoles permit password-only authentication",
     "security-eng-lead@company.com", "audit", "high", ["SCN-2026-0001"], ["A.8.5"], "2026-04-30"),
    ("FND-2026-0002", "Audit: MFA not enforced on several internal admin tools",
     "security-eng-lead@company.com", "audit", "high", ["SCN-2026-0001"], ["A.8.5"], "2026-05-04"),
    ("FND-2026-0003", "Self-identified: shared break-glass account lacks session logging",
     "iam-lead@company.com", "self-identified", "medium", ["SCN-2026-0001", "SCN-2026-0019"],
     ["A.8.5", "A.8.15"], "2026-05-11"),
    # An incident-PMAI finding feeding the abuse-detection scenario.
    ("FND-2026-0004", "Incident PMAI: detection model retrain slipped two cycles",
     "tns-lead@company.com", "incident-PMAI", "medium", ["SCN-2026-0008"], ["A.8.16"], "2026-05-15"),
    # A DR-readiness finding on the platform-outage scenario (won't-do from a crisis PMAI).
    ("FND-2026-0005", "Incident PMAI: quarterly DR test deferred, failover unproven",
     "platform-lead@company.com", "incident-PMAI", "high", ["SCN-2026-0013"], ["A.5.30"], "2026-05-20"),
]


def render_vuln(spec) -> str:
    (vid, title, owner, scns, controls, moves, ci, est_by, est_on, asset, expires, filed) = spec
    scns_render = "[" + ", ".join(scns) + "]"
    controls_render = "[" + ", ".join(controls) + "]"
    return "\n".join([
        "# An out-of-SLA unpatched vulnerability accepted at the asset level (SPEC",
        "# §2.5). Folds into the mapped scenario's PoR; it moves a factor, so it",
        "# enters the residual bands. Synthetic.",
        f"id: {vid}",
        "type: vuln",
        f"title: {title}",
        f"owner: {owner}",
        f"filed_on: {filed}",
        f"status: active",
        f"mapped_scenarios: {scns_render}",
        f"control: {controls_render}",
        f"moves: {moves}",
        f"with_acceptance_90ci: [{ci[0]}, {ci[1]}]",
        f"estimated_by: {est_by}",
        f"estimated_on: {est_on}",
        f"asset: {asset}",
        f"expires_on: {expires}",
        "",
    ])


def render_finding(spec) -> str:
    (fid, title, owner, source, severity, scns, controls, filed) = spec
    scns_render = "[" + ", ".join(scns) + "]"
    controls_render = "[" + ", ".join(controls) + "]"
    return "\n".join([
        "# An audit / incident-PMAI / self-identified finding (SPEC §2.5). Carries a",
        "# bounded severity that informs control health and the residual NARRATIVE,",
        "# but is NOT simulated -- it never enters the residual bands. Synthetic.",
        f"id: {fid}",
        "type: finding",
        f'title: "{title}"',
        f"owner: {owner}",
        f"filed_on: {filed}",
        f"status: open",
        f"source: {source}",
        f"severity: {severity}",
        f"mapped_scenarios: {scns_render}",
        f"control: {controls_render}",
        "",
    ])


# ---------------------------------------------------------------------------
# 8. Evidence (SPEC §2.8). Data only, no collector. Includes a fresh set, a
#    stale one, and a missing one to exercise the derived status.
# ---------------------------------------------------------------------------

EVIDENCE = [
    # (id, supports_controls, source, method, cadence, last_collected)
    ("EV-IAM-0001", ["A.8.5"], "idp-config-export", "api", "quarterly", "2026-04-15"),
    ("EV-IAM-0002", ["A.8.2", "A.5.18"], "privileged-access-review", "manual", "quarterly", "2026-05-02"),
    ("EV-DLP-0001", ["A.8.12"], "dlp-policy-export", "api", "monthly", "2026-06-01"),
    ("EV-BACKUP-0001", ["A.8.13"], "backup-job-report", "api", "weekly", "2026-06-10"),
    ("EV-VULN-0001", ["A.8.8"], "scanner-export", "api", "weekly", "2026-06-11"),
    ("EV-LOG-0001", ["A.8.15", "A.8.16"], "siem-coverage-report", "api", "monthly", "2026-05-28"),
    ("EV-CRYPTO-0001", ["A.8.24"], "tls-scan", "api", "monthly", "2026-05-30"),
    ("EV-NET-0001", ["A.8.20", "A.8.22"], "firewall-ruleset-export", "api", "quarterly", "2026-03-20"),
    # Stale: a quarterly control last collected far outside its window (SPEC §5.5).
    ("EV-DR-0001", ["A.5.30"], "dr-test-report", "manual", "quarterly", "2025-11-01"),
    # Stale: residency evidence overdue.
    ("EV-RESIDENCY-0001", ["A.8.11", "A.5.34"], "data-residency-audit", "manual", "semiannual", "2025-08-15"),
    # Missing: no last_collected -> status missing.
    ("EV-CHANGE-0001", ["A.8.32"], "change-approval-export", "api", "monthly", None),
    ("EV-SUPPLIER-0001", ["A.5.19", "A.5.20"], "vendor-attestation-register", "manual", "annual", "2026-01-10"),
]

EVIDENCE_HEAD = """\
# Proof a control operates (SPEC §2.8, thin -- DATA ONLY, no collector is built).
# status (fresh | stale | missing) is DERIVED from cadence + last_collected at
# build time. The record shape is the seam a real collector fills later (SPEC §8).
# A representative subset of controls carries evidence; a few are deliberately
# stale or missing to exercise the provability signal (SPEC §5.5). All synthetic.

"""


def render_evidence() -> str:
    out = [EVIDENCE_HEAD]
    for eid, controls, source, method, cadence, last in EVIDENCE:
        controls_render = "[" + ", ".join(controls) + "]"
        block = [
            f"{eid}:",
            f"  supports_controls: {controls_render}",
            f"  source: {source}",
            f"  collection_method: {method}",
            f"  cadence: {cadence}",
        ]
        block.append(f"  last_collected: {last}" if last else "  last_collected: null")
        out.append("\n".join(block) + "\n")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# 9. KRIs (SPEC §2.9). Inform re-estimation; never additive. status derived.
# ---------------------------------------------------------------------------

KRIS = [
    # (id, title, informs, current_value, threshold, trend, direction)
    ("KRI-MODEL-CONCENTRATION", "Share of critical paths dependent on a single model provider",
     ["SCN-2026-0031"], 0.62, 0.50, "rising", "over"),
    ("KRI-AGENTIC-WORKFLOWS", "Count of agentic workflows running in production without guardrails",
     ["SCN-2026-0032"], 7, 3, "rising", "over"),
    ("KRI-DETECTION-DRIFT", "Abuse-detection model recall drift since last retrain (pct pts)",
     ["SCN-2026-0033", "SCN-2026-0008"], 0.09, 0.05, "rising", "over"),
    ("KRI-MFA-COVERAGE", "Share of internal consoles NOT enforcing phishing-resistant MFA",
     ["SCN-2026-0001"], 0.34, 0.15, "rising", "over"),
    ("KRI-PATCH-SLA", "Share of critical vulns patched within SLA",
     ["SCN-2026-0012"], 0.82, 0.90, "receding", "under"),
    ("KRI-DR-CONFIDENCE", "Days since a successful full DR failover test",
     ["SCN-2026-0013"], 220, 120, "rising", "over"),
    ("KRI-RESIDENCY-FLOWS", "Cross-region regulated-data flows per quarter",
     ["SCN-2026-0014"], 14, 10, "rising", "over"),
    ("KRI-FRAUD-RATE", "Card-testing attempts landing a charge per 10k attempts",
     ["SCN-2026-0015"], 3.1, 5.0, "stable", "over"),
    ("KRI-VENDOR-ACCESS", "Count of vendor identities with standing internal access",
     ["SCN-2026-0011"], 41, 30, "rising", "over"),
    ("KRI-CHANGE-FAILURE", "Change-failure rate on migrated services (pct)",
     ["SCN-2026-0009"], 0.11, 0.10, "rising", "over"),
    ("KRI-PIPELINE-REJECTS", "Schema-invalid writes reaching the pipeline per week",
     ["SCN-2026-0016"], 6, 12, "receding", "over"),
    ("KRI-DPA-COVERAGE", "Share of subprocessors without a signed current DPA",
     ["SCN-2026-0018"], 0.18, 0.10, "rising", "over"),
]

KRI_HEAD = """\
# Key risk indicators (SPEC §2.9, thin -- like evidence). A KRI INFORMS
# re-estimation of an existing scenario/named-risk factor (never an additive
# term, SPEC §4) and triggers emerging-risk changes. status (ok | amber |
# breached) is DERIVED from current_value vs threshold; `direction: under` means
# a breach is a value at/below threshold (e.g. patch-SLA coverage). On the
# dashboard a KRI is a light signal on a risk, not its own view. The record shape
# is the seam for later live-metric ingestion (SPEC §8). All synthetic.

"""


def render_kris() -> str:
    out = [KRI_HEAD]
    for kid, title, informs, value, threshold, trend, direction in KRIS:
        informs_render = "[" + ", ".join(informs) + "]"
        out.append(
            f"{kid}:\n"
            f"  title: {title}\n"
            f"  informs: {informs_render}\n"
            f"  current_value: {value}\n"
            f"  threshold: {threshold}\n"
            f"  trend: {trend}\n"
            f"  direction: {direction}\n"
        )
    return "\n".join(out)


# ---------------------------------------------------------------------------
# 10. Horizon -- the emerging watch list at the edge (SPEC §2.10)
# ---------------------------------------------------------------------------

HORIZON = [
    ("HZN-AGENT-AUTONOMY", "Autonomous agents taking unsafe action in production",
     "TR-CHANGE", "KRI-AGENTIC-WORKFLOWS", "rising",
     "agentic workflows moving into prod ahead of guardrails"),
    ("HZN-MODEL-CONCENTRATION", "Systemic dependence on a single external model provider",
     "TR-THIRDPARTY", "KRI-MODEL-CONCENTRATION", "rising",
     "critical paths converging on one provider; no tested fallback"),
    ("HZN-DETECTION-DRIFT", "Silent drift degrading automated abuse detection",
     "TR-SECURITY", "KRI-DETECTION-DRIFT", "rising",
     "recall decaying between retrains; drift not yet alarmed"),
    ("HZN-PROMPT-INJECTION", "Prompt injection against customer-facing LLM features",
     "TR-SECURITY", "KRI-AGENTIC-WORKFLOWS", "stable",
     "injection surface growing as LLM features ship to users"),
]

HORIZON_HEAD = """\
# The emerging watch list at the edge (SPEC §2.10) -- signals too green to write a
# credible scenario yet. Mechanistic-test fence: an item earns a slot ONLY if it
# names both a candidate_domain (where it would manifest) and a watched_kri (its
# leading indicator). No domain and no indicator means it is a news alert, not a
# tracked risk -- validation enforces this. All synthetic.

"""


def render_horizon() -> str:
    out = [HORIZON_HEAD]
    for hid, title, domain, kri, trajectory, note in HORIZON:
        out.append(
            f"{hid}:\n"
            f"  title: {title}\n"
            f"  candidate_domain: {domain}\n"
            f"  watched_kri: {kri}\n"
            f"  trajectory: {trajectory}\n"
            f'  note: "{note}"\n'
        )
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


def build_ecosystem() -> None:
    """Write the v2 GRC-ecosystem corpus files under ``data/``."""
    DATA.mkdir(exist_ok=True)
    SCN.mkdir(exist_ok=True)
    ISSUES.mkdir(exist_ok=True)
    for old in SCN.glob("*.yaml"):
        old.unlink()
    for old in ISSUES.glob("*.yaml"):
        old.unlink()

    (DATA / "enterprise.yaml").write_text(ENTERPRISE)
    (DATA / "domains.yaml").write_text(render_domains())
    (DATA / "policies.yaml").write_text(render_policies())
    (DATA / "controls.yaml").write_text(render_controls())
    (DATA / "named_risks.yaml").write_text(render_named_risks())
    (DATA / "evidence.yaml").write_text(render_evidence())
    (DATA / "kris.yaml").write_text(render_kris())
    (DATA / "horizon.yaml").write_text(render_horizon())

    for spec in SCENARIOS:
        (SCN / f"{spec[0]}.yaml").write_text(render_scenario(spec))
    for spec in VULNS:
        (ISSUES / f"{spec[0]}.yaml").write_text(render_vuln(spec))
    for spec in FINDINGS:
        (ISSUES / f"{spec[0]}.yaml").write_text(render_finding(spec))

    n_scn = len(list(SCN.glob("*.yaml")))
    n_iss = len(list(ISSUES.glob("*.yaml")))
    n_ctrl = sum(len(v) for v in ANNEX_A.values())
    print(f"Wrote {len(DOMAINS)} domains, {len(NAMED_RISKS)} named risks, {n_scn} scenarios")
    print(f"Wrote {n_ctrl} ISO Annex A controls, {len(POLICIES)} policies, {len(EVIDENCE)} evidence records")
    print(f"Wrote {len(KRIS)} KRIs, {len(HORIZON)} horizon items, {n_iss} new issues (vulns + findings)")


if __name__ == "__main__":
    build_ecosystem()
