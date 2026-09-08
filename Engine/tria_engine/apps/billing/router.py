# tria_engine/apps/billing/router.py
#
# Billing REST surface, mounted at /billing (root-level prefix like the
# safety/monitoring routers; the frontend planCatalogService /
# subscriptionService call /billing/plans/* and /billing/subscription/*).
#
# Request/response shapes match the frontend contracts exactly:
#   plan          -> { id, name, price, maxStudies, maxUsers,
#                      storageLimitGb, features: string[], isDefault }
#   subscription  -> { id, status, startDate, endDate, autoRenewal, notes,
#                      planId, maxStudies?, maxUsers?, storageLimitGb? }
#   checkout      -> { gatewayOrderId, amount, currency, gatewayKey,
#                      paymentTransactionId }
#
# Payment is a deterministic MOCK gateway: checkout creates a
# PaymentTransaction row (status CREATED) and confirm() verifies the client
# echoed the gateway fields, marks the transaction PAID and applies the plan.
# Swap in a real Razorpay integration behind these same endpoints when the
# gateway is provisioned (RAZORPAY_* settings already exist in core/config).

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..accounts.dependencies import get_current_user
from ..accounts.models import User
from ..accounts.rbac import enforce, resolve_role
from ...core.config import settings
from ...core.database import get_db
from .models import BillingSubscription, PaymentTransaction, PlanTier, SubscriptionEvent

router = APIRouter(prefix="/billing", tags=["billing"])


# ---------------------------------------------------------------------------
# Plan catalog (billing_plantier)
# ---------------------------------------------------------------------------


def _plan_payload(row: PlanTier) -> dict:
    try:
        features = json.loads(row.features or "[]")
        if not isinstance(features, list):
            features = []
    except (ValueError, TypeError):
        features = []
    return {
        "id": str(row.id),
        "name": row.name,
        "price": float(row.price or 0),
        "maxStudies": row.max_studies,
        "maxUsers": row.max_users,
        "storageLimitGb": row.storage_limit_gb,
        "features": [str(f) for f in features],
        "isDefault": bool(row.is_default),
        "isActive": bool(row.is_active),
    }


def _plan_features(features) -> str:
    if isinstance(features, list):
        return json.dumps([str(f).strip() for f in features if str(f).strip()])
    if isinstance(features, str):
        try:
            parsed = json.loads(features)
            if isinstance(parsed, list):
                return json.dumps([str(f).strip() for f in parsed if str(f).strip()])
        except (ValueError, TypeError):
            pass
        return json.dumps([f.strip() for f in features.split(",") if f.strip()])
    return "[]"


def _require_organization(user: User):
    if user is None or not getattr(user, "organization_id", None):
        raise HTTPException(status_code=400, detail="An organization is required for billing operations.")


@router.get("/plans/")
@router.get("/plans")
def list_plans(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.execute(
        select(PlanTier).order_by(PlanTier.is_default.desc(), PlanTier.name)
    ).scalars().all()
    return [_plan_payload(row) for row in rows]


@router.post("/plans/")
@router.post("/plans")
def create_plan(
    body: dict,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    enforce(user, "billing", "create")
    name = str(body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Plan name is required.")
    existing = db.execute(select(PlanTier).where(PlanTier.name == name)).scalars().first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="A plan with this name already exists.")

    if bool(body.get("isDefault")):
        for row in db.execute(select(PlanTier).where(PlanTier.is_default.is_(True))).scalars().all():
            row.is_default = False
            db.add(row)

    row = PlanTier(
        name=name,
        price=Decimal(str(body.get("price") if body.get("price") is not None else 0)),
        max_studies=body.get("maxStudies") if body.get("maxStudies") is not None else body.get("max_studies"),
        max_users=body.get("maxUsers") if body.get("maxUsers") is not None else body.get("max_users"),
        storage_limit_gb=(
            body.get("storageLimitGb")
            if body.get("storageLimitGb") is not None
            else body.get("storage_limit_gb")
        ),
        features=_plan_features(body.get("features")),
        is_default=bool(body.get("isDefault")),
        is_active=bool(body.get("isActive", True)),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _plan_payload(row)


@router.put("/plans/{plan_id}/")
@router.put("/plans/{plan_id}")
def update_plan(
    plan_id: int,
    body: dict,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    enforce(user, "billing", "update")
    row = db.get(PlanTier, plan_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Plan not found.")

    name = str(body.get("name") or "").strip()
    if name and name != row.name:
        existing = db.execute(select(PlanTier).where(PlanTier.name == name)).scalars().first()
        if existing is not None:
            raise HTTPException(status_code=409, detail="A plan with this name already exists.")
        row.name = name

    if body.get("price") is not None:
        row.price = Decimal(str(body["price"]))
    if body.get("maxStudies") is not None or body.get("max_studies") is not None:
        row.max_studies = body.get("maxStudies", body.get("max_studies"))
    if body.get("maxUsers") is not None or body.get("max_users") is not None:
        row.max_users = body.get("maxUsers", body.get("max_users"))
    if body.get("storageLimitGb") is not None or body.get("storage_limit_gb") is not None:
        row.storage_limit_gb = body.get("storageLimitGb", body.get("storage_limit_gb"))
    if body.get("features") is not None:
        row.features = _plan_features(body.get("features"))
    if body.get("isActive") is not None:
        row.is_active = bool(body["isActive"])

    if bool(body.get("isDefault")) and not row.is_default:
        for other in db.execute(select(PlanTier).where(PlanTier.is_default.is_(True))).scalars().all():
            if other.id != row.id:
                other.is_default = False
                db.add(other)
        row.is_default = True
    elif body.get("isDefault") is False and row.is_default:
        row.is_default = False

    db.add(row)
    db.commit()
    db.refresh(row)
    return _plan_payload(row)


@router.delete("/plans/{plan_id}/")
@router.delete("/plans/{plan_id}")
def delete_plan(
    plan_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    enforce(user, "billing", "delete")
    row = db.get(PlanTier, plan_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Plan not found.")
    total = db.execute(select(PlanTier)).scalars().all()
    if len(total) <= 1:
        raise HTTPException(status_code=409, detail="At least one plan must remain in the catalog.")
    in_use = db.execute(
        select(BillingSubscription).where(BillingSubscription.plan_id == plan_id)
    ).scalars().first()
    if in_use is not None:
        raise HTTPException(
            status_code=409,
            detail="This plan is currently assigned to an active subscription and cannot be deleted.",
        )
    if row.is_default:
        raise HTTPException(status_code=409, detail="The default plan cannot be deleted.")
    db.delete(row)
    db.commit()
    return JSONResponse({"deleted": True}, status_code=200)


# ---------------------------------------------------------------------------
# Subscription (billing_subscription, one row per organization)
# ---------------------------------------------------------------------------


def _subscription_payload(row: BillingSubscription) -> dict:
    def _iso(value):
        return value.isoformat() if value else None

    return {
        "id": row.id,
        "status": row.status,
        "startDate": _iso(row.start_date),
        "endDate": _iso(row.end_date),
        "autoRenewal": bool(row.auto_renewal),
        "notes": row.notes or "",
        "planId": str(row.plan_id) if row.plan_id else None,
        "maxStudies": row.max_studies_override,
        "maxUsers": row.max_users_override,
        "storageLimitGb": row.storage_limit_gb_override,
    }


def _get_or_create_subscription(db: Session, user: User) -> BillingSubscription:
    _require_organization(user)
    row = db.execute(
        select(BillingSubscription).where(
            BillingSubscription.organization_id == user.organization_id
        )
    ).scalars().first()
    if row is not None:
        return row
    default_plan = db.execute(
        select(PlanTier).where(PlanTier.is_default.is_(True))
    ).scalars().first()
    row = BillingSubscription(
        status="Active",
        start_date=date.today(),
        end_date=date.today() + timedelta(days=30),
        auto_renewal=True,
        notes="",
        organization_id=user.organization_id,
        plan_id=default_plan.id if default_plan else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        try:
            return date.fromisoformat(str(value)[:10])
        except (ValueError, TypeError):
            return None


@router.get("/subscription/me/")
@router.get("/subscription/me")
def get_my_subscription(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = _get_or_create_subscription(db, user)
    return _subscription_payload(row)


@router.post("/subscription/assign/")
@router.post("/subscription/assign")
def assign_plan(
    body: dict,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Admin-only: assign a catalog tier to the org-wide subscription with no
    payment involved (downgrades, comped upgrades, free/default tiers)."""
    enforce(user, "billing", "update")
    plan_id = body.get("planId")
    if plan_id is None:
        raise HTTPException(status_code=400, detail="planId is required.")
    plan = db.get(PlanTier, int(plan_id))
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found.")

    row = _get_or_create_subscription(db, user)
    row.plan_id = plan.id
    row.status = "Active"
    if Decimal(str(plan.price or 0)) == 0:
        row.end_date = date.today() + timedelta(days=30)
    row.max_studies_override = None
    row.max_users_override = None
    row.storage_limit_gb_override = None
    db.add(row)
    db.commit()
    db.refresh(row)
    return _subscription_payload(row)


@router.patch("/subscription/me/")
@router.patch("/subscription/me")
def update_my_subscription(
    body: dict,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Edit the subscription's status / dates / notes / auto-renewal and the
    per-org limit overrides (the narrow PATCH SubscriptionEditModal feeds)."""
    enforce(user, "billing", "update")
    row = _get_or_create_subscription(db, user)
    if body.get("status") is not None:
        row.status = str(body["status"])[:20]
    if body.get("autoRenewal") is not None:
        row.auto_renewal = bool(body["autoRenewal"])
    if body.get("notes") is not None:
        row.notes = str(body["notes"])
    if body.get("startDate") is not None or body.get("start_date") is not None:
        row.start_date = _parse_date(body.get("startDate") or body.get("start_date"))
    if body.get("endDate") is not None or body.get("end_date") is not None:
        row.end_date = _parse_date(body.get("endDate") or body.get("end_date"))
    for field, column in (
        ("maxStudies", "max_studies_override"),
        ("maxUsers", "max_users_override"),
        ("storageLimitGb", "storage_limit_gb_override"),
    ):
        if body.get(field) is not None:
            setattr(row, column, int(body[field]))
    db.add(row)
    db.commit()
    db.refresh(row)
    return _subscription_payload(row)


# ---------------------------------------------------------------------------
# Checkout / confirm (mock gateway — deterministic, idempotent)
# ---------------------------------------------------------------------------


@router.post("/subscription/checkout/")
@router.post("/subscription/checkout")
def start_checkout(
    body: dict,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    enforce(user, "billing", "create")
    plan_id = body.get("planId")
    if plan_id is None:
        raise HTTPException(status_code=400, detail="planId is required.")
    plan = db.get(PlanTier, int(plan_id))
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found.")

    row = _get_or_create_subscription(db, user)
    amount = Decimal(str(plan.price or 0)) * 100  # paise
    transaction = PaymentTransaction(
        gateway="razorpay",
        gateway_order_id=f"order_{uuid.uuid4().hex[:16]}",
        gateway_payment_id=None,
        gateway_signature=None,
        amount=amount,
        currency="INR",
        status="CREATED",
        subscription_id=row.id,
        plan_id=plan.id,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    db.add(
        SubscriptionEvent(
            subscription_id=row.id,
            event_type="CHECKOUT_STARTED",
            metadata_=json.dumps({"planId": plan.id, "transactionId": transaction.id}),
        )
    )
    db.commit()
    return {
        "gatewayOrderId": transaction.gateway_order_id,
        "amount": int(amount),
        "currency": "INR",
        "gatewayKey": settings.RAZORPAY_KEY_ID or "rzp_test_mock_key",
        "paymentTransactionId": str(transaction.id),
    }


@router.post("/subscription/confirm/")
@router.post("/subscription/confirm")
def confirm_checkout(
    body: dict,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Verify a completed gateway payment server-side. The mock gateway checks
    that the transaction exists, is in CREATED state and the client echoed the
    gateway payment id + signature, then marks it PAID and applies the plan."""
    enforce(user, "billing", "update")
    transaction_id = body.get("paymentTransactionId")
    gateway_payment_id = body.get("gatewayPaymentId")
    gateway_signature = body.get("gatewaySignature")

    if transaction_id is None:
        raise HTTPException(status_code=400, detail="paymentTransactionId is required.")
    try:
        transaction = db.get(PaymentTransaction, int(transaction_id))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid paymentTransactionId.")
    if transaction is None:
        raise HTTPException(status_code=404, detail="Payment transaction not found.")
    if transaction.status != "CREATED":
        raise HTTPException(
            status_code=409, detail="Payment transaction was already processed."
        )
    if not gateway_payment_id or not gateway_signature:
        raise HTTPException(
            status_code=400, detail="Gateway payment id and signature are required."
        )

    transaction.gateway_payment_id = str(gateway_payment_id)
    transaction.gateway_signature = str(gateway_signature)
    transaction.status = "PAID"
    db.add(transaction)

    subscription = db.get(BillingSubscription, transaction.subscription_id)
    if subscription is None:
        raise HTTPException(status_code=404, detail="Subscription not found.")
    subscription.plan_id = transaction.plan_id
    subscription.status = "Active"
    subscription.start_date = date.today()
    subscription.end_date = date.today() + timedelta(days=settings.BILLING_DEFAULT_PERIOD_DAYS)
    subscription.max_studies_override = None
    subscription.max_users_override = None
    subscription.storage_limit_gb_override = None
    db.add(subscription)
    db.add(
        SubscriptionEvent(
            subscription_id=subscription.id,
            event_type="PAYMENT_CONFIRMED",
            metadata_=json.dumps({"transactionId": transaction.id}),
        )
    )
    db.commit()
    db.refresh(subscription)
    return _subscription_payload(subscription)