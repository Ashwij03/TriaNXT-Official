# tria_engine/apps/eisf/router.py
#
# eISF regulatory document repository REST surface, mounted at /api/eisf:
#
#   GET    /api/eisf/documents            list (study/site/folder/status filters)
#   GET    /api/eisf/documents/{code}     one document + version history
#   POST   /api/eisf/documents            create/upload (signature required)
#   PUT    /api/eisf/documents/{code}     update/replace — new version (signature required)
#   DELETE /api/eisf/documents/{code}     delete (signature required, Admin only)
#   POST   /api/eisf/documents/{code}/approve|reject|archive|expire   status transitions
#   GET    /api/eisf/structure            canonical folder/category taxonomy
#
# Every write endpoint enforces RBAC (enforce(user, "eisf", action)) before
# proceeding; reads are authenticated + org/study-scoped like every other
# module (no explicit "read" action, per the existing matrix convention).

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ...apps.accounts.dependencies import get_current_user
from ...apps.accounts.models import User
from ...apps.accounts.rbac import enforce
from ...core.database import get_db
from ..ctms.common import CtmsError, guarded, load_row
from .models import EisfDocument
from .services import (
    _content_bytes,
    _stored_bytes,
    basename_for_download,
    create_document,
    delete_document,
    get_document,
    issue_download_token,
    list_documents,
    list_signatures,
    resolve_download_token,
    set_document_status,
    sign_document,
    update_document,
    verify_document_integrity,
)
from .structure import EISF_STRUCTURE

router = APIRouter(prefix="/api/eisf", tags=["eisf"])


@router.get("/structure")
def eisf_structure(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Canonical binder taxonomy (mirrors the frontend EISFMenuConfig)."""
    return EISF_STRUCTURE


@router.get("/documents")
@router.get("/documents/")
def eisf_document_list(
    request: Request,
    study: str | None = None,
    site: str | None = None,
    folder: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    def _list():
        return list_documents(
            db, user, study=study, site=site, folder=folder, status=status
        )

    return guarded(_list)


@router.get("/documents/{code}")
def eisf_document_detail(
    code: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    def _detail():
        return get_document(db, user, code)

    return guarded(_detail)


@router.post("/documents")
@router.post("/documents/")
def eisf_document_create(
    body: dict,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    enforce(user, "eisf", "create")
    enforce(user, "eisf", "sign")

    def _create():
        return create_document(db, user, body)

    return guarded(_create)


@router.put("/documents/{code}")
def eisf_document_update(
    code: str,
    body: dict,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    enforce(user, "eisf", "update")
    enforce(user, "eisf", "sign")

    def _update():
        return update_document(db, user, code, body)

    return guarded(_update)


@router.delete("/documents/{code}")
def eisf_document_delete(
    code: str,
    body: dict | None = None,
    request: Request = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    enforce(user, "eisf", "delete")
    enforce(user, "eisf", "sign")

    def _delete():
        return delete_document(db, user, code, body or {})

    return guarded(_delete)


def _status_action(action: str):
    def _handler(
        code: str,
        body: dict | None = None,
        request: Request = None,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ):
        enforce(user, "eisf", "update")

        def _transition():
            return set_document_status(db, user, code, action)

        return guarded(_transition)

    return _handler


router.add_api_route(
    "/documents/{code}/approve",
    _status_action("approve"),
    methods=["POST"],
    summary="Approve an eISF document",
)
router.add_api_route(
    "/documents/{code}/reject",
    _status_action("reject"),
    methods=["POST"],
    summary="Reject an eISF document",
)
router.add_api_route(
    "/documents/{code}/archive",
    _status_action("archive"),
    methods=["POST"],
    summary="Archive an eISF document",
)
router.add_api_route(
    "/documents/{code}/expire",
    _status_action("expire"),
    methods=["POST"],
    summary="Mark an eISF document expired",
)


# ---------------------------------------------------------------------------
# Part 11 signing / integrity / signed downloads
# ---------------------------------------------------------------------------


def _load_document_row(db: Session, user: User, code: str) -> EisfDocument:
    row, _ = load_row(db, EisfDocument, user, code, "Document not found.")
    return row


@router.post("/documents/{code}/sign")
def eisf_document_sign(
    code: str,
    body: dict,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Record one completed electronic signature for a document. When the
    client supplies `signature_stamp`, it is verified against a
    server-recomputed SHA-256 before the signature is accepted."""
    enforce(user, "eisf", "sign")

    def _sign():
        row = _load_document_row(db, user, code)
        signature = sign_document(
            db,
            user,
            dict(row.data),
            meaning=str(body.get("meaning") or "approval"),
            signature_stamp=body.get("signature_stamp"),
            signed_at=body.get("signedAt") or body.get("signed_at"),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return {
            "id": signature.id,
            "documentCode": signature.document_code,
            "signerName": signature.signer_name,
            "signerRole": signature.signer_role,
            "meaning": signature.meaning,
            "signatureStamp": signature.signature_stamp,
            "signedAt": signature.signed_at.isoformat() if signature.signed_at else None,
        }

    return guarded(_sign)


@router.get("/documents/{code}/signatures")
def eisf_document_signatures(
    code: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    def _signatures():
        row = _load_document_row(db, user, code)
        return list_signatures(db, dict(row.data))

    return guarded(_signatures)


@router.get("/documents/{code}/verify-integrity")
def eisf_document_verify_integrity(
    code: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    def _verify():
        row = _load_document_row(db, user, code)
        return verify_document_integrity(db, dict(row.data))

    return guarded(_verify)


@router.get("/documents/{code}/download-token")
def eisf_document_download_token(
    code: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    def _token():
        row = _load_document_row(db, user, code)
        token = issue_download_token(db, user, dict(row.data))
        import time as _t

        # expiresAt mirrors the default TTL used by issue_download_token.
        return {"token": token, "expiresAt": int(_t.time()) + 300}

    return guarded(_token)


@router.get("/documents/{code}/download")
def eisf_document_download(
    code: str,
    request: Request,
    token: str = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Stream a document's stored content. A valid, non-expired signed
    download token is required (403 otherwise)."""
    from fastapi.responses import JSONResponse

    try:
        row = _load_document_row(db, user, code)
    except CtmsError as exc:
        return JSONResponse({"message": exc.message}, status_code=exc.status)
    document = dict(row.data)
    try:
        resolve_download_token(document.get("id") or code, token, user)
    except CtmsError as exc:
        return JSONResponse({"message": exc.message}, status_code=exc.status)
    content = _stored_bytes(document) or _content_bytes(document)
    filename = basename_for_download(document)
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )