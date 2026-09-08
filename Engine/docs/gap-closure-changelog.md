# Gap-Closure Changelog

One line per file added or modified by the combined implementation pass
(Feature gaps: Sections 3–5; Integration gaps: Section 8 P0–P3). Backend
repo root is `New TriaNXT/Engine/`; frontend is `New TriaNXT/UI/`; the
authoritative SQL package is `New TriaNXT/Sql/`.

## SQL package (`New TriaNXT/Sql/`)

- **added `10_1_eisf_and_governance_tables.sql`** — P0.1: ports the 9 backend-model tables
  missing from the package (`eisf_document`, `eisf_documentversion`, `ctms_complianceconfig`,
  `ctms_deviation`, `ctms_capa`, `ctms_auditevent`, `ctms_riskrule`, `ctms_riskscore`,
  `ctms_riskevent`) from Alembic revision `e7c4b2a1d9f8`, as idempotent
  `CREATE TABLE IF NOT EXISTS` statements with matching indexes.
- **added `10_2_electronic_signature.sql`** — Section 4.1: the singular
  `ctms_electronic_signature` ledger table (the multi-signer
  `ctms_signature_requests`/`ctms_signature_request_signers` already existed in
  `03_operations_governance.sql` and were wired, not recreated).
- **modified `run_all.sql`** — includes the two new files in order (after `10_missing_tables_alignment.sql`).
- **modified `09_validate.sql`** — row-count UNION now covers the 12 new tables.

Verified against a scratch PostgreSQL 18 database: full package runs with
`ON_ERROR_STOP=1`, 132 tables created (122 original + 9 + 1), validator runs.

## Backend (`Engine/`)

- **deleted `Engine/src/`** — P2.1: confirmed nothing in the deploy pipeline
  builds/serves it (`.dockerignore` explicitly excludes `src/`; `Dockerfile`
  copies backend-only); removed the stale duplicate frontend copy.
- **modified `Engine/README.md`** — P2.1: notes `New TriaNXT/UI/` is the single
  source of truth for frontend source; `src/` must not be recreated here.
- **added `Engine/MIGRATION_PLAN_V2_SCHEMA.md`** — P2.2: plan-only document for
  the 85 orphaned v2 tables (prioritization, naming-family decision, phase-1
  endpoint inventory, cross-references to Sections 5.1/5.2/5.4/5.9/5.11).
- **added `alembic/versions/9a3f7c2e5b10_electronic_signatures_and_requests.py`** —
  new migration creating `ctms_electronic_signature` (Section 4.1) and the
  plural signature-request tables (Section 5.3); verified `upgrade head` /
  `downgrade -1` on a fresh DB.
- **modified `apps/eisf/models.py`** — added the `ESignature` model
  (`ctms_electronic_signature`, Part 11 ledger row).
- **modified `apps/eisf/services.py`** — added `sha256_hex`, `_canonical_json`
  (byte-for-byte contract with the frontend `canonicalJson`),
  `build_signature_stamp`, `sign_document` (client stamp verified against the
  server recomputation; 400 on mismatch), `list_signatures`,
  `verify_document_integrity` (content SHA-256, recorded at write time),
  `store_document_file`/`_content_bytes` (shared media storage),
  `basename_for_download`, and HMAC-signed short-lived download tokens
  (`_sign_token`/`issue_download_token`/`resolve_download_token`); also a
  minimal targeted fix of a latent crash in `_build_record` (`existing.get()`
  on `None` on the create path when `fileSize` is absent) that blocked the new
  endpoints and P1.2.
- **modified `apps/eisf/router.py`** — added `POST /documents/{code}/sign`,
  `GET /documents/{code}/signatures`, `GET /documents/{code}/verify-integrity`,
  `GET /documents/{code}/download-token`, `GET /documents/{code}/download`
  (403 on invalid/expired token), same auth/dependency pattern as existing routes.
- **modified `apps/ctms/models.py`** — added `CtmsSignatureRequest` /
  `CtmsSignatureRequestSigner` mapping the existing plural SQL-package tables
  (document_id/study_id as plain typed columns because `ctms_documents` /
  `ctms_studies` have no ORM model yet; the package's FKs stay authoritative).
- **added `apps/ctms/router_signature.py`** — `POST /api/audit/signatures`
  (append-only signature ledger, the fail-soft mirror the frontend `signEntity`
  POSTs to) + `/api/signature-requests` list/create/detail/sign lifecycle.
- **added `apps/billing/router.py`** — P1.1: the six endpoints the frontend
  planCatalogService/subscriptionService call (`/billing/plans/*`,
  `/billing/subscription/me|assign|checkout|confirm`), backed by the existing
  billing models; deterministic mock gateway (checkout creates a
  `PaymentTransaction`, confirm verifies + applies the plan).
- **modified `apps/accounts/rbac.py`** — added the `billing` module
  (Admin-only create/update/delete) to the permission matrix.
- **modified `main.py`** — mounted the signature router, audit-signatures
  router and billing router.
- **added `tests/test_billing_api.py`** — plan CRUD/409s/RBAC, subscription
  assign/patch, checkout/confirm lifecycle.
- **added `tests/test_signature_integrity.py`** — eISF sign with valid/mismatch
  stamp, integrity verify (tamper detection), signed download tokens, audit
  ledger, signature-request lifecycle.

## Frontend (`UI/`)

- **added `src/shared/pages/Unauthorized.tsx` + `Unauthorized.css`** — Section 3.1: 403 page
  at `/unauthorized` and `/forbidden` (attempted path via route state, Return to
  Dashboard, Request Access).
- **added `src/shared/routes/GuardedRoute.tsx`** — Section 3.1: additive guard
  (login → role → requiredPermission → per-study scope) + `StudyRouteGuard`
  adapter; existing `ProtectedRoute`/`PermissionRoute` untouched.
- **modified `src/shared/auth/ProtectedRoute.tsx`** — Section 3.1: silent
  dashboard redirects for denied users now go to `/unauthorized` with the
  attempted path; no other logic changed.
- **modified `src/App.tsx`** — added the two 403 routes and wrapped
  `/study-dashboard/:id` with `StudyRouteGuard`.
- **modified `src/shared/services/actionSignatureService.ts`** — Section 3.3:
  added `SIGNATURE_MEANINGS` taxonomy, `defaultMeaningForAction`,
  `confirmLabelForAction`, `canonicalJson`, `sha256Hex`, `buildActionStamp`,
  `createActionSignature`, `getSignerIdentity`, `formatSignatureStamp/Time`,
  `attachSignatureToRecord`, `getSignatureLedgerEntries`,
  `recordSignatureLedgerEntry`; `signEntity` now sends `meaning` + the real
  SHA-256 stamp to `/api/audit/signatures`; every existing export unchanged.
- **modified `src/shared/components/ESignatureModal.tsx` + `.css`** — meaning
  picker (radio group), awaited `createActionSignature` so the stamp is a real
  SHA-256 digest, per-action confirm label.
- **added `src/shared/config/demoUsers.ts`** — Section 3.4.1: one demo account
  per role. Note: the spec claimed `adminService.ts` already imports/calls a
  `seedDemoDirectoryUsers()`; verified it does not exist in this codebase, so
  the file is supplied as specified with no consumer (recorded under
  "Observed but out of scope").
- **added `src/shared/pages/EISF/Constants/isfFolderStructure.ts`** — Section 3.4.2:
  canonical zone/folder structure built from `EISFMenuConfig`; `EISFDashboard`
  now imports through it.
- **added `src/shared/services/api/eisfApi.ts`** — P1.2: CRUD + sign /
  verify-integrity / download-token client for `/api/eisf/*`.
- **modified `src/shared/services/api/index.ts`** — export `eisfApi` (replacing
  the removed `etmfApi`).
- **modified `src/shared/pages/EISF/services/documentService.ts`** — P1.2:
  `persistModuleDocuments` best-effort diff-syncs to `/api/eisf/*` in API mode
  (localStorage stays the fallback); added `syncDocumentsToApi`,
  `refreshModuleDocumentsFromApi`, `toApiDocument`.
- **modified `src/shared/pages/EISF/EISFModuleWorkspace.tsx`** — P1.2: on mount,
  pull module documents from the API when enabled (fail-soft).
- **deleted `src/shared/services/api/etmfApi.ts`** — P0.2 (Option B): dead code
  (no page imports it; no `/etmf` backend router exists).
- **modified `src/shared/services/api/client.ts`** — P0.2 (Option B): removed
  the dead `uploadFileToS3`/`getDownloadUrl` presign helpers with a comment
  pointing at the live upload path (`/api/accounts/documents/upload/` and
  `/api/eisf/documents`).
- **modified `src/shared/services/api/aiReviewApi.ts`** — P3.1: documents that
  `reviewDocument`/`triageComment`/`decideFinding` are intentionally dormant
  pending UI design (backend endpoints stay).
- **added `src/shared/components/SubjectExplorer/ConsentStatusBadge.tsx`** —
  Section 3.2.1: consent badge + `useSubjectConsentStatus` hook over
  `getSubjectConsentStatus()`.
- **added `src/shared/components/SubjectExplorer/SubjectProfilePanel.tsx` +
  `SubjectProfile.css`** — Section 3.2.2: collapsible profile panel (identity
  fields, consent badge, timeline via `subjectTimeline.ts`, inline
  `SubjectComments`).
- **added `src/shared/components/subjects/SubjectFolderUpload.tsx` +
  `SubjectFolderUpload.css` + `folderUploadUtils.ts`** — Section 3.2.3: bulk
  folder upload (webkitdirectory picker, pure walk/group/validate helpers
  reusing `FileService.validateUploadCandidate`).
- **added `src/shared/components/SubjectExplorer/subjectIcfSyncService.ts`** —
  Section 3.2.4: ICF-folder detection + bidirectional mirror with
  `icfConsentService` (best-effort `/api/site/icf/versions` POST in API mode).
- **modified `src/shared/components/SubjectExplorer/StudySubjectsWorkspace.tsx`
  + `.css`** — "Profile" action + side panel for the selected subject.
- **modified `src/shared/components/SubjectExplorer/SubjectFileManager.tsx`** —
  "Upload Folder" toolbar action (one signature per batch; nested folders
  created via `FolderTreeService.createFolder`) + ICF-mirror effect on load and
  file changes inside an ICF folder.
- **modified `src/shared/components/SubjectExplorer/subjectTimeline.ts`** —
  minimal import repair: `getSchedules` comes from `adminService.ts` (the
  visit-schedule store), not `visitScheduleService.ts`; this was a pre-existing
  broken import that failed `tsc`.
- **added tests** `src/shared/services/__tests__/actionSignatureIntegrity.test.ts`,
  `src/shared/components/subjects/__tests__/folderUploadUtils.test.ts`,
  `src/shared/components/SubjectExplorer/__tests__/subjectIcfSyncService.test.ts`
  (22 tests, all passing).

## Observed but out of scope (triaged, not fixed)

- 9 legacy frontend test files (22 tests: planCatalog, subscriptionService,
  subscriptionGuard, SubscriptionContext, subscriptionFormat, PaymentModal,
  PlanPickerModal, referralService, folderTreeService) fail with
  `ReferenceError: jest is not defined` — they were written for the CRA/jest
  global API, which vitest does not inject. Pre-existing; unrelated to this
  pass (an attempted `vi` alias shim made the suite worse because vitest does
  not hoist `jest.mock` like `vi.mock`).
- `Engine/staticfiles/{admin,drf-yasg,rest_framework}` are stale Django/DRF-era
  assets; nothing serves them (FastAPI-only today). Left untouched.
- `Engine/build/`, `Engine/*.sqlite3`, `UI/build/`, `UI/dist/`,
  `UI/conflicts.txt`, root `_*.log` files: build artifacts/logs, untouched.
- `src/shared/config/demoUsers.ts` has no consumer yet — the claimed
  `seedDemoDirectoryUsers()` in `adminService.ts` does not exist in this
  codebase (see above).
- `ctms_electronic_signatures` (plural, orphaned in the SQL package) overlaps
  the new singular `ctms_electronic_signature`; reconciliation deferred to the
  v2 migration plan (see `MIGRATION_PLAN_V2_SCHEMA.md` §4).
- Section 5 tables not wired in this pass (documented in the migration plan):
  core hierarchy (5.1), general document store (5.2), financials (5.4), IP
  logistics (5.5), monitoring visits/findings (5.6), issues/CAPA (5.7), vendor
  contracts/kits (5.8), notifications/comments/reports (5.9), re-consent (5.10),
  reference/RBAC lookup tables (5.11). The plural v2 counterparts of all of
  these already exist in the SQL package; per the naming-conflict rule they
  should be wired, not duplicated (see `MIGRATION_PLAN_V2_SCHEMA.md` §1–2).
- ~~A full "Send for Signature" multi-signer UI does not yet exist~~ —
  RESOLVED by the follow-up pass below (Signature Requests workspace). The
  backend workflow (Section 5.3) and the workspace are complete, tested, and
  live-verified end-to-end against Postgres.
- The reference-data refactor of hard-coded enum arrays (`VISIT_STAGES` etc.)
  via a `referenceDataService` is follow-up (Section 5.11).

## Follow-up pass — Signature Requests workspace (Section 5.3 UI)

- **added `UI/src/shared/services/signatureRequestService.ts`** — dual-mode
  service for the workspace: list/create/sign against
  `/api/signature-requests` (and `/api/signature-requests/{id}/sign`) with a
  localStorage mirror when the API is unreachable; `fetchDirectoryUsers`
  (backend `/api/accounts/users/` in API mode, local `users` store offline);
  `currentUserCanSign` / `requestStatusLabel` / `signerProgress` UI helpers;
  `SIGNATURE_REQUESTS_EVENT` change event.
- **added `UI/src/shared/pages/signatures/SignatureRequests.tsx` + `.css`** —
  the workspace: KPI cards (total / awaiting-my-signature / completed), status
  tabs, searchable/filterable request table with signer chips, create modal
  (numeric document id + optional study id via datalist candidates, multi-
  signer directory picker, Save Draft / Create & Send), detail modal with
  per-signer meaning / timestamp / SHA-256 stamp, and the Sign action that
  drives the app-wide `ESignatureModal` (`openSignature` without an actionKey
  so the sign endpoint — not `signEntity` — is the ledger writer).
- **modified `UI/src/App.tsx`** — registered `/signature-requests` under
  `ProtectedRoute` gated to the backend `eisf:sign` roles (Admin, SiteStaff,
  PI, Sponsor).
- **modified `UI/src/shared/services/roleService.ts`** — added
  `/signature-requests` to the `ROUTE_ACCESS` matrix with the same four roles.
- **modified `UI/src/shared/components/dashboard/shared/DashboardSidebar.tsx`** —
  added the "Signature Requests" entry (FiCheckSquare) next to Audit Logs,
  gated to Admin/SiteStaff/PI/Sponsor.
- **added `UI/src/shared/services/__tests__/signatureRequestService.test.ts`** —
  16 tests: normalization (backend snake_case -> UI shape), status/progress
  helpers, signer-can-sign gating, API-mode create/sign/list payload contracts,
  backend-rejection surfacing, and the offline localStorage mirror incl. the
  two-signer completion transition.
- **modified `Engine/tria_engine/apps/ctms/router_signature.py`** — create now
  wraps flush+commit in `IntegrityError` handling and returns a clean 400
  ("The referenced document, study or signer does not exist.") instead of a
  raw 500 when the SQL package's FK to `ctms_documents`/`ctms_studies`/
  `accounts_user` rejects the payload.

Live end-to-end verification against Postgres (scratch DB loaded from
`Sql/run_all.sql`, seeded `ctms_documents` row): register two users, create a
SENT request for both signers, unknown-document create -> clean 400, sign as
PI -> SENT with one signer complete, sign as Sponsor -> COMPLETED, non-signer
sign -> 403 "You are not a signer on this request.", and ledger rows with
meaning + SHA-256 stamp written to `ctms_electronic_signature`. Backend suite:
112 passed. Frontend: `tsc --noEmit` clean; new suite 16/16; full suite at
baseline (196 passing, same 22 pre-existing jest-global failures).

## Follow-up pass — notifications onto ctms_notifications (v2 phase 1)

Phase-1 implementation of `MIGRATION_PLAN_V2_SCHEMA.md` §1: moved the
localStorage-only `notificationService` onto its corresponding v2 table
(`ctms_notifications`), per the plan's naming stance (wire the existing
plural table; no parallel singular family). Rows are per-recipient
(`user_id` NOT NULL) — the mirror stores each signed-in user's visible
records, so no org/role column or read-time role filtering is needed.

- **modified `Engine/tria_engine/apps/ctms/models.py`** — added
  `CtmsNotification` on `ctms_notifications`: the v2 base columns plus five
  additive extension columns carrying the frontend contract (`client_key`,
  `actor_name`, `actor_role`, `study_code`, `metadata` — the Declarative
  attribute is `meta` because `metadata` is reserved).
- **added `Engine/tria_engine/alembic/versions/c2f5a8e1b904_ctms_notifications_v2.py`**
  — inspector-guarded migration: pure-Alembic DBs get the full table
  (v2 base + extensions); SQL-package-loaded DBs with the pre-existing base
  table get only the extension columns added. Verified both paths on fresh
  SQLite DBs, plus `upgrade head` / table-shape checks.
- **added `Engine/tria_engine/apps/ctms/router_notifications.py`** —
  `GET /api/notifications` (current user's rows, newest first),
  `POST /api/notifications/sync` (idempotent bulk upsert by `(user_id,
  client_key)`; patch semantics — a partial record never wipes unmentioned
  fields; missing-key/title records reported, not fatal),
  `POST /api/notifications/{id}/read`. Every query is self-scoped to
  `user_id == current user` (404 for another user's row), so no RBAC module
  gate is required.
- **modified `Engine/tria_engine/main.py`** — mounted the notifications
  router.
- **added `Sql/10_3_ctms_notifications_ext.sql`** — additive
  `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` for the five extension columns
  + a `(user_id, client_key)` index; included from `run_all.sql`. Verified:
  full package runs with `ON_ERROR_STOP=1`; the table ends with all 16
  columns.
- **added `Engine/tria_engine/tests/test_notifications_api.py`** — 6 tests:
  sync→list lossless round-trip, idempotent resync by client_key,
  per-recipient isolation (user B sees nothing and gets 404 on user A's
  row), read-toggle endpoint, payload validation (skip reasons), and a
  partial-sync-preserves-fields regression (found live on Postgres — a bare
  read-state resync originally wiped actor/type/study). Autouse fixture
  clears `ctms_notifications` between tests (shared session DB).
- **modified `UI/src/shared/services/notificationService.ts`** — dual-mode
  mirror while keeping the localStorage store as the offline source of
  truth and every existing export unchanged: after each successful mutation
  (`createNotification`, `markNotificationRead`,
  `markAllNotificationsReadForUser`) the user's visible store is best-effort
  pushed via `POST /api/notifications/sync` (fail-soft, fire-and-forget);
  `getNotificationsForUser` hydrates once per session from
  `GET /api/notifications` when API mode is on and the local store is
  empty. New exports: `notificationRecordFromBackend`,
  `mergeNotifications`, `notificationsForSync`,
  `syncNotificationsToBackend`, `hydrateNotificationsFromBackend`.
- **added `UI/src/shared/services/__tests__/notificationSync.test.ts`** — 8
  tests covering the backend-row mapping (incl. snake-ish aliases and the
  no-client-key fallback) and merge semantics (local wins, dedupe, sorting,
  non-array tolerance).

Live end-to-end verification against Postgres (scratch DB from
`Sql/run_all.sql`): sync 2 records -> created 2; resync -> idempotent
(created 0 / updated 1); list returns both with correct read state; read
endpoint flips `is_read`; partial read-only resync preserves
actor/type/study (the wipe regression); rows land in `ctms_notifications`
with the FK to `accounts_user` satisfied. Backend suite: 118 passed.
Frontend: `tsc --noEmit` clean; new tests 8/8; full suite at baseline (204
passing, same 22 pre-existing jest-global failures); production build OK.