# tria_engine/tests/test_subject_status_history_api.py
#
# Task 3 — subject status-history trail:
#   * POST /api/site/subjects/history/sync  (append-only bulk upsert)
#   * GET  /api/site/subjects/{code}/history (merged chronological timeline)
#   * GET  /api/site/subjects/{code}/consent (server-computed consent status)
#
# Covers the merge/sort of the three timeline sources, append-only behavior
# (a new transition can never overwrite a prior one), and RBAC/scoping.

from __future__ import annotations

import uuid

from tria_engine.apps.accounts.models import User
from tria_engine.apps.organizations.models import Organization, Role
from tria_engine.core.database import SessionLocal
from tria_engine.core.security import hash_password

PASSWORD = "RolePass123!"
SUBJECTS_SYNC = "/api/site/subjects/sync"
HISTORY_SYNC = "/api/site/subjects/history/sync"
ICF_VERSIONS_SYNC = "/api/site/icf/versions/sync"
ICF_EVENTS_SYNC = "/api/site/icf/events/sync"
ICF_CAMPAIGNS_SYNC = "/api/site/icf/campaigns/sync"

# Every test uses its own study code — the shared test DB (conftest SQLite)
# never collides across tests, matching the existing test-file convention.
# The pre-existing test files assert whole-collection lengths, so every test
# here also deletes the rows it wrote before finishing.
STUDY = "TNX-HIST"
SUBJECT = "S-1001"

from tria_engine.apps.ctms.models import (  # noqa: E402
    CtmsConsentEvent,
    CtmsIcfVersion,
    CtmsReConsentCampaign,
    CtmsSubject,
    CtmsSubjectStatusHistory,
    CtmsVisit,
)

_CLEANUP_MODELS = (
    CtmsSubjectStatusHistory,
    CtmsVisit,
    CtmsConsentEvent,
    CtmsIcfVersion,
    CtmsReConsentCampaign,
    CtmsSubject,
)


def _cleanup(*studies: str) -> None:
    """Delete every row whose study scope column is one of `studies`."""
    db = SessionLocal()
    try:
        for model in _CLEANUP_MODELS:
            for study in studies:
                db.query(model).filter(model.study_id == study).delete()
        db.commit()
    finally:
        db.close()


def _seed_user(role_name: str, org_name: str) -> str:
    db = SessionLocal()
    try:
        org = db.query(Organization).filter(Organization.name == org_name).one()
        role = (
            db.query(Role)
            .filter(Role.name == role_name, Role.organization_id == org.id)
            .first()
        )
        if role is None:
            role = Role(name=role_name, organization_id=org.id)
            db.add(role)
            db.flush()
        email = f"{role_name.lower().replace(' ', '.')}.{uuid.uuid4().hex[:6]}@test.local"
        db.add(
            User(
                username=email.split("@")[0],
                email=email,
                password=hash_password(PASSWORD),
                first_name=role_name,
                last_name="User",
                is_active=True,
                organization_id=org.id,
                role_id=role.id,
            )
        )
        db.commit()
        return email
    finally:
        db.close()


def _login(client, email: str, password: str = PASSWORD):
    res = client.post("/api/accounts/login/", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return client


def _as_admin(client):
    return _login(client, "admin@test.local", "AdminPass123!")


def _subject(subj: str = SUBJECT, status: str = "Screened") -> dict:
    return {
        "id": subj,
        "subjectId": subj,
        "studyId": STUDY,
        "initials": "SJ",
        "site": "Site A",
        "siteNo": "SITE-A",
        "status": status,
        "screeningDate": "2026-09-01",
        "enrollmentDate": "—",
        "currentVisit": "Screening",
        "createdAt": "2026-09-01T08:00:00.000Z",
        "updatedAt": "2026-09-01T08:00:00.000Z",
    }


def _history_row(subj: str, status: str, changed_at: str, reason: str = "", study: str = STUDY) -> dict:
    return {
        "studyId": study,
        "subjectId": subj,
        "status": status,
        "reason": reason,
        "changedBy": "Site Staff",
        "changedAt": changed_at,
    }


def _sync(client, path: str, records) -> dict:
    res = client.post(path, json={"records": records})
    assert res.status_code == 200, res.text
    return res.json()


def _history_url(study: str = STUDY, subj: str = SUBJECT):
    return f"/api/site/subjects/{study}%3A%3A{subj}/history"


def _consent_url(study: str = STUDY, subj: str = SUBJECT):
    return f"/api/site/subjects/{study}%3A%3A{subj}/consent"


def _subject_in(study: str, subj: str = SUBJECT, status: str = "Screened") -> dict:
    return {
        **{k: v for k, v in _subject(subj, status).items() if k != "studyId"},
        "studyId": study,
    }


# ===========================================================================
# Auth / RBAC
# ===========================================================================


def test_status_history_surfaces_require_auth(client):
    assert client.post(HISTORY_SYNC, json={"records": []}).status_code == 401
    assert client.get(_history_url()).status_code == 401
    assert client.get(_consent_url()).status_code == 401
    _cleanup()


def test_status_history_unknown_subject_is_404(client):
    _as_admin(client)
    assert client.get(_history_url("TNX-NOPE", "S-0")).status_code == 404
    assert client.get(_consent_url("TNX-NOPE", "S-0")).status_code == 404
    _cleanup("TNX-NOPE")


def test_history_and_consent_are_org_scoped(client):
    study = "TNX-HIST-ORG"
    _as_admin(client)
    _sync(client, SUBJECTS_SYNC, [_subject_in(study)])
    _sync(client, HISTORY_SYNC, [_history_row(SUBJECT, "Enrolled", "2026-09-02T09:00:00.000Z", study=study)])

    # A user from another org resolves the subject to 404 (load_row scoping).
    org_b = Organization(name="HistOrgB")
    db = SessionLocal()
    try:
        db.add(org_b)
        db.flush()
        role = Role(name="Sponsor", organization_id=org_b.id)
        db.add(role)
        db.flush()
        email = f"hist.b.{uuid.uuid4().hex[:6]}@test.local"
        db.add(
            User(
                username=email.split("@")[0],
                email=email,
                password=hash_password(PASSWORD),
                first_name="Hist",
                last_name="B",
                is_active=True,
                organization_id=org_b.id,
                role_id=role.id,
            )
        )
        db.commit()
    finally:
        db.close()

    _login(client, email)
    assert client.get(_history_url(study)).status_code == 404
    assert client.get(_consent_url(study)).status_code == 404
    _cleanup(study)


def test_history_sync_is_write_gated(client):
    """CRO is read-only on subjects — the history sync inherits that gate."""
    cro = _seed_user("CRO", "Test Org")
    _login(client, cro)
    assert client.post(HISTORY_SYNC, json={"records": [_history_row(SUBJECT, "Enrolled", "2026-09-02T09:00:00.000Z")]}).status_code == 403
    _cleanup()


# ===========================================================================
# Append-only semantics
# ===========================================================================


def test_history_sync_is_append_only_across_transitions(client):
    study = "TNX-HIST-APPEND"
    _as_admin(client)
    _sync(client, SUBJECTS_SYNC, [_subject_in(study)])

    # Two transitions for the same subject at different times must land as two
    # distinct rows — the epoch-qualified code can never overwrite the first.
    report = _sync(
        client,
        HISTORY_SYNC,
        [
            _history_row(SUBJECT, "Enrolled", "2026-09-02T09:00:00.000Z", reason="enrolled", study=study),
            _history_row(SUBJECT, "Ongoing", "2026-09-10T09:00:00.000Z", reason="visit 1 done", study=study),
        ],
    )
    assert report["created"] == 2 and report["skipped"] == []

    data = client.get(_history_url(study)).json()
    timeline = data["timeline"]
    assert len(timeline) == 2
    assert [entry["type"] for entry in timeline] == ["status_change", "status_change"]
    assert [entry["detail"]["status"] for entry in timeline] == ["Enrolled", "Ongoing"]
    # Chronological order (earliest first).
    assert timeline[0]["at"] < timeline[1]["at"]
    _cleanup(study)


# ===========================================================================
# Merged timeline
# ===========================================================================


def test_history_merges_status_visits_and_consent_chronologically(client):
    study = "TNX-HIST-MERGE"
    _as_admin(client)
    _sync(client, SUBJECTS_SYNC, [_subject_in(study, status="Enrolled")])

    # Status change (early), completed visit (middle), consent event (latest).
    _sync(
        client,
        HISTORY_SYNC,
        [_history_row(SUBJECT, "Enrolled", "2026-09-02T09:00:00.000Z", reason="randomized", study=study)],
    )
    _sync(
        client,
        "/api/site/visits/sync",
        [
            {
                "id": f"{study}::{SUBJECT}::Visit 1",
                "date": "2026-09-05",
                "subjectId": SUBJECT,
                "visit": "Visit 1",
                "status": "Completed",
                "study": study,
                "completedAt": "2026-09-05T10:00:00.000Z",
            }
        ],
    )
    _sync(
        client,
        ICF_VERSIONS_SYNC,
        [
            {
                "id": "ICFV-HIST-1",
                "studyCode": study,
                "siteCode": "SITE-A",
                "version": "2.0",
                "status": "Active",
                "createdAt": "2026-08-01T00:00:00.000Z",
            }
        ],
    )
    _sync(
        client,
        ICF_EVENTS_SYNC,
        [
            {
                "id": "CNS-HIST-1",
                "studyCode": study,
                "siteCode": "SITE-A",
                "subjectId": SUBJECT,
                "icfVersionId": "ICFV-HIST-1",
                "icfVersion": "2.0",
                "date": "2026-09-08",
                "createdAt": "2026-09-08T11:00:00.000Z",
            }
        ],
    )

    data = client.get(_history_url(study)).json()
    timeline = data["timeline"]

    assert [entry["type"] for entry in timeline] == ["status_change", "visit", "consent"]
    # Chronologically sorted across the three sources.
    assert timeline[0]["at"].startswith("2026-09-02")
    assert timeline[1]["at"].startswith("2026-09-05")
    assert timeline[2]["at"].startswith("2026-09-08")
    assert timeline[1]["detail"]["visit"] == "Visit 1"
    assert timeline[2]["detail"]["icfVersion"] == "2.0"
    _cleanup(study)


# ===========================================================================
# Consent derivation
# ===========================================================================


def test_consent_derivation_states(client):
    study = "TNX-HIST-CONSENT"
    _as_admin(client)
    _sync(client, SUBJECTS_SYNC, [_subject_in(study)])

    # 1. No consent event -> Not Consented.
    status = client.get(_consent_url(study)).json()
    assert status["status"] == "not_consented"
    assert status["label"] == "Not Consented"
    assert status["needsAttention"] is True

    # 2. Consent on an ACTIVE ICF version -> Consented.
    _sync(
        client,
        ICF_VERSIONS_SYNC,
        [
            {
                "id": "ICFV-CNS-1",
                "studyCode": study,
                "siteCode": "SITE-A",
                "version": "1.0",
                "status": "Active",
                "createdAt": "2026-08-01T00:00:00.000Z",
            }
        ],
    )
    _sync(
        client,
        ICF_EVENTS_SYNC,
        [
            {
                "id": "CNS-CNS-1",
                "studyCode": study,
                "siteCode": "SITE-A",
                "subjectId": SUBJECT,
                "icfVersionId": "ICFV-CNS-1",
                "icfVersion": "1.0",
                "date": "2026-09-01",
                "createdAt": "2026-09-01T10:00:00.000Z",
            }
        ],
    )
    status = client.get(_consent_url(study)).json()
    assert status["status"] == "consented"
    assert status["needsAttention"] is False

    # 3. Open re-consent campaign pending for the subject -> Re-consent Required.
    _sync(
        client,
        ICF_CAMPAIGNS_SYNC,
        [
            {
                "id": "RC-CNS-1",
                "studyCode": study,
                "siteCode": "SITE-A",
                "amendmentId": "AMD-1",
                "icfVersionId": "ICFV-CNS-1",
                "icfVersion": "1.0",
                "status": "Open",
                "subjects": [{"subjectId": SUBJECT, "completedAt": None}],
                "createdAt": "2026-09-09T00:00:00.000Z",
            }
        ],
    )
    status = client.get(_consent_url(study)).json()
    assert status["status"] == "reconsent_required"
    assert status["label"] == "Re-consent Required"
    assert status["needsAttention"] is True

    # 4. Campaign completed -> back to Consented.
    _sync(
        client,
        ICF_CAMPAIGNS_SYNC,
        [
            {
                "id": "RC-CNS-1",
                "studyCode": study,
                "siteCode": "SITE-A",
                "amendmentId": "AMD-1",
                "icfVersionId": "ICFV-CNS-1",
                "icfVersion": "1.0",
                "status": "Completed",
                "subjects": [{"subjectId": SUBJECT, "completedAt": "2026-09-10T08:00:00.000Z"}],
                "createdAt": "2026-09-09T00:00:00.000Z",
            }
        ],    )
    status = client.get(_consent_url(study)).json()
    assert status["status"] == "consented"
    _cleanup(study)



