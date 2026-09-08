"""ctms_notifications v2 wiring (notifications phase 1)

Revision ID: c2f5a8e1b904
Revises: 9a3f7c2e5b10
Create Date: 2026-09-08 14:00:00.000000+00:00

Maps the fully-normalized v2 `ctms_notifications` table (already defined in
the authoritative SQL package, 03_operations_governance.sql) plus the
additive extension columns the frontend notificationService contract needs
(client_key, actor_name, actor_role, study_code, metadata).

The migration is inspector-guarded so it is safe on BOTH schema paths:
  * a pure-Alembic database (table absent -> created here in full), and
  * a SQL-package-loaded database (table already present -> only the
    extension columns are added; the package's own 10_3 file does the same
    ALTERs for fresh SQL-package installs).

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c2f5a8e1b904"
down_revision: Union[str, Sequence[str], None] = "9a3f7c2e5b10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


BASE_COLUMNS = [
    sa.Column(
        "notification_id",
        sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
        autoincrement=True,
        nullable=False,
    ),
    sa.Column(
        "user_id",
        sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
        nullable=False,
    ),
    sa.Column(
        "study_id",
        sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
        nullable=True,
    ),
    sa.Column("title", sa.String(length=255), nullable=False),
    sa.Column("body", sa.Text(), nullable=True),
    sa.Column("notification_type", sa.String(length=50), nullable=False),
    sa.Column("severity", sa.String(length=50), nullable=True),
    sa.Column("link", sa.String(length=500), nullable=True),
    sa.Column("is_read", sa.Boolean(), nullable=False),
    sa.Column("read_at", sa.DateTime(), nullable=True),
    sa.Column("created_at", sa.DateTime(), nullable=False),
]

EXTENSION_COLUMNS = [
    ("client_key", sa.Column("client_key", sa.String(length=255), nullable=True)),
    ("actor_name", sa.Column("actor_name", sa.String(length=255), nullable=True)),
    ("actor_role", sa.Column("actor_role", sa.String(length=100), nullable=True)),
    ("study_code", sa.Column("study_code", sa.String(length=100), nullable=True)),
    (
        "metadata",
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
    ),
]


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "ctms_notifications" not in table_names:
        # Pure-Alembic database: create the full table (base v2 columns +
        # extension columns in one DDL).
        op.create_table(
            "ctms_notifications",
            *BASE_COLUMNS,
            *[col for _, col in EXTENSION_COLUMNS],
            sa.ForeignKeyConstraint(
                ["user_id"], ["accounts_user.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("notification_id"),
        )
        op.create_index(
            "ix_ctms_notifications_user_id",
            "ctms_notifications",
            ["user_id"],
            unique=False,
        )
        op.create_index(
            "ix_ctms_notifications_client_key",
            "ctms_notifications",
            ["client_key"],
            unique=False,
        )
        return

    # SQL-package-loaded database: the v2 base table exists; add only the
    # extension columns that are missing (mirrors 10_3_ctms_notifications_ext.sql).
    existing = {
        column["name"] for column in inspector.get_columns("ctms_notifications")
    }
    for name, column in EXTENSION_COLUMNS:
        if name not in existing:
            op.add_column("ctms_notifications", column)
    if "ix_ctms_notifications_client_key" not in {
        index["name"] for index in inspector.get_indexes("ctms_notifications")
    }:
        op.create_index(
            "ix_ctms_notifications_client_key",
            "ctms_notifications",
            ["client_key"],
            unique=False,
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "ctms_notifications" not in inspector.get_table_names():
        return
    existing = {
        column["name"] for column in inspector.get_columns("ctms_notifications")
    }
    indexes = {
        index["name"] for index in inspector.get_indexes("ctms_notifications")
    }
    if "ix_ctms_notifications_client_key" in indexes:
        op.drop_index("ix_ctms_notifications_client_key", table_name="ctms_notifications")

    base_names = {
        "notification_id",
        "user_id",
        "study_id",
        "title",
        "body",
        "notification_type",
        "severity",
        "link",
        "is_read",
        "read_at",
        "created_at",
    }
    # Drop extension columns only — never the SQL package's base v2 columns.
    for name, _ in EXTENSION_COLUMNS:
        if name in existing and name not in base_names:
            op.drop_column("ctms_notifications", name)
    # Drop the whole table only when it is purely ours (no base v2 columns left).
    remaining = existing - {name for name, _ in EXTENSION_COLUMNS}
    if not remaining.intersection(base_names):
        op.drop_index(
            "ix_ctms_notifications_user_id",
            table_name="ctms_notifications",
            if_exists=True,
        )
        op.drop_table("ctms_notifications")
