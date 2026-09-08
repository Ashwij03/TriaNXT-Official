# tria_engine/apps/ctms/router_subjects.py
#
# Subject mirror REST surface (frontend subjectService.ts subjectsByStudy
# store — enrollment/screening records pushed via POST /subjects/sync):
#
#   GET /subjects/summary    aggregate counts/status envelope (dashboard KPIs)
#   GET /subjects            list (optional ?studyId= filter)
#   GET /subjects/{code}     one record by its study-qualified sync code
#
# Reads are authenticated + org-scoped, with SQL-level study/site scope
# filters applied from the row scope columns (same record layer as the gap
# modules). Record bodies are the exact subject JSON the UI renders.
#
# /summary is registered BEFORE /{code} so the literal path "summary" always
# resolves to the aggregate, never to a subject detail lookup.

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...apps.accounts.dependencies import get_current_user
from ...apps.accounts.models import User
from ...core.cache import ENROLLMENT_COUNTS_CACHE_KEY, cache_get_json, cache_set_json
from ...core.database import get_db
from .common import _scope_condition, guarded, iso_now, list_records, load_row
from .models import CtmsConsentEvent, CtmsIcfVersion, CtmsReConsentCampaign, CtmsSubject, CtmsSubjectStatusHistory, CtmsVisit

router = APIRouter(prefix="/subjects", tags=["ctms-subjects"])

# Canonical subject-lifecycle buckets the Sponsor/CRO/Site Staff dashboards
# render (subjectLifecycle.ts / normalizeStatus.ts): zero-padded so the UI
# can read a stable shape without defaulting on its side.
_CANONICAL_STATUSES = [
    "Screened",
    "Enrolled",
    "Ongoing",
    "Completed",
    "Withdrawn",
    "Dropout",
]

# Legacy/alternate tokens stored by older builds are normalized into the
# same buckets the frontend normalizer uses (screen* -> Screened,
# randomiz* / enroll* -> Enrolled, discontin*/terminat* -> Dropout).
_STATUS_ALIASES = {
    "screening": "Screened",
    "enrolling": "Enrolled",
    "enrolled": "Enrolled",
    "randomized": "Enrolled",
    "randomised": "Enrolled",
    "randomization": "Enrolled",
    "randomisation": "Enrolled",
    "on-study": "Enrolled",
    "ongoing": "Ongoing",
    "completed": "Completed",
    "withdrawn": "Withdrawn",
    "withdrew": "Withdrawn",
    "dropout": "Dropout",
    "drop out": "Dropout",
    "discontinued": "Dropout",
    "terminated": "Dropout",
}


def _canonical_status(raw) -> str:
    """Map a stored subject status token onto the six canonical buckets.

    Mirrors the frontend normalizeStatus semantics so legacy tokens such as
    \"Screening\" or \"Randomized\" land in the same bucket the UI would show.
    Unknown tokens are returned verbatim (never dropped from the totals).
    """
    token = str(raw or "").strip()
    if not token:
        return "Unknown"
    lower = token.lower()
    if lower in _STATUS_ALIASES:
        return _STATUS_ALIASES[lower]
    if "screen" in lower:
        return "Screened"
    if "randomi" in lower or "enroll" in lower:
        return "Enrolled"
    if "withdraw" in lower:
        return "Withdrawn"
    if "drop" in lower or "discontin" in lower or "terminat" in lower:
        return "Dropout"
    if lower == "ongoing" or lower == "completed":
        return token[:1].upper() + token[1:]
    return token


def _filter_study(records: list[dict], study_id: str | None) -> list[dict]:
    if not study_id:
        return records
    want = str(study_id).strip()
    return [r for r in records if str(r.get("studyId") or "").strip() == want]


def _subject_summary(records: list[dict]) -> dict:
    by_status = {status: 0 for status in _CANONICAL_STATUSES}
    enrolled = 0
    for record in records:
        status = _canonical_status(record.get("status"))
        if status in by_status:
            by_status[status] += 1
            # Enrolled-stage subjects (Enrolled/Ongoing/Completed) drive the
            # enrollment-progress KPIs (normalizeStatus.isEnrolledSubjectStatus).
            if status in ("Enrolled", "Ongoing", "Completed"):
                enrolled += 1
        else:
            by_status[status] = by_status.get(status, 0) + 1
    # byStatus ordering: canonical buckets first, then any extra tokens.
    extra = {k: v for k, v in by_status.items() if k not in _CANONICAL_STATUSES}
    ordered = {k: by_status[k] for k in _CANONICAL_STATUSES}
    ordered.update(extra)
    return {
        "total": len(records),
        "byStatus": ordered,
        "enrolled": enrolled,
    }


# ---------------------------------------------------------------------------
# Live per-study enrollment counts (Task 3)
#
# JSON-mirror equivalent of
#   SELECT study_id, COUNT(DISTINCT subject_id) ... WHERE status IN (...) GROUP BY study_id
# over the ctms_subject mirror rows, cached for 15 seconds (core/cache.py) and
# invalidated whenever POST /subjects/sync runs (router_sync.py).
# ---------------------------------------------------------------------------

_ENROLLMENT_COUNT_STATUSES = {"Screened", "Enrolled"}


def _enrollment_counts(records: list[dict]) -> dict:
    """Per-study {enrolled, total} counts of distinct subjects in the
    Screened/Enrolled canonical buckets. `total` mirrors the COUNT(DISTINCT)
    aggregation; `enrolled` is the subset whose canonical status is Enrolled.
    """
    by_study: dict[str, dict] = {}
    for record in records:
        status = _canonical_status(record.get("status"))
        if status not in _ENROLLMENT_COUNT_STATUSES:
            continue
        study = str(record.get("studyId") or record.get("study") or "").strip()
        if not study:
            continue
        bucket = by_study.setdefault(study, {"studyId": study, "enrolled": 0, "total": 0})
        bucket["total"] += 1
        if status == "Enrolled":
            bucket["enrolled"] += 1
    return {"byStudy": list(by_study.values()), "updatedAt": iso_now()}


@router.get("/enrollment-counts")
@router.get("/enrollment-counts/")
def subject_enrollment_counts(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cached = cache_get_json(ENROLLMENT_COUNTS_CACHE_KEY)
    if cached is not None:
        return {"data": cached}
    result = _enrollment_counts(list_records(db, CtmsSubject, user))
    cache_set_json(ENROLLMENT_COUNTS_CACHE_KEY, result, ttl_seconds=15)
    return {"data": result}


# ---------------------------------------------------------------------------
# Subject status-history / consent (Task 3)
# ---------------------------------------------------------------------------

# Consent-validity window used by the server-side consent derivation: an ICF
# version carries no expiry date, so a consent older than this window is
# reported as "Expiring Soon" (needs renewal review). Mirrored by the
# frontend subjectConsentStatus.ts module.
CONSENT_VALIDITY_DAYS = 730

# Completed visit statuses included in the subject timeline.
_TIMELINE_VISIT_STATUSES = {"completed"}


def _timeline_ts(value) -> str:
    """Normalize a record timestamp to an ISO string for chronological sort."""
    return str(value or "").strip() or iso_now()


def derive_subject_consent(
    subject: dict,
    consent_events: list[dict],
    icf_versions: list[dict],
    reconsent_campaigns: list[dict],
    *, now: datetime | None = None,
) -> dict:
    """Derive a subject's current consent status from the same source data the
    frontend's local logic reads (consent events + ICF versions + open
    re-consent campaigns).

    # TODO(Task 3): once eISF document-approval data is reliable, this
    # endpoint should be pointed at it instead — a signed/approved consent
    # document approval is the authoritative consent evidence. The derivation
    # below uses the ICF/eConsent records only (ctms_consentevent /
    # ctms_icfversion plus open ctms_reconsentcampaign rows).
    """
    subject_id = str(subject.get("subjectId") or subject.get("id") or "").strip()
    study_code = str(subject.get("studyId") or subject.get("study") or "").strip()
    today = (now or datetime.now(timezone.utc)).date()

    def _norm(value) -> str:
        return str(value or "").strip().lower()

    # 1. Open re-consent campaign pending for this subject -> action needed.
    open_campaign = next(
        (
            c
            for c in reconsent_campaigns
            if str(c.get("status") or "").strip().lower() == "open"
            and _norm(c.get("studyCode")) == _norm(study_code)
            and any(
                _norm(entry.get("subjectId")) == _norm(subject_id)
                and not entry.get("completedAt")
                for entry in (c.get("subjects") or [])
            )
        ),
        None,
    )
    if open_campaign is not None:
        return {
            "status": "reconsent_required",
            "label": "Re-consent Required",
            "needsAttention": True,
            "reason": f"Subject {subject_id} must re-consent on ICF v{open_campaign.get('icfVersion') or '?'} (campaign {open_campaign.get('id')}).",
            "campaignId": open_campaign.get("id"),
        }

    # 2. No consent event at all -> not consented.
    subject_events = [
        e
        for e in consent_events
        if _norm(e.get("subjectId")) == _norm(subject_id)
        and (not study_code or _norm(e.get("studyCode")) == _norm(study_code))
    ]
    if not subject_events:
        return {
            "status": "not_consented",
            "label": "Not Consented",
            "needsAttention": True,
            "reason": f"No consent event has been recorded for subject {subject_id}.",
        }

    latest = max(
        subject_events,
        key=lambda e: _timeline_ts(e.get("date") or e.get("createdAt")),
    )
    icf_version_id = str(latest.get("icfVersionId") or "").strip()
    icf_version = next(
        (v for v in icf_versions if str(v.get("id") or "").strip() == icf_version_id),
        None,
    )

    # 3. Consented on a version that was later superseded/expired -> re-consent.
    if icf_version is not None:
        version_status = str(icf_version.get("status") or "").strip().lower()
        if version_status in ("superseded", "expired", "archived"):
            return {
                "status": "reconsent_required",
                "label": "Re-consent Required",
                "needsAttention": True,
                "reason": f"Consent was recorded on ICF v{icf_version.get('version')} which is now {icf_version.get('status')}.",
                "icfVersionId": icf_version_id,
            }

    # 4. Consent older than the validity window -> expiring soon.
    consent_date = str(latest.get("date") or latest.get("createdAt") or "")[:10]
    if consent_date:
        try:
            signed_on = datetime.strptime(consent_date, "%Y-%m-%d").date()
            if (today - signed_on).days > CONSENT_VALIDITY_DAYS:
                return {
                    "status": "expiring_soon",
                    "label": "Expiring Soon",
                    "needsAttention": True,
                    "reason": f"Consent on ICF v{icf_version.get('version') if icf_version else '?'} signed {consent_date} is older than the {CONSENT_VALIDITY_DAYS}-day validity window.",
                    "icfVersionId": icf_version_id,
                }
        except ValueError:
            pass

    return {
        "status": "consented",
        "label": "Consented",
        "needsAttention": False,
        "reason": f"Consent confirmed on ICF v{icf_version.get('version') if icf_version else '?'} on {consent_date or 'recorded'}.",
        "icfVersionId": icf_version_id,
    }


def _build_subject_timeline(
    status_history: list[dict],
    visits: list[dict],
    consent_events: list[dict],
) -> list[dict]:
    entries: list[dict] = []
    for row in status_history:
        entries.append(
            {
                "type": "status_change",
                "at": _timeline_ts(row.get("changedAt") or row.get("createdAt")),
                "label": f"Status changed to {row.get('status') or 'Unknown'}",
                "detail": {
                    "status": row.get("status"),
                    "reason": row.get("reason") or "",
                    "changedBy": row.get("changedBy") or "",
                },
            }
        )
    for visit in visits:
        entries.append(
            {
                "type": "visit",
                "at": _timeline_ts(
                    visit.get("completedAt") or visit.get("actualDate") or visit.get("date") or visit.get("createdAt")
                ),
                "label": f"Visit {visit.get('visit') or '?'} completed",
                "detail": {
                    "visit": visit.get("visit"),
                    "date": visit.get("date"),
                    "status": visit.get("status"),
                },
            }
        )
    for event in consent_events:
        entries.append(
            {
                "type": "consent",
                "at": _timeline_ts(event.get("date") or event.get("createdAt")),
                "label": f"Consent recorded on ICF v{event.get('icfVersion') or '?'}",
                "detail": {
                    "icfVersion": event.get("icfVersion"),
                    "icfVersionId": event.get("icfVersionId"),
                    "witness": event.get("witness") or "",
                },
            }
        )
    entries.sort(key=lambda entry: entry["at"])
    return entries


@router.get("/{code}/history")
def subject_history(
    code: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Merged, chronologically-sorted timeline for one subject: status
    transitions (ctms_subject_status_history) + completed visits (ctms_visit)
    + consent events (ctms_consentevent), each tagged with its source type.
    """

    def _history():
        _, subject = load_row(db, CtmsSubject, user, code, "Subject not found.")
        subject_id = str(subject.get("subjectId") or "").strip()
        study = str(subject.get("studyId") or subject.get("study") or "").strip()

        def _scoped(model, extra=None):
            stmt = select(model)
            cond = _scope_condition(model, user)
            if cond is not None:
                stmt = stmt.where(cond)
            if extra is not None:
                stmt = stmt.where(extra)
            return [dict(r.data) for r in db.execute(stmt).scalars().all()]

        status_rows = _scoped(CtmsSubjectStatusHistory)
        if subject_id:
            status_rows = [
                r
                for r in status_rows
                if str(r.get("subjectId") or "").strip() == subject_id
                and (not study or str(r.get("studyId") or r.get("studyCode") or "").strip() == study)
            ]

        visits = _scoped(CtmsVisit)
        visits = [
            v
            for v in visits
            if str(v.get("subjectId") or "").strip() == subject_id
            and str(v.get("status") or "").strip().lower() in _TIMELINE_VISIT_STATUSES
        ]

        consent_events = _scoped(CtmsConsentEvent)
        consent_events = [
            e
            for e in consent_events
            if str(e.get("subjectId") or "").strip() == subject_id
        ]

        return {
            "subjectId": subject_id or subject.get("id"),
            "studyId": study,
            "timeline": _build_subject_timeline(status_rows, visits, consent_events),
        }

    return guarded(_history)


@router.get("/{code}/consent")
def subject_consent_status(
    code: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Server-computed consent status for one subject (badge source for the
    Subject dashboards/rows). Derivation lives in derive_subject_consent so
    the frontend and backend share the same rules.
    """

    def _consent():
        _, subject = load_row(db, CtmsSubject, user, code, "Subject not found.")
        subject_id = str(subject.get("subjectId") or "").strip()
        study = str(subject.get("studyId") or subject.get("study") or "").strip()

        def _records(model):
            stmt = select(model)
            cond = _scope_condition(model, user)
            if cond is not None:
                stmt = stmt.where(cond)
            return [dict(r.data) for r in db.execute(stmt).scalars().all()]

        events = _records(CtmsConsentEvent)
        versions = _records(CtmsIcfVersion)
        campaigns = _records(CtmsReConsentCampaign)
        if subject_id:
            events = [e for e in events if str(e.get("subjectId") or "").strip() == subject_id]
        if study:
            campaigns = [c for c in campaigns if str(c.get("studyCode") or "").strip() == study]
        status = derive_subject_consent(subject, events, versions, campaigns)
        return {"subjectId": subject_id or subject.get("id"), "studyId": study, **status}

    return guarded(_consent)


@router.get("/summary")
@router.get("/summary/")
def subject_summary(
    request: Request,
    studyId: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Aggregate mirror totals under a {\"data\": ...} envelope — the same
    contract Safety Center's summary endpoint uses, so dashboard cards can
    read totals in API mode instead of counting local stores alone.
    """
    records = _filter_study(list_records(db, CtmsSubject, user), studyId)
    return {"data": _subject_summary(records)}


@router.get("")
@router.get("/")
def subject_list(
    request: Request,
    studyId: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    records = _filter_study(list_records(db, CtmsSubject, user), studyId)
    return records


@router.get("/{code}")
def subject_detail(
    code: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    def _detail():
        _, record = load_row(db, CtmsSubject, user, code, "Subject not found.")
        return record

    return guarded(_detail)
