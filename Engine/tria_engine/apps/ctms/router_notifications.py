# tria_engine/apps/ctms/router_notifications.py
#
# Phase-1 v2 wiring for the frontend notificationService (MIGRATION_PLAN_V2_
# SCHEMA.md §1, §3 — notifications domain). Persists the user's notifications
# into the fully-normalized v2 `ctms_notifications` table (plus the additive
# extension columns carrying the frontend record contract):
#
#   GET  /api/notifications                — the current user's rows, newest
#                                            first (per-recipient model: a
#                                            user only ever sees their own).
#   POST /api/notifications/sync           — bulk upsert of the caller's
#                                            visible localStorage records,
#                                            idempotent by (user_id,
#                                            client_key). Fail-soft mirror:
#                                            the frontend store stays the
#                                            source of truth; this keeps the
#                                            backend durable + hydrates a
#                                            fresh device.
#   POST /api/notifications/{id}/read      — mark one row read / unread
#                                            (body: {"read": bool}).
#
# Authorization: rows are self-scoped — every read/write is restricted to
# user_id == the authenticated user (403 otherwise), so no RBAC module gate
# is needed; there is nothing another user could be authorized to see.

from __future__ import annotations

from datetime import datetime, timezone as _tz

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..accounts.dependencies import get_current_user
from ..accounts.models import User
from ...core.database import get_db
from .common import CtmsError, guarded
from .models import CtmsNotification

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _parse_iso(value: str):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def _row_payload(row: CtmsNotification) -> dict:
    """Backend row -> the frontend notificationService record shape.

    The record id is the client_key (the localStorage record's own id) so a
    re-push of the hydrated record stays idempotent; notification_id is the
    durable backend primary key, surfaced for UI deep-links/debugging.
    """
    return {
        "id": row.client_key or f"notif-{row.notification_id}",
        "backendId": row.notification_id,
        "title": row.title or "",
        "message": row.body or "",
        "actorName": row.actor_name or "",
        "actorRole": row.actor_role or "",
        "studyCode": row.study_code or "",
        "type": row.notification_type or "",
        "metadata": row.meta if isinstance(row.meta, dict) else {},
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "read": bool(row.is_read),
    }


def _apply_record(db: Session, row: CtmsNotification, record: dict) -> None:
    """Patch a row's mutable fields from one frontend record.

    Patch semantics, not replace semantics: a field is only touched when the
    incoming record actually carries it (the frontend always sends complete
    records, so full pushes are exact mirrors; a partial push — e.g. a bare
    read-state update — never wipes actor/type/study metadata it did not
    mention).
    """
    if "title" in record:
        row.title = str(record.get("title") or "")[:255]
    if "message" in record:
        row.body = str(record.get("message") or "")[:10000] or None
    if "type" in record:
        row.notification_type = (str(record.get("type") or "INFO").strip() or "INFO")[:50]
    if "severity" in record:
        row.severity = str(record.get("severity") or "").strip()[:50] or None
    if "link" in record:
        row.link = str(record.get("link") or "").strip()[:500] or None
    if "actorName" in record:
        row.actor_name = str(record.get("actorName") or "").strip()[:255] or None
    if "actorRole" in record:
        row.actor_role = str(record.get("actorRole") or "").strip()[:100] or None
    if "studyCode" in record:
        row.study_code = str(record.get("studyCode") or "").strip()[:100] or None
    if "metadata" in record:
        row.meta = record.get("metadata") if isinstance(record.get("metadata"), dict) else None
    parsed_created = _parse_iso(record.get("createdAt"))
    if parsed_created:
        row.created_at = parsed_created
    if "read" in record:
        _apply_read_state(row, bool(record.get("read")))


def _apply_read_state(row: CtmsNotification, read: bool) -> None:
    if read and not row.is_read:
        row.is_read = True
        row.read_at = row.read_at or datetime.now(_tz.utc).replace(tzinfo=None)
    elif not read and row.is_read:
        row.is_read = False
        row.read_at = None


@router.get("")
@router.get("/")
def list_notifications(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    def _list():
        rows = (
            db.execute(
                select(CtmsNotification)
                .where(CtmsNotification.user_id == user.id)
                .order_by(CtmsNotification.created_at.desc())
            )
            .scalars()
            .all()
        )
        return [_row_payload(row) for row in rows]

    return guarded(_list)


@router.post("/sync")
def sync_notifications(
    body: dict,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Bulk upsert the caller's visible notifications (idempotent by client_key).

    Body: {"notifications": [<frontend notificationService records>]}. Each
    record's `id` (falling back to `eventId`) is the client_key. Existing
    rows for this user are updated in place — including read state — and new
    ids are inserted. Records without any stable key are skipped (reported).
    """

    def _sync():
        records = body.get("notifications") if isinstance(body, dict) else None
        if not isinstance(records, list):
            raise CtmsError("A notifications array is required.", status=400)

        created = 0
        updated = 0
        skipped: list[dict] = []
        for record in records:
            if not isinstance(record, dict):
                skipped.append({"id": None, "reason": "not-an-object"})
                continue
            client_key = str(
                record.get("id") or record.get("eventId") or ""
            ).strip()
            if not client_key:
                skipped.append({"id": None, "reason": "missing-id"})
                continue

            row = (
                db.execute(
                    select(CtmsNotification).where(
                        CtmsNotification.user_id == user.id,
                        CtmsNotification.client_key == client_key,
                    )
                )
                .scalars()
                .first()
            )
            if row is None:
                # Insert requires a title (schema NOT NULL) and a stable key.
                if not str(record.get("title") or "").strip():
                    skipped.append({"id": client_key, "reason": "missing-title"})
                    continue
                row = CtmsNotification(
                    user_id=user.id,
                    client_key=client_key,
                    notification_type="INFO",
                    title=str(record.get("title") or "")[:255],
                    is_read=False,
                    created_at=_parse_iso(record.get("createdAt"))
                    or datetime.now(_tz.utc).replace(tzinfo=None),
                )
                db.add(row)
                db.flush()
                _apply_record(db, row, record)
                created += 1
            else:
                # Update is a patch — a title-only-missing partial record is
                # fine; the existing row keeps its title.
                _apply_record(db, row, record)
                updated += 1

        db.commit()
        return {"created": created, "updated": updated, "skipped": skipped}

    return guarded(_sync)


@router.post("/{notification_id}/read")
@router.post("/{notification_id}/read/")
def set_notification_read(
    notification_id: int,
    body: dict,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    def _set_read():
        row = db.get(CtmsNotification, notification_id)
        if row is None or row.user_id != user.id:
            raise CtmsError("Notification not found.", status=404)
        read = bool((body or {}).get("read", True))
        _apply_read_state(row, read)
        db.commit()
        db.refresh(row)
        return _row_payload(row)

    return guarded(_set_read)
