# tria_engine/apps/eisf/structure.py
#
# Canonical eISF folder/category taxonomy (the regulatory binder structure).
#
# This mirrors the frontend sidebar exactly — src/shared/pages/EISF/Constants/
# EISFMenuConfig.ts (module id "1.0".."22.0" + numbered sub-sections), so the
# backend repository and the UI tree can never drift apart. New sections in
# the UI must be added here (and to the frontend isfFolderStructure.ts
# constant) at the same time.

from __future__ import annotations

EISF_STRUCTURE: list[dict] = [
    {
        "id": "1.0",
        "title": "Participating Site Team",
        "path": "/eisf/participating-site-team",
        "children": [
            {"id": "1.1", "title": "Contact List"},
            {"id": "1.2", "title": "Signature & Delegation Log"},
            {"id": "1.3", "title": "CVs"},
            {"id": "1.4", "title": "GCP Training Certificates"},
            {"id": "1.5", "title": "EDC Training Certifications"},
            {"id": "1.6", "title": "Other Training Certificates"},
        ],
    },
    {
        "id": "2.0",
        "title": "Project Management",
        "path": "/eisf/project-management",
        "children": [
            {"id": "2.1", "title": "Reserved (No Site Documents)"},
            {"id": "2.2", "title": "Team Communication"},
        ],
    },
    {
        "id": "3.0",
        "title": "Protocol / Protocol Amendments",
        "path": "/eisf/protocol",
        "children": [
            {"id": "3.1", "title": "Site Protocol Version Tracker"},
            {"id": "3.2", "title": "Current Approved Study Protocol"},
            {"id": "3.3", "title": "Superseded Study Protocols"},
            {"id": "3.4", "title": "Local Site Non-Compliance Log"},
            {"id": "3.5", "title": "Non-Compliance Reports"},
            {"id": "3.6", "title": "Serious Breaches & CAPA"},
            {"id": "3.7", "title": "Serious Breach Reports"},
            {"id": "3.8", "title": "Related Correspondence"},
        ],
    },
    {
        "id": "4.0",
        "title": "Participant Information & Consent",
        "path": "/eisf/participant-consent",
        "children": [
            {"id": "4.1", "title": "PGICF & PICF Version Tracker"},
            {"id": "4.2", "title": "Current PGICF & PICFs"},
            {"id": "4.3", "title": "Other Approved Participant Information"},
            {"id": "4.4", "title": "Superseded PGICF & PICFs"},
            {"id": "4.5", "title": "Superseded Participant Information"},
            {"id": "4.6", "title": "Signed PGICF & PICFs"},
        ],
    },
    {
        "id": "5.0",
        "title": "Regulatory",
        "path": "/eisf/regulatory",
        "children": [
            {"id": "5.1", "title": "Regulatory Authorisation"},
            {"id": "5.2", "title": "Supplementary Documents"},
            {"id": "5.3", "title": "Reserved"},
        ],
    },
    {
        "id": "6.0",
        "title": "Ethics",
        "path": "/eisf/ethics",
        "children": [
            {"id": "6.1", "title": "Ethics Approval Letters"},
            {"id": "6.2", "title": "Ethics Submission Documents"},
            {"id": "6.3", "title": "Committee Composition & Compliance"},
            {"id": "6.4", "title": "Annual / Final Reports"},
            {"id": "6.5", "title": "Related Correspondence"},
        ],
    },
    {
        "id": "7.0",
        "title": "Research Governance Office (RGO)",
        "path": "/eisf/research-governance",
        "children": [
            {"id": "7.1", "title": "Governance Authorisation Letters"},
            {"id": "7.2", "title": "RGO Submission Documentation"},
            {"id": "7.3", "title": "Annual Project Progress Reports & Final Project Report"},
            {"id": "7.4", "title": "Related Correspondence"},
        ],
    },
    {
        "id": "8.0",
        "title": "Study-Specific Procedures / SOPs",
        "path": "/eisf/sop",
        "children": [
            {"id": "8.1", "title": "Current Manual of Procedures / SOPs"},
            {"id": "8.2", "title": "Superseded Manual of Procedures / SOPs"},
        ],
    },
    {
        "id": "9.0",
        "title": "Site Initiation",
        "path": "/eisf/site-initiation",
        "children": [
            {"id": "9.1", "title": "Site Initiation Meeting Documentation"},
            {"id": "9.2", "title": "Site Initiation Follow Up Letter"},
            {"id": "9.3", "title": "Site Activation Documentation / Letter"},
        ],
    },
    {
        "id": "10.0",
        "title": "Site Training",
        "path": "/eisf/site-training",
        "children": [
            {"id": "10.1", "title": "Investigator Meetings"},
            {"id": "10.2", "title": "Other Presentations"},
            {"id": "10.3", "title": "Site-Specific Training Log"},
            {"id": "10.4", "title": "Other Training Resources"},
        ],
    },
    {
        "id": "11.0",
        "title": "Participant Recruitment",
        "path": "/eisf/recruitment",
        "children": [
            {"id": "11.1", "title": "Pre-Screening Log"},
            {"id": "11.2", "title": "Consent, Screening & Enrolment Log"},
            {"id": "11.3", "title": "Participant ID Log"},
            {"id": "11.4", "title": "Related Correspondence"},
        ],
    },
    {
        "id": "12.0",
        "title": "Participant Randomisation / Registration Procedures",
        "path": "/eisf/randomization",
        "children": [
            {"id": "12.1", "title": "Randomisation / Registration User Manual"},
            {"id": "12.2", "title": "Records of Unblinding"},
            {"id": "12.3", "title": "Related Correspondence"},
        ],
    },
    {
        "id": "13.0",
        "title": "Data Management",
        "path": "/eisf/data-management",
        "children": [
            {"id": "13.1", "title": "Blank Paper CRF"},
            {"id": "13.2", "title": "CRF Completion Guidelines"},
            {"id": "13.3", "title": "Completed EDC System Account Application Forms"},
            {"id": "13.4", "title": "Source Document Plan"},
            {"id": "13.5", "title": "Related Correspondence"},
        ],
    },
    {
        "id": "14.0",
        "title": "Safety Monitoring & Reporting",
        "path": "/eisf/safety",
        "children": [
            {"id": "14.1", "title": "Blank Expedited Safety Report Forms"},
            {"id": "14.2", "title": "Reference Safety Information"},
            {"id": "14.3", "title": "Completed Expedited Safety Report Forms"},
            {"id": "14.4", "title": "Safety Reports to RGO / Regulatory Authority"},
            {"id": "14.5", "title": "On-Site Unblinding Procedures"},
            {"id": "14.6", "title": "Related Correspondence"},
        ],
    },
    {
        "id": "15.0",
        "title": "Study Quality Assurance, Monitoring, Audits & Inspections",
        "path": "/eisf/monitoring",
        "children": [
            {"id": "15.1", "title": "Reserved - Sponsor/CPI Maintained"},
            {"id": "15.2", "title": "Site Monitoring Log"},
            {"id": "15.3", "title": "Reserved - Sponsor/CPI Maintained"},
            {"id": "15.4", "title": "Monitoring Visit Correspondence and Feedback"},
            {"id": "15.5", "title": "Trial Close-Out"},
            {"id": "15.6", "title": "Local Research Governance Audit Reports and Correspondence"},
            {"id": "15.7", "title": "Regulatory Inspections Reports and Correspondence"},
        ],
    },
    {
        "id": "16.0",
        "title": "Local Laboratory Documentation",
        "path": "/eisf/laboratory",
        "children": [
            {"id": "16.1", "title": "Research Sample Lab Manual"},
            {"id": "16.2", "title": "Local Lab Certificates of Accreditation"},
            {"id": "16.3", "title": "Normal Local Lab Reference Ranges"},
            {"id": "16.4", "title": "Biospecimen Collection Log"},
            {"id": "16.5", "title": "Biospecimen Shipment Receipt Tracking"},
            {"id": "16.6", "title": "Biospecimen Storage Monitoring Documentation"},
            {"id": "16.7", "title": "Related Correspondence"},
        ],
    },
    {
        "id": "17.0",
        "title": "Supplies / Shipping Records",
        "path": "/eisf/supplies",
        "children": [
            {"id": "17.1", "title": "Documentation Relating to Provision of Study Supplies"},
        ],
    },
    {
        "id": "18.0",
        "title": "Legal Documentation",
        "path": "/eisf/legal",
        "children": [
            {"id": "18.1", "title": "Clinical Trial Agreement"},
            {"id": "18.2", "title": "Other Agreements"},
            {"id": "18.3", "title": "Related Correspondence"},
        ],
    },
    {
        "id": "19.0",
        "title": "Finance Documentation",
        "path": "/eisf/finance",
        "children": [
            {"id": "19.1", "title": "Invoices / Receipts"},
            {"id": "19.2", "title": "Related Correspondence"},
        ],
    },
    {
        "id": "20.0",
        "title": "Other Communication",
        "path": "/eisf/other-communication",
        "children": [
            {"id": "20.1", "title": "Newsletters from Sponsor"},
            {"id": "20.2", "title": "General Correspondence"},
        ],
    },
    {
        "id": "21.0",
        "title": "Archiving",
        "path": "/eisf/archiving",
        "children": [
            {"id": "21.1", "title": "Archiving Details"},
            {"id": "21.2", "title": "Related Correspondence"},
        ],
    },
    {
        "id": "22.0",
        "title": "Investigational Product",
        "path": "/eisf/investigational-product",
        "children": [
            {"id": "22.1", "title": "Instructions for Handling IP"},
            {"id": "22.2", "title": "Documentation of IP Shipment"},
            {"id": "22.3", "title": "Documentation of IP Dispensing, Accountability & Inventory"},
            {"id": "22.4", "title": "Documentation of IP Storage Monitoring"},
            {"id": "22.5", "title": "Documentation of IP Quarantine / Returns / Destruction"},
            {"id": "22.6", "title": "Related Correspondence"},
        ],
    },
]

# Canonical document lifecycle statuses (mirrors the frontend
# DOCUMENT_STATUS constants — same tokens, same spelling).
EISF_DOCUMENT_STATUSES = [
    "Draft",
    "Pending",
    "Under Review",
    "Under Approval",
    "Approved",
    "Rejected",
    "Superseded",
    "Expired",
    "Archived",
    "Missing",
]

# Statuses that end a document's active lifecycle (no further transitions
# except through a replacement version).
EISF_FINAL_STATUSES = {"Approved", "Archived", "Superseded", "Expired"}


def section_by_id(section_id: str) -> dict | None:
    for section in EISF_STRUCTURE:
        if str(section.get("id")) == str(section_id):
            return section
    return None


def folder_by_id(folder_id: str) -> dict | None:
    for section in EISF_STRUCTURE:
        for child in section.get("children") or []:
            if str(child.get("id")) == str(folder_id):
                return dict(child, parent=section)
    return None