# tria_engine/tests/test_billing_api.py
#
# Billing REST surface (apps/billing/router.py) — the contract the frontend
# planCatalogService / subscriptionService call in API mode:
#   GET/POST/PUT/DELETE /billing/plans/...
#   GET/PATCH      /billing/subscription/me/
#   POST           /billing/subscription/assign/
#   POST           /billing/subscription/checkout/
#   POST           /billing/subscription/confirm/
#
# Covers: plan CRUD + duplicate-name 409, single-default rule, in-use delete
# 409, RBAC (non-admin gets 403 on plan writes), subscription read/assign/
# patch, and the mock checkout/confirm lifecycle.

from __future__ import annotations

import uuid

from tria_engine.apps.accounts.models import User
from tria_engine.apps.organizations.models import Organization, Role
from tria_engine.core.database import SessionLocal
from tria_engine.core.security import hash_password

PASSWORD = "BillingPass123!"


def _seed_role_user(role_name: str, tag: str) -> str:
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
        db.add(
            User(
                username=email.split("@")[0],
                email=email,
                password=hash_password(PASSWORD),
                first_name=role_name,
                last_name="User",
                is_active=True,
                organization_id=org.id,
                role_id=role.id,
            )
        )
        db.commit()
        return email
    finally:
        db.close()


def _login(client, email: str, password: str = PASSWORD):
    res = client.post(
        "/api/accounts/login/",
        json={"email": email, "password": password},
    )
    assert res.status_code == 200, res.text
    return client


def _admin(client):
    return _login(client, "admin@test.local", "AdminPass123!")


def _plan(name: str, **overrides) -> dict:
    plan = {
        "name": name,
        "price": 499,
        "maxStudies": 10,
        "maxUsers": 25,
        "storageLimitGb": 100,
        "features": ["Up to 10 studies", "25 users"],
        "isDefault": False,
    }
    plan.update(overrides)
    return plan


def test_plan_catalog_crud_and_default_rule(client):
    _admin(client)

    # Empty catalog initially.
    res = client.get("/billing/plans/")
    assert res.status_code == 200, res.text
    catalog = res.json()
    assert isinstance(catalog, list)

    # Create two plans; the second is promoted to default.
    res = client.post("/billing/plans/", json=_plan("Basic", price=0, isDefault=True))
    assert res.status_code == 200, res.text
    basic = res.json()
    assert basic["name"] == "Basic"
    assert basic["features"] == ["Up to 10 studies", "25 users"]
    assert basic["isDefault"] is True

    res = client.post("/billing/plans/", json=_plan("Enterprise"))
    assert res.status_code == 200, res.text
    enterprise = res.json()
    assert enterprise["isDefault"] is False

    # Duplicate name -> 409.
    res = client.post("/billing/plans/", json=_plan("Basic"))
    assert res.status_code == 409, res.text

    # Update: price + name; promote to default demotes the other tier.
    res = client.put(
        f"/billing/plans/{enterprise['id']}/",
        json={"price": 1999, "isDefault": True},
    )
    assert res.status_code == 200, res.text
    updated = res.json()
    assert updated["price"] == 1999
    assert updated["isDefault"] is True

    after = {p["name"]: p for p in client.get("/billing/plans/").json()}
    assert after["Basic"]["isDefault"] is False

    # Delete the now non-default Basic plan.
    res = client.delete(f"/billing/plans/{basic['id']}/")
    assert res.status_code == 200, res.text
    names = [p["name"] for p in client.get("/billing/plans/").json()]
    assert "Basic" not in names


def test_plan_delete_in_use_rejected(client):
    _admin(client)
    res = client.post(
        "/billing/plans/", json=_plan("InUse", price=100, isDefault=True)
    )
    assert res.status_code == 200, res.text
    plan_id = res.json()["id"]

    # Assign the plan to the org subscription, then try to delete it.
    res = client.post("/billing/subscription/assign/", json={"planId": plan_id})
    assert res.status_code == 200, res.text
    assert res.json()["planId"] == str(plan_id)

    res = client.delete(f"/billing/plans/{plan_id}/")
    assert res.status_code == 409, res.text


def test_plan_writes_require_admin(client):
    cro_email = _seed_role_user("CRO", "billingcro")
    _login(client, cro_email)

    res = client.post("/billing/plans/", json=_plan("NotAllowed"))
    assert res.status_code == 403, res.text
    res = client.post("/billing/subscription/assign/", json={"planId": 1})
    assert res.status_code == 403, res.text


def test_subscription_read_assign_patch(client):
    _admin(client)
    res = client.post("/billing/plans/", json=_plan("SubPlan", price=0, isDefault=True))
    assert res.status_code == 200, res.text
    plan_id = res.json()["id"]

    # GET /subscription/me/ lazily creates the org row.
    res = client.get("/billing/subscription/me/")
    assert res.status_code == 200, res.text
    subscription = res.json()
    assert subscription["status"] == "Active"
    assert "planId" in subscription

    # assign (free plan resets the trial window).
    res = client.post("/billing/subscription/assign/", json={"planId": plan_id})
    assert res.status_code == 200, res.text
    assert res.json()["planId"] == str(plan_id)
    assert res.json()["endDate"]

    # PATCH status / notes / overrides.
    res = client.patch(
        "/billing/subscription/me/",
        json={"status": "Suspended", "notes": "testing", "maxStudies": 5},
    )
    assert res.status_code == 200, res.text
    patched = res.json()
    assert patched["status"] == "Suspended"
    assert patched["notes"] == "testing"
    assert patched["maxStudies"] == 5


def test_checkout_confirm_lifecycle(client):
    _admin(client)
    res = client.post(
        "/billing/plans/", json=_plan("PaidPlan", price=1200, isDefault=True)
    )
    assert res.status_code == 200, res.text
    plan_id = res.json()["id"]

    res = client.post("/billing/subscription/checkout/", json={"planId": plan_id})
    assert res.status_code == 200, res.text
    checkout = res.json()
    assert checkout["gatewayOrderId"]
    assert checkout["amount"] == 120000  # 1200 * 100 paise
    assert checkout["currency"] == "INR"
    assert checkout["paymentTransactionId"]

    # Confirm with echoed gateway fields.
    res = client.post(
        "/billing/subscription/confirm/",
        json={
            "paymentTransactionId": checkout["paymentTransactionId"],
            "gatewayPaymentId": "pay_test_123",
            "gatewaySignature": "sig_123",
        },
    )
    assert res.status_code == 200, res.text
    confirmed = res.json()
    assert confirmed["status"] == "Active"
    assert confirmed["planId"] == str(plan_id)

    # Re-confirming the same transaction is rejected (idempotency guard).
    res = client.post(
        "/billing/subscription/confirm/",
        json={
            "paymentTransactionId": checkout["paymentTransactionId"],
            "gatewayPaymentId": "pay_test_123",
            "gatewaySignature": "sig_123",
        },
    )
    assert res.status_code == 409, res.text


def test_checkout_requires_plan(client):
    _admin(client)
    res = client.post("/billing/subscription/checkout/", json={"planId": 999999})
    assert res.status_code == 404, res.text