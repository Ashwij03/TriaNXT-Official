# tria_engine/tests/test_subject_enrollment_counts.py
#
# Task 3 — live per-study enrollment counts (GET /api/site/subjects/
# enrollment-counts): per-study aggregation of distinct subjects in the
# Screened/Enrolled canonical buckets, the 15-second cache, and cache
# invalidation whenever POST /subjects/sync runs.

from __future__ import annotations

import uuid

from tria_engine.apps.accounts.models import User
from tria_engine.apps.ctms.models import CtmsSubject
from tria_engine.apps.organizations.models import Organization, Role
from tria_engine.core.cache import ENROLLMENT_COUNTS_CACHE_KEY, cache_delete
from tria_engine.core.database import SessionLocal
from tria_engine.core.security import hash_password

PASSWORD = "RolePass123!"
SUBJECTS_SYNC = "/api/site/subjects/sync"
ENROLLMENT_COUNTS = "/api/site/subjects/enrollment-counts/"

# The conftest SQLite DB is shared by every test file and the pre-existing
# tests assert whole-collection lengths — so every test here cleans up the
# rows it writes (unique per-test study codes make that surgical).
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


def _subject(study: str, subj: str, status: str = "Screened") -> dict:
    return {
        "id": subj,
        "subjectId": subj,
        "studyId": study,
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


def _sync(client, path: str, records) -> dict:
    res = client.post(path, json={"records": records})
    assert res.status_code == 200, res.text
    return res.json()


def test_enrollment_counts_require_auth(client):
    assert client.get(ENROLLMENT_COUNTS).status_code == 401
    _cleanup()


def test_enrollment_counts_aggregate_and_filter_statuses(client):
    """Only canonical Screened/Enrolled subjects count; Ongoing/Withdrawn and
    every other bucket are excluded (the COUNT(DISTINCT) status filter)."""
    _as_admin(client)
    _sync(
        client,
        SUBJECTS_SYNC,
        [
            _subject("TNX-ENC-A", "S-01", status="Screened"),
            _subject("TNX-ENC-A", "S-02", status="Enrolled"),
            _subject("TNX-ENC-A", "S-03", status="Ongoing"),
            _subject("TNX-ENC-A", "S-04", status="Withdrawn"),
            _subject("TNX-ENC-A", "S-05", status="Screening"),  # legacy -> Screened
            _subject("TNX-ENC-A", "S-06", status="Randomized"),  # legacy -> Enrolled
            _subject("TNX-ENC-B", "S-01", status="Enrolled"),
            _subject("TNX-ENC-B", "S-02", status="Completed"),
        ],
    )

    data = client.get(ENROLLMENT_COUNTS).json()["data"]
    by_study = {row["studyId"]: row for row in data["byStudy"]}

    assert by_study["TNX-ENC-A"] == {"studyId": "TNX-ENC-A", "enrolled": 2, "total": 4}
    assert by_study["TNX-ENC-B"] == {"studyId": "TNX-ENC-B", "enrolled": 1, "total": 1}
    # Ongoing/Withdrawn/Completed rows never enter the totals.
    assert by_study["TNX-ENC-A"]["total"] + by_study["TNX-ENC-B"]["total"] == 5
    _cleanup("TNX-ENC-A", "TNX-ENC-B")


def test_enrollment_counts_cache_and_invalidation(client):
    """Second call within the 15s TTL returns the cached value; a subjects
    sync in between invalidates the entry so the next read is fresh."""
    _as_admin(client)
    cache_delete(ENROLLMENT_COUNTS_CACHE_KEY)
    _sync(client, SUBJECTS_SYNC, [_subject("TNX-CACHE", "S-01", status="Enrolled")])

    first = client.get(ENROLLMENT_COUNTS).json()["data"]
    assert first["byStudy"][0] == {"studyId": "TNX-CACHE", "enrolled": 1, "total": 1}

    # Insert a subject directly into the DB (bypassing the sync endpoint, so
    # the cache is NOT invalidated) — the next read still returns the cached
    # aggregate (stale by design inside the TTL window).
    db = SessionLocal()
    try:
        from tria_engine.apps.accounts.models import User as UserModel

        admin = db.query(UserModel).filter(UserModel.email == "admin@test.local").one()
        db.add(
            CtmsSubject(
                code="TNX-CACHE::S-02",
                organization_id=admin.organization_id,
                study_id="TNX-CACHE",
                site_id=None,
                data=_subject("TNX-CACHE", "S-02", status="Screened"),
            )
        )
        db.commit()
    finally:
        db.close()

    cached = client.get(ENROLLMENT_COUNTS).json()["data"]
    assert cached["byStudy"][0]["total"] == 1  # still the cached value

    # Re-pushing the collection through /subjects/sync invalidates the cache.
    _sync(
        client,
        SUBJECTS_SYNC,
        [
            _subject("TNX-CACHE", "S-01", status="Enrolled"),
            _subject("TNX-CACHE", "S-02", status="Screened"),
        ],
    )
    fresh = client.get(ENROLLMENT_COUNTS).json()["data"]
    assert fresh["byStudy"][0] == {"studyId": "TNX-CACHE", "enrolled": 1, "total": 2}
    _cleanup("TNX-CACHE")
    cache_delete(ENROLLMENT_COUNTS_CACHE_KEY)


def test_enrollment_counts_org_scoped(client):
    """Users only ever see their own organization's aggregate (same SQL-level
    scope as every other subjects read)."""
    cache_delete(ENROLLMENT_COUNTS_CACHE_KEY)
    _org_b = _seed_user("Sponsor", "Test Org")
    org_b = "CountOrgB"
    db = SessionLocal()
    try:
        org = Organization(name=org_b)
        db.add(org)
        db.flush()
        org_b_id = org.id
        role = Role(name="Sponsor", organization_id=org_b_id)
        db.add(role)
        db.flush()
        email = f"count.b.{uuid.uuid4().hex[:6]}@test.local"
        db.add(
            User(
                username=email.split("@")[0],
                email=email,
                password=hash_password(PASSWORD),
                first_name="Count",
                last_name="B",
                is_active=True,
                organization_id=org_b_id,
                role_id=role.id,
            )
        )
        db.commit()
    finally:
        db.close()

    _as_admin(client)
    _sync(client, SUBJECTS_SYNC, [_subject("ORG-CNT-A", "S-01", status="Enrolled")])

    _login(client, email)
    _sync(client, SUBJECTS_SYNC, [_subject("ORG-CNT-B", "S-01", status="Screened")])

    data = client.get(ENROLLMENT_COUNTS).json()["data"]
    by_study = {row["studyId"]: row for row in data["byStudy"]}
    assert list(by_study) == ["ORG-CNT-B"]
    assert by_study["ORG-CNT-B"] == {"studyId": "ORG-CNT-B", "enrolled": 0, "total": 1}
    assert _org_b is not None
    _cleanup("ORG-CNT-A", "ORG-CNT-B")