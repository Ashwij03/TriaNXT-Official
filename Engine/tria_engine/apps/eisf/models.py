# tria_engine/apps/eisf/models.py
#
# eISF regulatory document repository persistence.
#
#   eisf_document          — one row per regulatory document. Thin relational
#                            row (code + org/study/site scope columns) with the
#                            full document record in the JSON `data` column,
#                            exactly like every _CtmsRecord table in
#                            apps/ctms/models.py — the row scope columns let
#                            the existing SQL-level scope filters run on the
#                            eISF repository too.
#   eisf_documentversion   — the Part 11 audit trail: one row per uploaded
#                            version, holding the flattened SignaturePayload
#                            (signed_by / signature_stamp / signed_at) plus
#                            who uploaded it and when. Relational (real FK to
#                            eisf_document.id), mirroring how CtmsUiStorage is
#                            a genuine relational table in this codebase.
#
# Schema creation follows the standard Alembic path (see
# tria_engine/alembic/versions/...eisf_regulatory_repository.py).

from __future__ import annotations

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from tria_engine.core.database import BIGINT, Base
from tria_engine.core.timeutils import utcnow
from ..ctms.models import _CtmsRecord


class EisfDocument(_CtmsRecord, Base):
    """A regulatory binder document (JSON-mirror record + scope columns).

    The JSON document is the exact record the EISF pages render (documentName,
    folderId/folderTitle, category, version, status, uploadedBy, ...); the
    scope columns carry studyCode/siteCode for SQL-level filtering.
    """

    __tablename__ = "eisf_document"


class ESignature(Base):
    """One completed electronic signature (21 CFR Part 11 audit row).

    Distinct from EisfDocumentVersion (which flattens the SignaturePayload
    onto each document version): this is the general signature ledger row
    written by POST /eisf/documents/{code}/sign and by the shared
    /api/audit/signatures surface. document_id/document_code reference the
    signed eisf document (row id + frontend code); document_type lets the
    same ledger record signatures over other document kinds in the future
    (the column set is deliberately storage-agnostic).

    The row is immutable once written — nothing in the codebase updates or
    deletes these rows.
    """

    __tablename__ = "ctms_electronic_signature"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    # eisf_document row id (BIGINT). Plain column, not a hard FK: the ledger
    # may also record signatures over general ctms_documents in future.
    document_id: Mapped[int | None] = mapped_column(BIGINT, nullable=True, index=True)
    document_code: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False, default="eisf")
    signer_user_id: Mapped[int | None] = mapped_column(
        BIGINT, ForeignKey("accounts_user.id", ondelete="SET NULL"), nullable=True, index=True
    )
    signer_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    signer_role: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    meaning: Mapped[str] = mapped_column(String(50), nullable=False, default="approval")
    # SHA-256 hex digest of the canonical signing payload (tamper-evident).
    signature_stamp: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    signed_at: Mapped[object] = mapped_column(DateTime, nullable=False, default=utcnow)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime, nullable=False, default=utcnow)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<ESignature id={self.id} document={self.document_code!r} "
            f"signer={self.signer_name!r} meaning={self.meaning!r}>"
        )


class EisfDocumentVersion(Base):
    """Append-only e-signature + upload audit trail for one document.

    Each uploaded/replaced version of a document inserts a new row. The row
    is immutable once written (the JSON document's own `signatures` array is
    append-only too); nothing in the codebase updates these rows.
    """

    __tablename__ = "eisf_documentversion"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("eisf_document.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0")
    # 21 CFR Part 11 — flattened SignaturePayload.
    signed_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    signature_stamp: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    signed_at: Mapped[object] = mapped_column(DateTime, nullable=True)
    uploaded_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    uploaded_at: Mapped[object] = mapped_column(DateTime, nullable=False, default=utcnow)
    created_at: Mapped[object] = mapped_column(DateTime, nullable=False, default=utcnow)