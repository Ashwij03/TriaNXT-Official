# tria_engine/tests/test_notifications_api.py
#
# Phase-1 v2 notifications wiring (MIGRATION_PLAN_V2_SCHEMA.md §1):
#   * POST /api/notifications/sync      — idempotent bulk upsert of the
#                                         caller's records by client_key
#   * GET  /api/notifications           — per-recipient list (user isolation)
#   * POST /api/notifications/{id}/read — mark one row read/unread
#
# The frontend notificationService remains the offline source of truth; these
# tests pin the backend mirror contract the sync endpoint must satisfy:
# records round-trip losslessly (title/message/actor/studyCode/type/metadata/
# createdAt/read) and a user can never read or write another user's rows.

from __future__ import annotations

import uuid

import pytest

from tria_engine.apps.accounts.models import User
from tria_engine.apps.ctms.models import CtmsNotification
from tria_engine.apps.organizations.models import Organization, Role
from tria_engine.core.database import SessionLocal
from tria_engine.core.security import hash_password

PASSWORD = "RolePass123!"


@pytest.fixture(autouse=True)
def _clean_notification_rows():
    """The test DB is shared across every test function in the run, so each
    notifications test starts from an empty ctms_notifications table."""
    yield
    db = SessionLocal()
    try:
        db.query(CtmsNotification).delete()
        db.commit()
    finally:
        db.close()


def _seed_user(role_name: str, tag: str) -> tuple[int, str]:
    db = SessionLocal()
    try:
        org = db.query(Organization).order_by(Organization.id).first()
        role = (
            db.query(Role)
            .filter(Role.name == role_name, Role.organization_id == org.id)
            .first()
        )
        if role is None:
            role = Role(name=role_name, organization_id=org.id)
            db.add(role)
            db.flush()
        email = f"{tag}-{uuid.uuid4().hex[:6]}@test.local"
        user = User(
            username=email.split("@")[0],
            email=email,
            password=hash_password(PASSWORD),
            first_name=role_name,
            last_name="User",
            is_active=True,
            organization_id=org.id,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id, email
    finally:
        db.close()


def _login(client, email: str) -> None:
    res = client.post(
        "/api/accounts/login/",
        json={"email": email, "password": PASSWORD},
    )
    assert res.status_code == 200, res.text


def _login_admin(client) -> None:
    res = client.post(
        "/api/accounts/login/",
        json={"email": "admin@test.local", "password": "AdminPass123!"},
    )
    assert res.status_code == 200, res.text


def _sample_record(**overrides):
    record = {
        "id": f"NOTIF-{uuid.uuid4().hex[:10]}",
        "title": "Subject added",
        "message": "Subject SUB-004 was added to STUDY-X by Jane - PI.",
        "actorName": "Jane Doe",
        "actorRole": "PI",
        "studyCode": "STUDY-X",
        "type": "subject_added",
        "metadata": {"subjectId": "SUB-004", "studyName": "Trial X"},
        "createdAt": "2026-09-08T10:00:00.000Z",
        "read": False,
    }
    record.update(overrides)
    return record


def test_sync_then_list_roundtrip(client):
    _login_admin(client)

    records = [
        _sample_record(id="NOTIF-a1", title="Subject added"),
        _sample_record(
            id="NOTIF-a2",
            title="Study Completed",
            message="Study Trial X completed.",
            actorName="System",
            studyCode="",
            type="study_completed",
            metadata={"studyCode": "STUDY-X"},
            read=True,
            createdAt="2026-09-08T09:00:00.000Z",
        ),
    ]
    res = client.post("/api/notifications/sync", json={"notifications": records})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["created"] == 2
    assert body["updated"] == 0
    assert body["skipped"] == []

    res = client.get("/api/notifications")
    assert res.status_code == 200, res.text
    rows = res.json()
    assert len(rows) == 2

    by_id = {row["id"]: row for row in rows}
    first = by_id["NOTIF-a1"]
    assert first["backendId"] is not None
    assert first["title"] == "Subject added"
    assert first["message"] == "Subject SUB-004 was added to STUDY-X by Jane - PI."
    assert first["actorName"] == "Jane Doe"
    assert first["actorRole"] == "PI"
    assert first["studyCode"] == "STUDY-X"
    assert first["type"] == "subject_added"
    assert first["metadata"] == {"subjectId": "SUB-004", "studyName": "Trial X"}
    assert first["read"] is False
    # UTC +00:00 preserved as the local record timestamp.
    assert first["createdAt"].startswith("2026-09-08T10:00:00")

    second = by_id["NOTIF-a2"]
    assert second["read"] is True
    assert second["studyCode"] == ""
    assert second["actorName"] == "System"


def test_sync_is_idempotent_by_client_key(client):
    _login_admin(client)

    record = _sample_record(id="NOTIF-stable")
    res = client.post("/api/notifications/sync", json={"notifications": [record]})
    assert res.json()["created"] == 1

    # Re-sync the same record: updated in place, never duplicated.
    res = client.post("/api/notifications/sync", json={"notifications": [record]})
    assert res.status_code == 200, res.text
    assert res.json() == {"created": 0, "updated": 1, "skipped": []}

    res = client.get("/api/notifications")
    assert len(res.json()) == 1

    # An updated copy of the same record refreshes fields.
    updated = {**record, "read": True, "message": "Edited body"}
    res = client.post("/api/notifications/sync", json={"notifications": [updated]})
    assert res.json()["updated"] == 1

    res = client.get("/api/notifications")
    row = res.json()[0]
    assert row["message"] == "Edited body"
    assert row["read"] is True


def test_partial_sync_preserves_unmentioned_fields(client):
    """Patch semantics: a bare read-state push must not wipe actor/type/study
    metadata the record did not carry (regression from a live Postgres test
    where a partial resync cleared actor_name / notification_type)."""
    _login_admin(client)

    full = _sample_record(id="NOTIF-full")
    res = client.post("/api/notifications/sync", json={"notifications": [full]})
    assert res.json()["created"] == 1

    # Partial update: only id + read (a read-state-only push).
    res = client.post(
        "/api/notifications/sync",
        json={"notifications": [{"id": "NOTIF-full", "read": True}]},
    )
    assert res.status_code == 200, res.text
    assert res.json()["updated"] == 1

    res = client.get("/api/notifications")
    row = res.json()[0]
    assert row["read"] is True
    # Fields the partial payload did not mention are preserved.
    assert row["actorName"] == "Jane Doe"
    assert row["actorRole"] == "PI"
    assert row["studyCode"] == "STUDY-X"
    assert row["type"] == "subject_added"
    assert row["message"] == "Subject SUB-004 was added to STUDY-X by Jane - PI."


def test_rows_are_per_recipient(client):
    _login_admin(client)
    _, other_email = _seed_user("SiteStaff", "ntf-other")

    res = client.post(
        "/api/notifications/sync",
        json={"notifications": [_sample_record(id="NOTIF-admin")]},
    )
    assert res.json()["created"] == 1

    # The second user sees none of the admin's rows.
    _login(client, other_email)
    res = client.get("/api/notifications")
    assert res.json() == []

    # ...and cannot read/mark the admin's row.
    res = client.post("/api/notifications/1/read", json={"read": True})
    assert res.status_code == 404, res.text


def test_read_endpoint_toggles_read_state(client):
    _login_admin(client)
    res = client.post(
        "/api/notifications/sync",
        json={"notifications": [_sample_record(id="NOTIF-read")]},
    )
    row = client.get("/api/notifications").json()[0]
    notification_id = row["backendId"]
    assert row["read"] is False

    res = client.post(f"/api/notifications/{notification_id}/read", json={"read": True})
    assert res.status_code == 200, res.text
    assert res.json()["read"] is True

    res = client.get("/api/notifications")
    assert res.json()[0]["read"] is True

    # Unread toggles back.
    res = client.post(
        f"/api/notifications/{notification_id}/read", json={"read": False}
    )
    assert res.json()["read"] is False
    assert client.get("/api/notifications").json()[0]["read"] is False


def test_sync_validates_payload(client):
    _login_admin(client)

    # Non-list payload.
    res = client.post("/api/notifications/sync", json={"notifications": {}})
    assert res.status_code == 400, res.text

    # Records without a stable key or a title are skipped, not fatal.
    res = client.post(
        "/api/notifications/sync",
        json={
            "notifications": [
                {"message": "no id no title"},
                {"id": "NOTIF-ok", "title": "Valid"},
                {"id": "NOTIF-empty-title", "title": "  "},
                "not-an-object",
            ]
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["created"] == 1
    reasons = {entry["reason"] for entry in body["skipped"]}
    assert "missing-id" in reasons
    assert "missing-title" in reasons
    assert "not-an-object" in reasons
