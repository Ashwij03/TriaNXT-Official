# tria_engine/apps/ctms/models.py
#
# Backend persistence for the Site CTMS gap modules implemented in the
# frontend (M18 Protocol Amendments, M19 IP/Supply Accountability, M20
# IRB/IEC Submissions, M21 ICF/eConsent, M22 Vendor & Lab Management, M23
# Site Feasibility & Selection).
#
# Design note: each frontend localStorage service keeps flat JSON records
# (one list per entity). To keep the API contract byte-faithful to the
# frontend records — including nested structures such as per-site task
# packs (amendment.sites), transaction trails and excursion lists — each
# record is stored as a JSON document on a thin relational row. The
# relational columns (code, organization_id, created_at/updated_at)
# provide org scoping, ordering and auditability; the document holds the
# full record exactly as the UI renders it.
#
# Schema creation: `Base.metadata.create_all(engine)` creates these tables
# alongside the migrated accounts tables (additive only — nothing existing
# is touched). See docs/gap-assessment/ for the migration note.

from __future__ import annotations

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tria_engine.core.database import BIGINT, Base
from tria_engine.core.timeutils import utcnow


class _CtmsRecord:
    """Shared columns for every CTMS JSON-record table (SQLAlchemy mixin).

    study_id / site_id hold the record's studyCode / siteCode (the codes the
    frontend uses) as first-class indexed columns so role scope filters for
    Site Staff / PI / CRO / Sponsor run at the SQL level instead of having
    to parse each record's JSON. Records that are not study/site-scoped
    (e.g. org-level vendor records) leave both NULL, which the scope filter
    treats as "visible to every org member".
    """

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("organizations_organization.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    study_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    site_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[object] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )


# --- M18 Protocol Amendments -------------------------------------------
class CtmsAmendment(_CtmsRecord, Base):
    __tablename__ = "ctms_amendment"


# --- M19 IP / Supply accountability -------------------------------------
class CtmsIpLot(_CtmsRecord, Base):
    __tablename__ = "ctms_iplot"


# --- M20 IRB / IEC submissions ------------------------------------------
class CtmsIrbSubmission(_CtmsRecord, Base):
    __tablename__ = "ctms_irbsubmission"


# --- M21 ICF / eConsent -------------------------------------------------
class CtmsIcfVersion(_CtmsRecord, Base):
    __tablename__ = "ctms_icfversion"


class CtmsConsentEvent(_CtmsRecord, Base):
    __tablename__ = "ctms_consentevent"


class CtmsReConsentCampaign(_CtmsRecord, Base):
    __tablename__ = "ctms_reconsentcampaign"


# --- M22 Vendor & Lab management ---------------------------------------
class CtmsVendor(_CtmsRecord, Base):
    __tablename__ = "ctms_vendor"


class CtmsKit(_CtmsRecord, Base):
    __tablename__ = "ctms_kit"


# --- M23 Site feasibility & selection -----------------------------------
class CtmsFeasibilityCandidate(_CtmsRecord, Base):
    __tablename__ = "ctms_feasibilitycandidate"


class CtmsFeasibilityScoring(_CtmsRecord, Base):
    """Per-study scoring criteria configuration (code == normalized study code)."""

    __tablename__ = "ctms_feasibilityscoring"


# --- Safety (AE / SAE cases) ----------------------------------------------
class CtmsAeCase(_CtmsRecord, Base):
    """Adverse-event / SAE case (Safety Center). Row scope columns hold the
    case's study code (data['study_id']) so Site Staff / PI study-scope
    filters run at the SQL level; the JSON document carries the full case
    exactly as SafetyCenter.tsx renders it.
    """

    __tablename__ = "ctms_safetyaecase"


# --- Monitoring access requests -------------------------------------------
class CtmsMonitoringRequest(_CtmsRecord, Base):
    """Date-scoped, view-only monitoring access request (MonitoringAccess.tsx).
    Records are org-level (no study/site scope columns) because the workflow
    is between requester and approver inside one organization; the requested
    site id lives in the JSON document (data['site']).
    """

    __tablename__ = "ctms_monitoringrequest"


# --- Subjects & visits (enrollment / screening mirror) ----------------------
class CtmsSubject(_CtmsRecord, Base):
    """Subject records mirrored from the frontend subjectsByStudy store
    (subjectService.ts). Row scope columns hold the subject's study code
    (data['studyId']) so SQL-level study filters apply; the JSON document is
    the exact subject row the UI renders.
    """

    __tablename__ = "ctms_subject"


class CtmsVisit(_CtmsRecord, Base):
    """Per-subject visit schedule rows mirrored from the frontend adminSchedules
    store (visitScheduleService.ts). Each row's code is the schedule id
    (`study::subjectId::visit`) and data['study']/data['studyKey'] carry the
    study code used for the row-level scope column.
    """

    __tablename__ = "ctms_visit"


class CtmsSubjectStatusHistory(_CtmsRecord, Base):
    """Append-only status-transition trail for subjects (Task 3).

    Every status change inserts a NEW row; rows are never updated or deleted,
    so the Subject Profile timeline stays a durable, chronological audit.
    The ER-diagram fields live in the JSON `data` column (subjectId, status,
    reason, changedBy, changedAt) exactly like every other Ctms* record, with
    the study code promoted to the row-level `study_id` scope column.

    Row code convention: `"<studyCode>::<subjectId>::h<epochMillis>"` — the
    epoch suffix makes every transition's code unique by construction, so the
    generic bulk_sync_records upsert-by-code helper can never accidentally
    overwrite a prior transition.
    """

    __tablename__ = "ctms_subject_status_history"


# --- Multi-signer signature requests (5.3) --------------------------------------
# These two classes model the fully-normalized v2 tables already defined in
# the authoritative SQL package (03_operations_governance.sql):
# ctms_signature_requests / ctms_signature_request_signers. They track a
# request for one-or-more signatures (sequential/parallel sign-off) and each
# signer's pending/complete status — broader than the single completed
# signature recorded by ctms_electronic_signature (apps/eisf/models.py).


class CtmsSignatureRequest(Base):
    """A signature request: one-or-more signers asked to sign a document.

    document_id / study_id are plain typed columns here (no ORM FK): the
    authoritative SQL package (03_operations_governance.sql) declares the
    FK to ctms_documents / ctms_studies, which have no SQLAlchemy model yet
    (they are part of the orphaned v2 family — see MIGRATION_PLAN_V2_SCHEMA.md).
    The database enforces those constraints; the ORM stays loadable until the
    v2 models land.
    """

    __tablename__ = "ctms_signature_requests"

    request_id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    study_id: Mapped[int | None] = mapped_column(BIGINT, nullable=True)
    requested_by: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("accounts_user.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT")
    sent_at: Mapped[object] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[object] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[object] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime, nullable=False, default=utcnow)


class CtmsSignatureRequestSigner(Base):
    """One signer on a signature request (pending/complete status)."""

    __tablename__ = "ctms_signature_request_signers"
    __table_args__ = (UniqueConstraint("request_id", "user_id"),)

    signer_id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("ctms_signature_requests.request_id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("accounts_user.id", ondelete="RESTRICT"), nullable=False
    )
    signer_role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    signer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    meaning: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signed_at: Mapped[object] = mapped_column(DateTime, nullable=True)
    verification_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    certificate: Mapped[dict | None] = mapped_column(JSON, nullable=True)


# --- Governance module scaffolding (Task 6 — data layer only) ------------------
# These tables back the future Compliance / Audit / Deviations / CAPA / Risk
# pages. They follow the exact _CtmsRecord + Base pattern; no routes or UI
# exist yet (see the sidebar governance links task for the forward-looking
# navigation scaffolding).


# --- Notifications (v2 migration phase 1 — ctms_notifications) ---------------
# Maps the fully-normalized v2 table from the SQL package
# (03_operations_governance.sql) plus a small set of ADDITIVE extension
# columns (client_key, actor_name, actor_role, study_code, metadata) that
# carry the frontend notificationService record contract the v2 base columns
# cannot express. The extension columns ship as idempotent ALTERs in the SQL
# package (10_3_ctms_notifications_ext.sql) and in the matching Alembic
# revision.
#
# Rows are per-recipient (user_id NOT NULL): the backend mirrors the current
# signed-in user's visible notifications, so there is no org/role column and
# no read-time role filtering — the write path already resolved who sees
# what. study_id stays a plain typed column (ctms_studies has no ORM model
# yet); the raw study code lives in study_code.


class CtmsNotification(Base):
    __tablename__ = "ctms_notifications"

    notification_id: Mapped[int] = mapped_column(
        BIGINT, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("accounts_user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    study_id: Mapped[int | None] = mapped_column(BIGINT, nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    body: Mapped[str | None] = mapped_column(String, nullable=True)
    notification_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="INFO"
    )
    severity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_read: Mapped[bool] = mapped_column(nullable=False, default=False)
    read_at: Mapped[object] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime, nullable=False, default=utcnow)
    # --- additive extension columns (frontend contract) ---
    client_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    actor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    study_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Declarative-attribute name is `meta` because `metadata` is reserved by
    # the SQLAlchemy Declarative API; the DB column stays "metadata" (the SQL
    # package's 10_3 extension column).
    meta: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)


class CtmsComplianceConfig(_CtmsRecord, Base):
    """Per-org/study compliance configuration (thresholds, notification
    rules). Code == the study code for study-scoped configs."""

    __tablename__ = "ctms_complianceconfig"


class CtmsDeviation(_CtmsRecord, Base):
    """Protocol deviation records (site-reported, tracked to closure)."""

    __tablename__ = "ctms_deviation"


class CtmsCapa(_CtmsRecord, Base):
    """Corrective And Preventive Action records linked to deviations."""

    __tablename__ = "ctms_capa"


class CtmsAuditEvent(_CtmsRecord, Base):
    """Structured audit events (who did what to which record and when).
    Written via common.record_audit_event(...)."""

    __tablename__ = "ctms_auditevent"


class CtmsRiskRule(_CtmsRecord, Base):
    """Risk scoring rule configuration (conditions -> points)."""

    __tablename__ = "ctms_riskrule"


class CtmsRiskScore(_CtmsRecord, Base):
    """Computed risk scores per study/subject (latest snapshot per code)."""

    __tablename__ = "ctms_riskscore"


class CtmsRiskEvent(_CtmsRecord, Base):
    """Risk-triggering events/notifications (append-only trail)."""

    __tablename__ = "ctms_riskevent"
