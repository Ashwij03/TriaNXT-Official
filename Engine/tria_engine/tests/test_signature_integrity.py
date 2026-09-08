# tria_engine/tests/test_signature_integrity.py
#
# Part 11 e-signature integrity (Section 4.1) + multi-signer signature
# requests (Section 5.3):
#   * POST /api/eisf/documents/{code}/sign — accepts a valid SHA-256 stamp,
#     rejects a mismatched stamp with 400.
#   * GET  /api/eisf/documents/{code}/signatures
#   * GET  /api/eisf/documents/{code}/verify-integrity — valid:false once
#     the stored content is altered after signing.
#   * GET  /api/eisf/documents/{code}/download-token + /download — valid
#     non-expired token streams the content; invalid/expired tokens are 403.
#   * POST /api/audit/signatures — appends to the signature ledger.
#   * POST /api/signature-requests/... — multi-signer request lifecycle.

from __future__ import annotations

import uuid

from tria_engine.apps.eisf.services import build_signature_stamp
from tria_engine.apps.accounts.models import User
from tria_engine.apps.organizations.models import Organization, Role
from tria_engine.core.database import SessionLocal
from tria_engine.core.security import hash_password


PASSWORD = "RolePass123!"


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


def _admin(client):
    res = client.post(
        "/api/accounts/login/",
        json={"email": "admin@test.local", "password": "AdminPass123!"},
    )
    assert res.status_code == 200, res.text
    return client


def _create_document(client, code: str | None = None) -> dict:
    payload = {
        "documentName": "Informed Consent Form",
        "studyCode": "STUDY-SIG",
        "siteCode": "SITE-01",
        "category": "ICF",
        "folderId": "icf",
        "version": "1.0",
        "status": "Draft",
        "signature": {"printedName": "Admin User", "signedAt": "2026-09-08T09:00:00.000Z"},
    }
    if code:
        payload["documentName"] = code
    res = client.post("/api/eisf/documents", json=payload)
    assert res.status_code == 200, res.text
    return res.json()


def test_sign_document_with_valid_stamp(client):
    _admin(client)
    doc = _create_document(client)
    code = doc["id"]

    # Compute the server-side canonical stamp over the SAME payload the
    # frontend createActionSignature would produce (actionKey eisf:sign,
    # entityType eisf_document, meta {documentCode, version}, signedAt).
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "admin").first()
        # Build the stamp while the session is open (role is a lazy relation).
        signed_at = "2026-09-08T10:30:00.000Z"
        expected = build_signature_stamp(
            document=doc, user=user, meaning="approval", timestamp=signed_at
        )
    finally:
        db.close()

    res = client.post(
        f"/api/eisf/documents/{code}/sign",
        json={"meaning": "approval", "signature_stamp": expected, "signedAt": signed_at},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["meaning"] == "approval"
    assert body["signatureStamp"] == expected
    assert body["signerName"]

    # The stamp is a real SHA-256 hex digest (64 chars), not the raw name.
    assert len(expected) == 64
    assert expected != "Admin User"

    # Signatures list includes the row.
    res = client.get(f"/api/eisf/documents/{code}/signatures")
    assert res.status_code == 200, res.text
    assert any(s["signatureStamp"] == expected for s in res.json())


def test_sign_document_rejects_mismatched_stamp(client):
    _admin(client)
    doc = _create_document(client)
    res = client.post(
        f"/api/eisf/documents/{doc['id']}/sign",
        json={"meaning": "approval", "signature_stamp": "0" * 64},
    )
    assert res.status_code == 400, res.text
    assert "verification failed" in res.json()["message"]


def test_verify_integrity_detects_tampering(client):
    _admin(client)
    doc = _create_document(client)
    code = doc["id"]

    res = client.get(f"/api/eisf/documents/{code}/verify-integrity")
    assert res.status_code == 200, res.text
    assert res.json()["valid"] is True
    assert res.json()["expected_hash"] == res.json()["actual_hash"]

    # Tamper with the stored row directly (bypassing the service layer so the
    # recorded content hash is NOT refreshed — a real tampering scenario).
    from tria_engine.apps.eisf.models import EisfDocument

    db = SessionLocal()
    try:
        row = db.query(EisfDocument).filter(EisfDocument.code == code).first()
        data = dict(row.data)
        data["documentName"] = "TAMPERED - altered after signing"
        row.data = data
        db.add(row)
        db.commit()
    finally:
        db.close()

    res = client.get(f"/api/eisf/documents/{code}/verify-integrity")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["valid"] is False
    assert body["expected_hash"] != body["actual_hash"]


def test_download_requires_valid_token(client):
    _admin(client)
    doc = _create_document(client)
    code = doc["id"]

    res = client.get(f"/api/eisf/documents/{code}/download")
    assert res.status_code in (400, 422)  # missing/invalid token rejected

    res = client.get(f"/api/eisf/documents/{code}/download", params={"token": "garbage"})
    assert res.status_code == 403, res.text

    res = client.get(f"/api/eisf/documents/{code}/download-token")
    assert res.status_code == 200, res.text
    token = res.json()["token"]

    res = client.get(f"/api/eisf/documents/{code}/download", params={"token": token})
    assert res.status_code == 200, res.text
    assert "Content-Disposition" in res.headers

    # A token for another document must not work.
    other = _create_document(client, "Other-Doc")
    res = client.get(
        f"/api/eisf/documents/{other['id']}/download", params={"token": token}
    )
    assert res.status_code == 403, res.text


def test_audit_signatures_ledger(client):
    _admin(client)
    res = client.post(
        "/api/audit/signatures",
        json={
            "actionKey": "document:delete",
            "entityType": "eisf_document",
            "entityName": "ICF v2",
            "meta": {"studyId": "STUDY-SIG"},
            "meaning": "approval",
            "signature": {
                "printedName": "Admin User",
                "signatureStamp": "a" * 64,
                "signedAt": "2026-09-08T11:00:00.000Z",
                "meaning": "approval",
            },
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["meaning"] == "approval"
    assert body["signatureStamp"] == "a" * 64
    assert body["actionKey"] == "document:delete"


def test_signature_request_lifecycle(client):
    _admin(client)
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        admin_id = admin.id
        admin_name = admin.username
    finally:
        db.close()
    staff_id, _staff_email = _seed_user("SiteStaff", "sigstaff")

    # Create a request for two signers (admin + a seeded Site Staff user).
    res = client.post(
        "/api/signature-requests/",
        json={
            "documentId": 42,
            "studyId": 7,
            "title": "Approve ICF v2",
            "signers": [
                {"userId": admin_id, "signerName": admin_name, "signerRole": "ADMIN"},
                {"userId": staff_id, "signerName": "SiteStaff User", "signerRole": "SITE_STAFF"},
            ],
        },
    )
    assert res.status_code == 200, res.text
    request = res.json()
    assert request["status"] == "DRAFT"
    assert len(request["signers"]) == 2

    # List includes it.
    res = client.get("/api/signature-requests/")
    assert res.status_code == 200, res.text
    assert any(r["requestId"] == request["requestId"] for r in res.json())

    # Signing once marks ONE signer row complete (the request stays open).
    res = client.post(
        f"/api/signature-requests/{request['requestId']}/sign",
        json={
            "meaning": "review",
            "signature": {
                "printedName": admin_name,
                "signatureStamp": "b" * 64,
                "signedAt": "2026-09-08T12:00:00.000Z",
            },
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "DRAFT"
    signed = [s for s in body["signers"] if s["status"] == "SIGNED"]
    assert len(signed) == 1

    # The Site Staff signer signs too — request completes.
    _login_staff = client.post(
        "/api/accounts/login/",
        json={"email": _staff_email, "password": PASSWORD},
    )
    assert _login_staff.status_code == 200, _login_staff.text
    res = client.post(
        f"/api/signature-requests/{request['requestId']}/sign",
        json={"meaning": "review", "signature": {"printedName": "SiteStaff User"}},
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "COMPLETED"

    # Back to admin for the final assertions.
    _admin(client)

    # Signing a third time is rejected.
    res = client.post(
        f"/api/signature-requests/{request['requestId']}/sign",
        json={"meaning": "review"},
    )
    assert res.status_code == 400, res.text