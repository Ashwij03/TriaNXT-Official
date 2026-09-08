# Migration Plan — V2 Schema (87 orphaned SQL-package tables)

> Status: **PLAN ONLY** — no schema or code changes are authorized by this
> document. It exists to triage the gap-closure work for the fully-normalized,
> plural-named "v2" tables that the authoritative SQL package
> (`New TriaNXT/Sql/`) already defines but no backend model or route touches.
>
> Companion documents:
> - `POSTGRES_CONNECTION.md` — the SQL package, not Alembic, is the
>   authoritative schema source for the target database.
> - `docs/gap-closure-changelog.md` — what this plan's phase-1 items that were
>   already picked up (e.g. eTMF wiring, signature requests, reference data)
>   look like once implemented.
>
> Numbers below were re-derived from the actual package on 2026-09-08:
> 131 `CREATE TABLE` statements across the 11 numbered files, 46 tables have a
> SQLAlchemy model (`__tablename__`), leaving **85 orphaned tables** (the
> original audit estimated 87 — the delta is measurement noise: two of the
> audit's "orphaned" tables gained models as part of P0.1/P1.x work).

## 0. Framing

Two naming families coexist in the package today:

- **Singular JSON-mirror tables** (`ctms_subject`, `ctms_visit`, `ctms_amendment`,
  `ctms_vendor`, `ctms_icfversion`, …) — wired end-to-end through the FastAPI
  "gap-module" routers. One row per frontend record, full payload in `data
  JSONB`, study/site codes promoted to indexed scope columns. These are the
  **production path today**.
- **Plural fully-normalized "v2" tables** (`ctms_subjects`, `ctms_visits`,
  `ctms_amendments`, `ctms_vendors`, `ctms_icf_versions`, …) — rich typed
  columns, proper FKs, no JSON blob. **Zero backend/frontend wiring today.**

The decision in §2 (coexist vs. migrate) gates how much of the v2 family we
eventually build routers for. Everything below is written so that the two
families can coexist indefinitely (the "v2 as read-only reporting layer" path)
or converge (the "v2 as the new source of truth" path).

## 1. Prioritization — which tables first

Ordered by how much real user pain each domain currently has (all of the
frontend services below are pure-localStorage today and have a plausible home
in these tables):

### Phase 1 (highest value — partially started, see changelog)
| Domain | Orphaned tables | Frontend consumer(s) today | Why first |
|---|---|---|---|
| eTMF | `ctms_etmf_zones`, `ctms_etmf_documents`, `ctms_etmf_completeness_requirements` | `EtmfCenter` (renders `EISFDashboard`), dead `etmfApi.ts` | Full eTMF module exists in UI with no backend; P0.2/P1.2 already chose to remove the dead API stub; wiring these tables is the natural next step |
| Signature workflow | `ctms_signature_requests`, `ctms_signature_request_signers` | `actionSignatureService.ts` ledger (3.3) | Multi-signer "Send for Signature" is a named feature gap (Section 5.3); models/routes landed in the current pass |
| Reference/lookup data | `permissions`, `role_permissions`, `user_roles`, `countries`, `currencies`, `timezones`, `study_status`, `site_status`, `visit_types`, `activity_types`, `document_types`, `issue_types`, `severity_levels`, `system_configurations`, `notification_templates` | Hard-coded constants (`VISIT_STAGES` etc.) | Cheap, high-leverage: a `referenceDataService` replaces dozens of hard-coded enum arrays; RBAC lookups feed the accounts module |

### Phase 2 (feature-gap tables from Sections 5.1/5.2/5.4/5.9)
| Domain | Orphaned tables | Frontend consumer(s) today |
|---|---|---|
| Core trial hierarchy (5.1) | `ctms_studies`, `ctms_sites`, `ctms_investigators`, `ctms_protocols`, `ctms_study_milestones`, `ctms_study_team_members`, `ctms_study_versions`, `ctms_study_tasks`, `ctms_site_staff`, `ctms_site_contacts`, `ctms_site_budgets` | `studyService.ts`, `Sites`/`SiteManagement` screens |
| Documents (5.2) | `ctms_documents`, `ctms_document_folders`, `ctms_document_versions`, `ctms_document_approvals`, `ctms_document_extractions`, `ctms_document_audit_trail` | `folderService.ts`, `DocumentFolderManager.tsx`, `SubjectFileManager` (file records) |
| Financials (5.4) | `ctms_budgets`, `ctms_site_budgets`, `ctms_payments`, `ctms_invoices`, `ctms_receivables`, `ctms_subject_costs` | `financialService.ts` |
| Monitoring (5.6) | `ctms_monitoring_visits`, `ctms_monitoring_findings` | `router_monitoring.py` requests → visits/findings once fulfilled |
| Issues/CAPA (5.7) | `ctms_issues`, `ctms_action_items`, `ctms_capa_actions`, `ctms_regulatory_checklist_items` | Governance pages (forward-looking) |
| Vendors (5.8) | `ctms_vendor_contracts`, `ctms_vendor_kits` | `vendorService.ts` |
| Comms/reporting (5.9) | `ctms_notifications`, `ctms_comments`, `ctms_progress_notes`, `ctms_reports`, `ctms_report_schedules` | `notificationService.ts`, `commentService.ts`, `reportService.ts`, `adminService.ts` |
| Re-consent (5.10) | `ctms_reconsent_campaigns`, `ctms_reconsent_subjects`, `ctms_consent_events`, `ctms_icf_versions` | `icfConsentService.ts` |

### Phase 3 (forward-looking / AI)
`ctms_ai_conversations`, `ctms_ai_messages`, `ctms_ai_findings`,
`ctms_risk_rules`, `ctms_risk_events`, `ctms_audit_events`,
`ctms_access_requests`, `ctms_adverse_events`, `ctms_visit_plans`,
`ctms_visit_plan_*`, `ctms_visit_activities`, `ctms_ip_shipments`,
`ctms_ip_excursions`, `ctms_ip_transactions`, `ctms_ip_lots`,
`ctms_amendment_site_tasks`, `ctms_amendments`, `ctms_feasibility_candidates`,
`ctms_feasibility_scoring`, `ctms_irb_submissions`, `ctms_monitoring_access_requests`.

## 2. Naming-family decision (needs a product/architecture owner)

**Do not resolve unilaterally.** Two defensible end states:

- **(A) Coexist permanently** — singular JSON-mirror tables stay the write path
  (they are byte-faithful to the frontend localStorage records and already
  RBAC/scope-wired); plural v2 tables become a read-only reporting/analytics
  layer populated by an idempotent projector. Cheapest; keeps every existing
  integration intact.
- **(B) Converge on v2** — eventually migrate `ctms_subject` → `ctms_subjects`,
  `ctms_visit` → `ctms_visits`, etc., with a data backfill and router rewrites.
  Cleanest schema, most engineering.

Recommendation to take to the owner: start with (A); revisit (B) only if the
JSON-mirror tables demonstrably hurt reporting or referential integrity.
Sections 5.1/5.2/5.4/5.9/5.11 of the gap-closure brief propose *new singular
tables* that in almost every case already have a plural v2 counterpart in the
package (e.g. `ctms_document` vs `ctms_documents`, `ctms_notification` vs
`ctms_notifications`, `permission` vs `permissions`). Per the naming-conflict
rule, the resolved stance is: **wire/extend the existing plural tables; do not
create parallel singular families.**

## 3. Phase-1 endpoint inventory (rough)

| Router | Prefix | Endpoints |
|---|---|---|
| `apps/ctms/router_etmf.py` (new) | `/etmf` | `GET /zones/`, `GET /documents/?studyId=`, `GET /documents/{id}/`, `POST /documents/`, `PATCH /documents/{id}/`, `DELETE /documents/{id}/`, `GET /documents/completeness/?studyId=` |
| `apps/ctms/router_signature.py` (new, in this pass) | `/api/signature-requests` | `GET /`, `POST /`, `POST /{id}/signers`, `PATCH /signers/{id}`, plus `POST /api/audit/signatures` ledger |
| `apps/ctms/router_reference.py` (new, in this pass) | `/api/reference-data` | `GET /countries`, `GET /currencies`, `GET /timezones`, `GET /statuses`, `GET /types`, `GET /configurations`, `GET /notification-templates`, `GET /permissions` |
| Frontend services | — | `etmfApi.ts` (revived against the new router), `referenceDataService.ts`, `signatureRequestService.ts` (future), dual-mode with localStorage fallback per the standard pattern |

## 4. Per-domain notes (reconciliation with Sections 5.x)

- **5.1 / 5.2 / 5.4 / 5.9 / 5.11**: see §2 — prefer the existing plural v2
  tables over the brief's singular names.
- **5.3**: `ctms_signature_requests`/`ctms_signature_request_signers` exist and
  were wired in the current pass (models + migration + router). They reference
  `ctms_documents(document_id)` NOT NULL — a "Send for Signature" UI must
  therefore target general document records; eISF-document signing uses the
  single-signer `ctms_electronic_signature` table (Section 4.1).
- **5.6**: `ctms_monitoringrequest` (singular, wired) is the *request*; the v2
  `ctms_monitoring_visits`/`ctms_monitoring_findings` tables are the fulfilled
  visit + findings. Both should coexist (request → visit lifecycle).
- **P0.1**: the 9 governance/eISF tables were added to the SQL package as
  `10_1_eisf_and_governance_tables.sql` (JSON-mirror shape, matching their
  models); they are intentionally NOT folded into the v2 family.
- **`ctms_electronic_signatures` (plural, orphaned)**: the Section 4.1 work
  created the singular `ctms_electronic_signature` (matching its SQLAlchemy
  model). These two tables overlap; when v2 converges, fold the singular into
  the plural or drop the plural — flagged for the owner, not resolved here.

## 5. Out of scope for this document

Actual models/routes/migrations for phases 2–3, backfills, projectors, and the
naming-family decision itself.