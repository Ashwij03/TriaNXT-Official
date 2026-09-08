from __future__ import annotations

from datetime import datetime
import logging
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column, Session
from fastapi import APIRouter, Depends, Request

from ...apps.accounts.dependencies import get_current_user
from ...apps.accounts.models import User
from ...core.database import BIGINT, Base, get_db
from ...core.timeutils import utcnow
from sqlalchemy import JSON, text


class CtmsUiStorage(Base):
    __tablename__ = "ctms_ui_storage"
    __table_args__ = (UniqueConstraint("user_id", "storage_key", name="uq_ctms_ui_storage_user_key"),)

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("accounts_user.id", ondelete="CASCADE"), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[object] = mapped_column(JSON, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[object] = mapped_column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


router = APIRouter(prefix="/api/client-storage", tags=["client-storage"])


def _row_value(row):
    return {"key": row.storage_key, "value": row.value, "updated_at": row.updated_at.isoformat() if row.updated_at else None}


@router.get("")
@router.get("/")
def list_storage(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.execute(select(CtmsUiStorage).where(CtmsUiStorage.user_id == user.id).order_by(CtmsUiStorage.storage_key)).scalars().all()
    return {"data": [_row_value(r) for r in rows]}


@router.put("/{storage_key:path}")
def put_storage(storage_key: str, payload: dict, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not storage_key or len(storage_key) > 255:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid storage key")
    row = db.execute(select(CtmsUiStorage).where(CtmsUiStorage.user_id == user.id, CtmsUiStorage.storage_key == storage_key)).scalar_one_or_none()
    if row is None:
        row = CtmsUiStorage(user_id=user.id, storage_key=storage_key, value=payload.get("value"))
        db.add(row)
    else:
        row.value = payload.get("value")
        row.updated_at = utcnow()
    db.commit()
    db.refresh(row)
    return _row_value(row)


@router.delete("/{storage_key:path}", status_code=204)
def delete_storage(storage_key: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.execute(select(CtmsUiStorage).where(CtmsUiStorage.user_id == user.id, CtmsUiStorage.storage_key == storage_key)).scalar_one_or_none()
    if row is not None:
        db.delete(row)
        db.commit()
    return None


def ensure_ui_storage_table(engine):
    """Ensure the UI storage table exists without poisoning a transaction.

    Startup DDL is deliberately executed one statement at a time.  If an
    installation has a schema mismatch, the failing statement is rolled
    back independently and the original PostgreSQL error is logged instead
    of being replaced by SQLSTATE 25P02 (InFailedSqlTransaction).
    """
    dialect = engine.dialect.name

    if dialect == "postgresql":
        # Match the existing accounts_user.id type.  This makes the helper
        # safe against databases created from older Django/CTMS schemas
        # where the user PK may be INTEGER rather than BIGINT.
        user_id_type = "BIGINT"
        try:
            with engine.connect() as conn:
                row = conn.execute(text("""
                    SELECT data_type
                    FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = 'accounts_user'
                      AND column_name = 'id'
                """)).first()
                if row and row[0] == "integer":
                    user_id_type = "INTEGER"
        except Exception as exc:
            logger = __import__("logging").getLogger("tria_engine")
            logger.warning("Could not inspect accounts_user.id; defaulting UI storage user_id to BIGINT: %s", exc)

        statements = [
            f"""CREATE TABLE IF NOT EXISTS ctms_ui_storage (
                id BIGSERIAL PRIMARY KEY,
                user_id {user_id_type} NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
                storage_key VARCHAR(255) NOT NULL,
                value JSONB,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_ctms_ui_storage_user_key UNIQUE (user_id, storage_key)
            )""",
            "CREATE INDEX IF NOT EXISTS ix_ctms_ui_storage_user_id ON ctms_ui_storage(user_id)",
            "CREATE INDEX IF NOT EXISTS ix_ctms_ui_storage_key ON ctms_ui_storage(storage_key)",
        ]
    else:
        statements = [
            """CREATE TABLE IF NOT EXISTS ctms_ui_storage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                storage_key VARCHAR(255) NOT NULL,
                value JSON,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                UNIQUE(user_id, storage_key)
            )""",
            "CREATE INDEX IF NOT EXISTS ix_ctms_ui_storage_user_id ON ctms_ui_storage(user_id)",
            "CREATE INDEX IF NOT EXISTS ix_ctms_ui_storage_key ON ctms_ui_storage(storage_key)",
        ]

    logger = logging.getLogger("tria_engine")
    for statement in statements:
        try:
            # A separate transaction per DDL statement guarantees that one
            # failure cannot turn the next statement into SQLSTATE 25P02.
            with engine.begin() as conn:
                conn.execute(text(statement))
        except Exception as exc:
            logger.error("UI storage DDL failed: %s | SQL: %s", exc, " ".join(statement.split()))
            # If the table already exists, index creation can still be useful;
            # otherwise continue startup and let API calls expose the real
            # database problem rather than preventing the whole Engine from
            # starting.

