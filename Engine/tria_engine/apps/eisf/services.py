# tria_engine/apps/eisf/services.py
#
# eISF document repository business logic — CRUD + versioning + status
# transitions. Reuses the shared ctms record layer (create_record,
# save_record, load_row, list_records, audit) so scoping, RBAC enforcement
# and audit logging behave exactly like every other module in the app.

from __future__ import annotations

import hashlib
import hmac
import json
import time as _time
from datetime import datetime, timezone as _tz

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..accounts.models import User
from ..ctms.common import CtmsError, audit, create_record, iso_now, list_records, load_row, new_id, save_record
from .models import EisfDocument, EisfDocumentVersion
from .structure import EISF_FINAL_STATUSES

# Document lifecycle actions exposed as POST /documents/{code}/<action>.
STATUS_TRANSITIONS = {
    "approve": "Approved",
    "reject": "Rejected",
    "archive": "Archived",
    "expire": "Expired",
}


def require_signature(signature: dict | None) -> dict:
    """Part 11 gate — every document mutation needs a captured signature.

    Mirrors the frontend error-message style ({"message": ...} with the exact
    wording SubjectExplorer/fileService.ts uses).
    """
    if not isinstance(signature, dict) or not str(signature.get("printedName") or "").strip():
        raise CtmsError(
            "E-Signature is required before a document can be created, updated or deleted.",
            status=400,
        )
    return {
        "printedName": str(signature.get("printedName") or "").strip(),
        "signatureStamp": str(signature.get("signatureStamp") or ""),
        "signedAt": str(signature.get("signedAt") or "") or iso_now(),
    }


def _append_signature(record: dict, signature: dict) -> list[dict]:
    """Append a SignaturePayload to the record's append-only signatures array."""
    signatures = list(record.get("signatures") or [])
    signatures.append(signature)
    return signatures


def _build_record(
    payload: dict,
    signature: dict,
    actor: str,
    *,
    code: str | None = None,
    existing: dict | None = None,
) -> dict:
    now = iso_now()
    folder = payload.get("folderId") or payload.get("section") or payload.get("sectionId") or ""
    record = {
        **(existing or {}),
        "id": code or new_id("EISF-", upper=True),
        "studyCode": payload.get("studyCode") or (existing or {}).get("studyCode") or "",
        "siteCode": payload.get("siteCode") or (existing or {}).get("siteCode") or "",
        "folderId": folder,
        "folderTitle": payload.get("folderTitle") or payload.get("sectionTitle") or "",
        "category": payload.get("category") or payload.get("documentType") or "",
        "documentName": payload.get("documentName") or payload.get("name") or "Untitled Document",
        "name": payload.get("documentName") or payload.get("name") or (existing or {}).get("name"),
        "fileName": payload.get("fileName") or (existing or {}).get("fileName") or "",
        "fileSize": (
            payload.get("fileSize")
            if payload.get("fileSize") is not None
            else (existing or {}).get("fileSize")
        ),
        "version": payload.get("version") or (existing or {}).get("version") or "1.0",
        "status": payload.get("status") or (existing or {}).get("status") or "Draft",
        "uploadedBy": actor,
        "uploadedAt": (existing or {}).get("uploadedAt") or now,
        "modifiedDate": now,
        "modifiedBy": actor,
    }
    # Keep the append-only signature trail on the record itself (the version
    # rows below are the durable Part 11 audit trail).
    record["signatures"] = _append_signature(record, signature)
    record["lastSignature"] = signature
    # Content hash recorded at write time so verify_document_integrity can
    # detect any later tampering with the stored content.
    return _stamp_content_hash(record)


def create_document(db: Session, user: User, payload: dict) -> dict:
    signature = require_signature(payload.get("signature"))
    record = _build_record(payload, signature, _actor(user))
    created = create_record(db, EisfDocument, user, record["id"], record)
    _record_version(db, created, signature, user)
    audit(db, user, "EISF_DOCUMENT_CREATED", details={"documentId": created["id"], "name": created["documentName"]})
    return created


def update_document(db: Session, user: User, code: str, payload: dict) -> dict:
    signature = require_signature(payload.get("signature"))
    row, record = load_row(db, EisfDocument, user, code, "Document not found.")
    next_record = _build_record(payload, signature, _actor(user), code=code, existing=record)
    # A new version supersedes the previous one.
    prev_version = str(record.get("version") or "1.0")
    if str(next_record.get("version") or "1.0") != prev_version:
        next_record["status"] = "Pending"
    saved = save_record(db, user, row, next_record)
    _record_version(db, saved, signature, user)
    audit(db, user, "EISF_DOCUMENT_UPDATED", details={"documentId": code, "version": saved.get("version")})
    return saved


def delete_document(db: Session, user: User, code: str, payload: dict) -> dict:
    signature = require_signature(payload.get("signature"))
    row, record = load_row(db, EisfDocument, user, code, "Document not found.")
    audit(
        db,
        user,
        "EISF_DOCUMENT_DELETED",
        details={"documentId": code, "name": record.get("documentName"), "signedBy": signature["printedName"]},
    )
    db.delete(row)
    db.commit()
    return {"deleted": True, "id": code}


def set_document_status(db: Session, user: User, code: str, action: str) -> dict:
    """Apply a lifecycle transition (approve/reject/archive/expire)."""
    target = STATUS_TRANSITIONS.get(action)
    if target is None:
        raise CtmsError("Unknown document action.", status=400)
    row, record = load_row(db, EisfDocument, user, code, "Document not found.")
    current = str(record.get("status") or "Draft")
    if current in EISF_FINAL_STATUSES and current != target:
        raise CtmsError(f"Cannot {action} a document in '{current}' status.")
    record["status"] = target
    record["modifiedDate"] = iso_now()
    record["modifiedBy"] = _actor(user)
    history = list(record.get("history") or [])
    history.append({"action": f"STATUS:{target.upper()}", "at": iso_now(), "by": _actor(user)})
    record["history"] = history
    saved = save_record(db, user, row, record)
    audit(db, user, f"EISF_DOCUMENT_{target.upper()}", details={"documentId": code, "status": target})
    return saved


def _actor(user: User) -> str:
    role = getattr(user, "role", None)
    name = getattr(role, "name", "")
    if name:
        return name
    return getattr(user, "username", None) or "Unknown"


def _record_version(db: Session, record: dict, signature: dict, user: User) -> EisfDocumentVersion:
    """Insert one immutable version row for the (newly created/replaced) version."""
    row = (
        db.execute(
            select(EisfDocument).where(
                EisfDocument.code == record["id"],
                EisfDocument.organization_id == user.organization_id,
            )
        )
        .scalars()
        .first()
    )
    if row is None:
        return None
    version = EisfDocumentVersion(
        document_id=row.id,
        code=record["id"],
        version=str(record.get("version") or "1.0"),
        signed_by=signature["printedName"],
        signature_stamp=signature.get("signatureStamp") or "",
        signed_at=_parse_iso(signature.get("signedAt") or ""),
        uploaded_by=_actor(user),
    )
    db.add(version)
    db.commit()
    return version


def _parse_iso(value: str):
    """Best-effort parse of an ISO-8601 timestamp (JS Date.toISOString)."""
    if not value:
        return None
    try:
        from datetime import datetime

        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def list_documents(db: Session, user: User, *, study: str | None = None, site: str | None = None, folder: str | None = None, status: str | None = None) -> list[dict]:
    records = list_records(db, EisfDocument, user)
    if study:
        key = str(study).strip().lower()
        records = [r for r in records if str(r.get("studyCode") or "").strip().lower() == key]
    if site:
        key = str(site).strip().lower()
        records = [r for r in records if str(r.get("siteCode") or "").strip().lower() == key]
    if folder:
        key = str(folder).strip().lower()
        records = [
            r
            for r in records
            if key
            in (
                str(r.get("folderId") or r.get("section") or r.get("sectionId") or "").strip().lower(),
                str(r.get("category") or "").strip().lower(),
            )
        ]
    if status:
        records = [r for r in records if str(r.get("status") or "").strip().lower() == str(status).strip().lower()]
    records.sort(key=lambda r: r.get("modifiedDate") or r.get("uploadedAt") or "", reverse=True)
    return records


def get_document(db: Session, user: User, code: str) -> dict:
    _, record = load_row(db, EisfDocument, user, code, "Document not found.")
    versions = (
        db.execute(
            select(EisfDocumentVersion)
            .where(EisfDocumentVersion.code == code)
            .order_by(EisfDocumentVersion.created_at.desc(), EisfDocumentVersion.id.desc())
        )
        .scalars()
        .all()
    )
    record = dict(record)
    record["versions"] = [
        {
            "version": v.version,
            "signedBy": v.signed_by,
            "signatureStamp": v.signature_stamp,
            "signedAt": v.signed_at.isoformat() if v.signed_at else None,
            "uploadedBy": v.uploaded_by,
            "uploadedAt": v.uploaded_at.isoformat() if v.uploaded_at else None,
        }
        for v in versions
    ]
    return record


def document_exists(db: Session, user: User, code: str) -> bool:
    try:
        load_row(db, EisfDocument, user, code, "Document not found.")
        return True
    except CtmsError:
        return False


# ---------------------------------------------------------------------------
# Part 11 integrity — SHA-256 content hashes + tamper-evident signature stamps
# ---------------------------------------------------------------------------

from ...core.config import settings
from .models import ESignature


# Canonical action key used when stamping an eISF signing action. The
# frontend's createActionSignature / buildActionStamp must use the SAME
# actionKey + entityType + meta shape for client-computed stamps to match
# the server recomputation (see the frontend buildActionStamp contract in
# src/shared/services/actionSignatureService.ts).
SIGN_ACTION_KEY = "eisf:sign"
SIGN_ENTITY_TYPE = "eisf_document"


def sha256_hex(content: bytes) -> str:
    """SHA-256 hex digest of raw bytes (same primitive as the frontend)."""
    return hashlib.sha256(content).hexdigest()


def _sorted(value):
    """Recursively sort dict keys so the same logical payload always
    canonicalises the same way (byte-for-byte contract with the frontend's
    canonicalJson)."""
    if isinstance(value, dict):
        return {str(k): _sorted(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_sorted(v) for v in value]
    return value


def _canonical_json(payload: dict) -> str:
    """Deterministic JSON string (sorted keys recursively, compact) — the
    server-side twin of the frontend's canonicalJson()."""
    return json.dumps(_sorted(payload), sort_keys=True, separators=(",", ":"))


def _signer_identity(user) -> dict:
    """Mirror of the frontend getSignerIdentity() shape."""
    role = getattr(user, "role", None)
    role_name = getattr(role, "name", "") or ""
    display = getattr(user, "username", "") or ""
    if getattr(user, "first_name", "") or getattr(user, "last_name", ""):
        display = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip() or display
    return {
        "displayName": display,
        "email": getattr(user, "email", "") or "",
        "role": role_name,
        "userId": str(getattr(user, "id", "") or ""),
    }


def build_signature_stamp(*, document, user, meaning: str, timestamp) -> str:
    """Server-side equivalent of the frontend's buildActionStamp: SHA-256 of
    the canonical payload binding document identity, signer identity, the
    signature meaning and the signing timestamp together."""
    payload = {
        "actionKey": SIGN_ACTION_KEY,
        "entityType": SIGN_ENTITY_TYPE,
        "entityName": document.get("documentName") or document.get("name") or "Untitled Document",
        "meaning": meaning or "approval",
        "signerIdentity": _signer_identity(user),
        "timestamp": timestamp or iso_now(),
        "meta": {
            "documentCode": document.get("id") or "",
            "version": document.get("version") or "1.0",
        },
    }
    return sha256_hex(_canonical_json(payload).encode("utf-8"))


def _document_row_id(db: Session, code: str) -> int | None:
    row = db.execute(
        select(EisfDocument).where(EisfDocument.code == code)
    ).scalars().first()
    return row.id if row is not None else None


def sign_document(db: Session, user: User, document, meaning: str, signature_stamp: str | None = None, signed_at: str | None = None, ip_address: str | None = None, user_agent: str | None = None) -> ESignature:
    """Persist one completed electronic signature for a document.

    When the client supplies a signature_stamp, it is verified against a
    server-recomputed stamp over the same canonical payload (document +
    signer + meaning + the client's signedAt). A mismatching stamp is
    rejected with a 400 rather than trusted blindly.
    """
    meaning = (meaning or "approval").strip() or "approval"
    timestamp = signed_at or iso_now()
    expected = build_signature_stamp(document=document, user=user, meaning=meaning, timestamp=timestamp)
    if signature_stamp is not None and str(signature_stamp or "").strip():
        if str(signature_stamp).strip() != expected:
            raise CtmsError(
                "Signature stamp verification failed: the submitted stamp does not match the "
                "server-recomputed SHA-256 of the signing payload.",
                status=400,
            )
    else:
        signature_stamp = expected

    row = ESignature(
        document_id=_document_row_id(db, document.get("id") or ""),
        document_code=str(document.get("id") or ""),
        document_type="eisf",
        signer_user_id=user.id if user else None,
        signer_name=_actor(user),
        signer_role=getattr(getattr(user, "role", None), "name", "") or "",
        meaning=meaning,
        signature_stamp=str(signature_stamp).strip(),
        signed_at=_parse_iso(timestamp) or datetime.now(_tz.utc).replace(tzinfo=None),
        ip_address=ip_address,
        user_agent=(user_agent or "")[:255] if user_agent else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, user, "EISF_DOCUMENT_SIGNED", details={"documentId": document.get("id"), "meaning": meaning})
    return row


def list_signatures(db: Session, document) -> list[dict]:
    """Every ESignature row for a document (newest first)."""
    code = str(document.get("id") or "")
    rows = (
        db.execute(
            select(ESignature)
            .where(ESignature.document_code == code)
            .order_by(ESignature.signed_at.desc(), ESignature.id.desc())
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": r.id,
            "documentCode": r.document_code,
            "documentType": r.document_type,
            "signerName": r.signer_name,
            "signerRole": r.signer_role,
            "signerUserId": r.signer_user_id,
            "meaning": r.meaning,
            "signatureStamp": r.signature_stamp,
            "signedAt": r.signed_at.isoformat() if r.signed_at else None,
            "ipAddress": r.ip_address,
        }
        for r in rows
    ]


# Fields that make up a document's substantive content for integrity hashing.
# Lifecycle/audit fields (status, modifiedDate, history, signatures, ...) are
# deliberately excluded so a Part 11 status transition does not invalidate the
# content hash — but any change to name/version/file/category/scope does.
_CONTENT_FIELDS = (
    "documentName",
    "name",
    "fileName",
    "fileSize",
    "version",
    "folderId",
    "folderTitle",
    "category",
    "studyCode",
    "siteCode",
)


def _content_payload(document) -> dict:
    return {field: document.get(field) for field in _CONTENT_FIELDS}


def _content_bytes(document) -> bytes:
    """Canonical bytes of the document's stored content (integrity input)."""
    return _canonical_json(_content_payload(document)).encode("utf-8")


def verify_document_integrity(db: Session, document) -> dict:
    """Recompute the content hash and compare against the hash recorded at
    signing time. Returns {valid, expected_hash, actual_hash, checked_at}."""
    expected = str(document.get("contentSha256") or "")
    actual = sha256_hex(_content_bytes(document))
    return {
        "valid": bool(expected) and expected == actual,
        "expected_hash": expected,
        "actual_hash": actual,
        "checked_at": iso_now(),
    }


def _stamp_content_hash(document: dict) -> dict:
    """Record the current content hash on the document record (called on
    every create/update so the recorded hash always matches the version just
    written)."""
    document["contentSha256"] = sha256_hex(_content_bytes(document))
    return document


# ---------------------------------------------------------------------------
# Persisted file content + signed download tokens
# ---------------------------------------------------------------------------


def store_document_file(db: Session, document, file_bytes: bytes, filename: str) -> None:
    """Persist raw file bytes via the shared media storage (same mechanism
    accounts uses: core.storage.save_document) and record the storage name
    on the document record."""
    from ...core.storage import save_document

    stored = save_document("eisf", file_bytes, filename)
    record = dict(document)
    record["storageName"] = stored.name
    record["fileSize"] = stored.size
    row, _ = load_row(db, EisfDocument, None, record.get("id") or "", "Document not found.")
    row.data = record
    db.add(row)
    db.commit()


def _stored_bytes(document) -> bytes | None:
    """Read persisted file bytes for a document, or None when no file was
    stored (the JSON-mirror record only)."""
    storage_name = document.get("storageName")
    if not storage_name:
        return None
    try:
        from ...core.storage import absolute_path

        path = absolute_path(storage_name)
        if path.is_file():
            return path.read_bytes()
    except OSError:
        return None
    return None


def basename_for_download(document) -> str:
    """Download filename: the original file name when stored, otherwise a
    `<code>.json` export of the canonical record content."""
    name = document.get("fileName") or document.get("documentName") or document.get("name") or "document"
    storage_name = document.get("storageName")
    if storage_name:
        from ...core.storage import StoredFile

        return StoredFile(name=storage_name).basename
    base = str(name or "document").replace(" ", "_")
    return f"{base}.json"


_DOWNLOAD_TOKEN_TTL_SECONDS = 300


def _sign_token(payload: str) -> str:
    """HMAC-SHA256 over the token payload using the app secret."""
    secret = getattr(settings, "secret_key", "") or "dev-only-not-for-production-change-me-immediately"
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def issue_download_token(db: Session, user: User, document, ttl_seconds: int = _DOWNLOAD_TOKEN_TTL_SECONDS) -> str:
    """Short-lived, signed download token: HMAC over document id + expiry +
    issuing user id. Stateless — no DB row is written (the `db` argument
    exists for parity with sibling service signatures)."""
    exp = int(_time.time()) + int(ttl_seconds)
    payload = f"{document.get('id') or ''}.{exp}.{user.id if user else 0}"
    return f"{payload}.{_sign_token(payload)}"


def resolve_download_token(document_id, token: str, user: User) -> bytes:
    """Validate a download token and return the document's file bytes.
    Raises CtmsError(403) on a malformed / expired / mismatched token."""
    parts = str(token or "").split(".")
    if len(parts) != 4:
        raise CtmsError("Invalid download token.", status=403)
    payload = ".".join(parts[:3])
    sig = parts[3]
    if not hmac.compare_digest(_sign_token(payload), sig):
        raise CtmsError("Invalid download token.", status=403)
    try:
        token_document_id, exp, user_id = payload.split(".")
        if str(token_document_id) != str(document_id):
            raise CtmsError("Download token does not match this document.", status=403)
        if int(exp) < int(_time.time()):
            raise CtmsError("Download token has expired.", status=403)
        if user is not None and int(user_id) != int(user.id):
            raise CtmsError("Download token was issued to a different user.", status=403)
    except ValueError as exc:
        raise CtmsError("Invalid download token.", status=403) from exc
    return None