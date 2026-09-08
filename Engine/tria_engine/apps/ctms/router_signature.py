# tria_engine/apps/ctms/router_signature.py
#
# Electronic-signature surfaces:
#
#   POST /api/audit/signatures                    — append one completed
#                                                   signature to the
#                                                   ctms_electronic_signature
#                                                   ledger (the fail-soft
#                                                   backend mirror the
#                                                   frontend signEntity()
#                                                   already POSTs to).
#   GET  /api/signature-requests                  — list multi-signer
#                                                   signature requests.
#   POST /api/signature-requests                  — create a request +
#                                                   its signers.
#   GET  /api/signature-requests/{id}             — one request + signers.
#   POST /api/signature-requests/{id}/sign        — the current user signs
#                                                   (marks their signer row
#                                                   complete, appends an
#                                                   ESignature ledger row).
#
# The request tables (ctms_signature_requests / ctms_signature_request_signers)
# are the fully-normalized v2 tables already defined in the SQL package; the
# ledger uses the single-signature ctms_electronic_signature table from
# apps/eisf/models.py.

from __future__ import annotations

from datetime import datetime, timezone as _tz

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..accounts.dependencies import get_current_user
from ..accounts.models import User
from ..accounts.rbac import enforce, resolve_role
from ...core.database import get_db
from ..eisf.models import ESignature
from .common import CtmsError, guarded, iso_now
from .models import CtmsSignatureRequest, CtmsSignatureRequestSigner

router = APIRouter(prefix="/api/signature-requests", tags=["signature-requests"])
audit_router = APIRouter(prefix="/api/audit", tags=["audit"])


def _signer_payload(row: CtmsSignatureRequestSigner) -> dict:
    return {
        "signerId": row.signer_id,
        "requestId": row.request_id,
        "userId": row.user_id,
        "signerName": row.signer_name,
        "signerRole": row.signer_role,
        "status": row.status,
        "meaning": row.meaning,
        "signedAt": row.signed_at.isoformat() if row.signed_at else None,
        "verificationStatus": row.verification_status,
    }


def _request_payload(db: Session, row: CtmsSignatureRequest) -> dict:
    signers = (
        db.execute(
            select(CtmsSignatureRequestSigner)
            .where(CtmsSignatureRequestSigner.request_id == row.request_id)
            .order_by(CtmsSignatureRequestSigner.signer_id)
        )
        .scalars()
        .all()
    )
    return {
        "requestId": row.request_id,
        "documentId": row.document_id,
        "studyId": row.study_id,
        "requestedBy": row.requested_by,
        "title": row.title,
        "status": row.status,
        "sentAt": row.sent_at.isoformat() if row.sent_at else None,
        "expiresAt": row.expires_at.isoformat() if row.expires_at else None,
        "completedAt": row.completed_at.isoformat() if row.completed_at else None,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "signers": [_signer_payload(s) for s in signers],
    }


# ---------------------------------------------------------------------------
# /api/audit/signatures — append-only signature ledger
# ---------------------------------------------------------------------------


@audit_router.post("/signatures")
def record_signature(
    body: dict,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Append one completed signature to the ctms_electronic_signature ledger.

    Mirrors the payload the frontend signEntity() already POSTs
    ({actionKey, entityType, entityName, meta, signature}). The signature's
    meaning + SHA-256 stamp are preserved so the ledger is a defensible
    21 CFR Part 11 audit trail, not just a name + timestamp.
    """
    def _record():
        signature = body.get("signature") or {}
        stamp = str(signature.get("signatureStamp") or "")
        meaning = str(body.get("meaning") or signature.get("meaning") or "approval")
        signed_at = str(signature.get("signedAt") or "") or iso_now()
        row = ESignature(
            document_code=str(body.get("entityName") or body.get("entityType") or ""),
            document_type=str(body.get("entityType") or "generic"),
            signer_user_id=user.id if user else None,
            signer_name=str(signature.get("printedName") or "") or (user.username if user else ""),
            signer_role=resolve_role(user) or "",
            meaning=meaning,
            signature_stamp=stamp,
            signed_at=_parse_iso(signed_at) or datetime.now(_tz.utc).replace(tzinfo=None),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {
            "id": row.id,
            "actionKey": body.get("actionKey") or "",
            "entityType": row.document_type,
            "entityName": row.document_code,
            "meaning": row.meaning,
            "signatureStamp": row.signature_stamp,
            "signedAt": row.signed_at.isoformat() if row.signed_at else None,
            "recordedAt": iso_now(),
        }

    return guarded(_record)


def _parse_iso(value: str):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Multi-signer signature requests
# ---------------------------------------------------------------------------


@router.get("")
@router.get("/")
def list_signature_requests(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    def _list():
        rows = (
            db.execute(
                select(CtmsSignatureRequest).order_by(CtmsSignatureRequest.created_at.desc())
            )
            .scalars()
            .all()
        )
        return [_request_payload(db, row) for row in rows]

    return guarded(_list)


@router.post("")
@router.post("/")
def create_signature_request(
    body: dict,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a signature request for one-or-more signers.

    Body: { documentId: number, studyId?: number, title?: string,
            signers: [{ userId, signerName, signerRole? }] }
    """
    enforce(user, "eisf", "sign")

    def _create():
        document_id = body.get("documentId")
        if document_id is None:
            raise CtmsError("documentId is required.", status=400)
        signers = body.get("signers") or []
        if not isinstance(signers, list) or len(signers) == 0:
            raise CtmsError("At least one signer is required.", status=400)

        now = datetime.now(_tz.utc).replace(tzinfo=None)
        row = CtmsSignatureRequest(
            document_id=int(document_id),
            study_id=int(body["studyId"]) if body.get("studyId") is not None else None,
            requested_by=user.id,
            title=str(body.get("title") or "")[:500],
            status=str(body.get("status") or "DRAFT")[:50],
            sent_at=now if str(body.get("status") or "").upper() == "SENT" else None,
            created_at=now,
        )
        db.add(row)
        # The first flush inserts the request row — the SQL package's FK to
        # ctms_documents / ctms_studies is checked here, so the IntegrityError
        # can surface at flush OR commit. Wrap both so an unknown document /
        # study / signer returns a clean 400 instead of a raw 500.
        try:
            db.flush()
            for signer in signers:
                if signer.get("userId") is None or not str(signer.get("signerName") or "").strip():
                    raise CtmsError("Each signer needs userId and signerName.", status=400)
                db.add(
                    CtmsSignatureRequestSigner(
                        request_id=row.request_id,
                        user_id=int(signer["userId"]),
                        signer_role=str(signer.get("signerRole") or "")[:100] or None,
                        signer_name=str(signer["signerName"]).strip()[:255],
                        status="PENDING",
                    )
                )
            db.commit()
        except IntegrityError:
            db.rollback()
            raise CtmsError(
                "The referenced document, study or signer does not exist.",
                status=400,
            )
        db.refresh(row)
        return _request_payload(db, row)

    return guarded(_create)


@router.get("/{request_id}")
def get_signature_request(
    request_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    def _detail():
        row = db.get(CtmsSignatureRequest, request_id)
        if row is None:
            raise CtmsError("Signature request not found.", status=404)
        return _request_payload(db, row)

    return guarded(_detail)


@router.post("/{request_id}/sign")
def sign_signature_request(
    request_id: int,
    body: dict,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """The current user signs the request: marks their signer row complete
    and appends one ESignature ledger row. When every signer has signed the
    request is marked completed."""
    enforce(user, "eisf", "sign")

    def _sign():
        req = db.get(CtmsSignatureRequest, request_id)
        if req is None:
            raise CtmsError("Signature request not found.", status=404)
        signer = (
            db.execute(
                select(CtmsSignatureRequestSigner).where(
                    CtmsSignatureRequestSigner.request_id == request_id,
                    CtmsSignatureRequestSigner.user_id == user.id,
                )
            )
            .scalars()
            .first()
        )
        if signer is None:
            raise CtmsError("You are not a signer on this request.", status=403)
        if signer.status.upper() == "SIGNED":
            raise CtmsError("You have already signed this request.", status=400)

        meaning = str(body.get("meaning") or "approval")
        stamp = str((body.get("signature") or {}).get("signatureStamp") or body.get("signatureStamp") or "")
        signed_at = str((body.get("signature") or {}).get("signedAt") or body.get("signedAt") or "") or iso_now()

        signer.status = "SIGNED"
        signer.meaning = meaning
        signer.signed_at = _parse_iso(signed_at) or datetime.now(_tz.utc).replace(tzinfo=None)
        # Best-effort verification marker: a SHA-256 stamp means the payload
        # was stamped client-side; a real cryptographic verification pass runs
        # through the eISF verify-integrity surface.
        signer.verification_status = "verified" if stamp else "recorded"
        db.add(signer)

        db.add(
            ESignature(
                document_code=f"sigreq:{request_id}",
                document_type="signature_request",
                signer_user_id=user.id,
                signer_name=str((body.get("signature") or {}).get("printedName") or "") or (user.username or ""),
                signer_role=resolve_role(user) or "",
                meaning=meaning,
                signature_stamp=stamp,
                signed_at=signer.signed_at,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
        )
        # The session is configured with autoflush=False — flush the signer
        # update before the pending-count query below sees the DB.
        db.flush()

        pending = (
            db.execute(
                select(CtmsSignatureRequestSigner).where(
                    CtmsSignatureRequestSigner.request_id == request_id,
                    CtmsSignatureRequestSigner.status != "SIGNED",
                )
            )
            .scalars()
            .first()
        )
        if pending is None:
            req.status = "COMPLETED"
            req.completed_at = datetime.now(_tz.utc).replace(tzinfo=None)
            db.add(req)
        db.commit()
        return _request_payload(db, req)

    return guarded(_sign)