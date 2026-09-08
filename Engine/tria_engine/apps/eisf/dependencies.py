# tria_engine/apps/eisf/dependencies.py
#
# Request-scoped dependencies for the eISF repository, reusing the app-wide
# session/auth plumbing: the current user (accounts dependencies), the DB
# session (core.database.get_db) and the RBAC scope helpers
# (accounts.rbac.resolve_user_scope / assert_write_scope).

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from ..accounts.dependencies import get_current_user
from ..accounts.models import User
from ..accounts.rbac import assert_write_scope, resolve_user_scope
from ...core.database import get_db


def get_scope(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Effective org/study/site scope for the signed-in user."""
    return {
        "organization_id": user.organization_id if user else None,
        "scope": resolve_user_scope(user),
    }


def assert_document_scope(user: User, study_code: str | None, site_code: str | None) -> None:
    """403 when the requested study/site is outside the user's assignment."""
    assert_write_scope(user, study_code, site_code)


__all__ = ["get_scope", "assert_document_scope"]