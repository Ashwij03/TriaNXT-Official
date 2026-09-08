# backend/Engine/scripts/create_default_admin.py
#
# One-off script: creates (or repairs) a single, permanent Admin account
# directly in PostgreSQL, using the exact same password-hashing and
# session/model code the real FastAPI backend uses for every other user.
# This intentionally bypasses the public /api/accounts/register/ endpoint
# (which the frontend no longer offers "Admin" on, by design) and is meant
# to be run once, locally, by a developer/operator — not exposed as an API.
#
# Run from the backend root (same folder as check_postgres_connection.py):
#   python -m scripts.create_default_admin
#
# Safe to re-run: if the account already exists, it updates the password/
# role/flags to match this script instead of creating a duplicate.

from sqlalchemy import select
from tria_engine.apps.accounts.models import User
from tria_engine.apps.organizations.models import Organization, Role
from tria_engine.core.database import SessionLocal
from tria_engine.core.security import hash_password

# ---------------------------------------------------------------------------
# Edit these values if you want different default Admin credentials.
# ---------------------------------------------------------------------------
# Edit these values if you want different default Admin credentials.
# These match src/shared/config/defaultAdmin.ts on the frontend by default.
# ---------------------------------------------------------------------------
ADMIN_USERNAME = "sysadmin01"
ADMIN_EMAIL = "admin1@trianxt.com"
ADMIN_PASSWORD = "Admin@123"
ADMIN_FIRST_NAME = "System"
ADMIN_LAST_NAME = "Administrator"
ORGANIZATION_NAME = "Demo Sponsor Organization"  # matches sql/08_seed.sql
ROLE_NAME = "Admin"  # must be exactly "Admin" — see apps/accounts/router.py ROLE_NAME_MAP


def main() -> None:
    db = SessionLocal()
    try:
        # 1. Find (or create) the organization this admin belongs to.
        org = db.execute(
            select(Organization).where(Organization.name == ORGANIZATION_NAME)
        ).scalar_one_or_none()
        if org is None:
            org = Organization(name=ORGANIZATION_NAME)
            db.add(org)
            db.commit()
            db.refresh(org)
            print(f"Created organization: {org.name} (id={org.id})")
        else:
            print(f"Using existing organization: {org.name} (id={org.id})")

        # 2. Find (or create) the Admin role tied to that organization.
        role = db.execute(
            select(Role).where(Role.name == ROLE_NAME, Role.organization_id == org.id)
        ).scalar_one_or_none()
        if role is None:
            role = Role(name=ROLE_NAME, organization_id=org.id)
            db.add(role)
            db.commit()
            db.refresh(role)
            print(f"Created role: {role.name} (id={role.id})")
        else:
            print(f"Using existing role: {role.name} (id={role.id})")

        # 3. Find the user by email OR username (either could already exist).
        user = db.execute(
            select(User).where(
                (User.email == ADMIN_EMAIL) | (User.username == ADMIN_USERNAME)
            )
        ).scalar_one_or_none()

        hashed = hash_password(ADMIN_PASSWORD)

        if user is None:
            user = User(
                username=ADMIN_USERNAME,
                email=ADMIN_EMAIL,
                first_name=ADMIN_FIRST_NAME,
                last_name=ADMIN_LAST_NAME,
                organization_id=org.id,
                role_id=role.id,
                password=hashed,
                is_active=True,
                is_staff=True,
                is_superuser=True,
                must_change_password=False,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"Created Admin user: {user.username} <{user.email}> (id={user.id})")
        else:
            user.username = ADMIN_USERNAME
            user.email = ADMIN_EMAIL
            user.first_name = ADMIN_FIRST_NAME
            user.last_name = ADMIN_LAST_NAME
            user.organization_id = org.id
            user.role_id = role.id
            user.password = hashed
            user.is_active = True
            user.is_staff = True
            user.is_superuser = True
            user.must_change_password = False
            db.commit()
            print(f"Updated existing user to Admin: {user.username} <{user.email}> (id={user.id})")

        print("\nDone. You can now log in with:")
        print(f"  username/email: {ADMIN_USERNAME} / {ADMIN_EMAIL}")
        print(f"  password:       {ADMIN_PASSWORD}")

    finally:
        db.close()


if __name__ == "__main__":
    main()