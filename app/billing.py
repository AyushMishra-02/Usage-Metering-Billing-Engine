import datetime
import math
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.models import Tenant, Subscription, Plan, UsageEvent

# ─── Pricing Constants (per the capstone spec) ───────────────────────────────
#
# Token type        │ Cost per 1 000 tokens (cents)
# ──────────────────┼─────────────────────────────────
# Input tokens      │ 1.5
# Cached tokens     │ 0.75   (50 % discount)
# Output tokens     │ 6.0
# Reasoning tokens  │ 12.0
# API call flat fee │ 0.5 cents each
#
COST_PER_1K = {
    "input_tokens":     1.5,
    "cached_tokens":    0.75,
    "output_tokens":    6.0,
    "reasoning_tokens": 12.0,
}
COST_API_CALL_CENTS = 0.5


def calculate_token_cost_cents(
    input_tokens: int = 0,
    cached_tokens: int = 0,
    output_tokens: int = 0,
    reasoning_tokens: int = 0,
) -> float:
    """Return cost in *fractional* cents for a single request."""
    cost = 0.0
    cost += (input_tokens / 1000) * COST_PER_1K["input_tokens"]
    cost += (cached_tokens / 1000) * COST_PER_1K["cached_tokens"]
    cost += (output_tokens / 1000) * COST_PER_1K["output_tokens"]
    cost += (reasoning_tokens / 1000) * COST_PER_1K["reasoning_tokens"]
    return cost


def check_quota_and_record_usage(
    db: Session, 
    tenant_id: str, 
    event_type: str, 
    quantity: int, 
    idempotency_key: str
):
    # 1. Fetch Subscription and Plan
    subscription = db.query(Subscription).filter(Subscription.tenant_id == tenant_id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
        
    if subscription.status != "active":
        raise HTTPException(status_code=402, detail="Payment required. Subscription is not active.")
        
    plan = subscription.plan
    
    # 2. Calculate current usage (assuming monthly, simplifying to all-time for this demo or current month)
    # Let's filter for the current month
    now = datetime.datetime.now(datetime.timezone.utc)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    current_usage = db.query(func.sum(UsageEvent.quantity)).filter(
        UsageEvent.tenant_id == tenant_id,
        UsageEvent.event_type == event_type,
        UsageEvent.timestamp >= start_of_month
    ).scalar() or 0
    
    # 3. Check Quota
    limit = plan.api_call_limit if event_type == 'api_call' else plan.ai_token_limit
    
    if current_usage + quantity > limit:
        raise HTTPException(status_code=429, detail=f"Quota exceeded for {event_type}. Used: {current_usage}, Requested: {quantity}, Limit: {limit}")
        
    # 4. Record Usage (Idempotent)
    event = UsageEvent(
        tenant_id=tenant_id,
        event_type=event_type,
        quantity=quantity,
        idempotency_key=idempotency_key
    )
    
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # It's a retry of a successful request
        return True # Indicates idempotent success
        
    return False # Indicates new record created


def get_cost_rollup(db: Session, tenant_id: str) -> dict:
    """
    Return a monthly cost breakdown for a tenant.

    We iterate through every usage_event for the current billing period
    and apply the pricing table above.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    rows = (
        db.query(UsageEvent.event_type, func.sum(UsageEvent.quantity))
        .filter(
            UsageEvent.tenant_id == tenant_id,
            UsageEvent.timestamp >= start_of_month,
        )
        .group_by(UsageEvent.event_type)
        .all()
    )

    usage = {r[0]: int(r[1]) for r in rows}

    api_calls      = usage.get("api_call", 0)
    input_tokens   = usage.get("input_tokens", 0)
    cached_tokens  = usage.get("cached_tokens", 0)
    output_tokens  = usage.get("output_tokens", 0)
    reasoning_tokens = usage.get("reasoning_tokens", 0)
    # Legacy "ai_token" bucket (from earlier tests) treated as input tokens
    legacy_tokens  = usage.get("ai_token", 0)

    cost_api       = api_calls * COST_API_CALL_CENTS
    cost_input     = ((input_tokens + legacy_tokens) / 1000) * COST_PER_1K["input_tokens"]
    cost_cached    = (cached_tokens / 1000) * COST_PER_1K["cached_tokens"]
    cost_output    = (output_tokens / 1000) * COST_PER_1K["output_tokens"]
    cost_reasoning = (reasoning_tokens / 1000) * COST_PER_1K["reasoning_tokens"]

    total_cents = cost_api + cost_input + cost_cached + cost_output + cost_reasoning

    return {
        "period_start": start_of_month.isoformat(),
        "period_end": now.isoformat(),
        "line_items": {
            "api_calls":        {"quantity": api_calls,         "cost_cents": round(cost_api, 4)},
            "input_tokens":     {"quantity": input_tokens + legacy_tokens, "cost_cents": round(cost_input, 4)},
            "cached_tokens":    {"quantity": cached_tokens,     "cost_cents": round(cost_cached, 4)},
            "output_tokens":    {"quantity": output_tokens,     "cost_cents": round(cost_output, 4)},
            "reasoning_tokens": {"quantity": reasoning_tokens,  "cost_cents": round(cost_reasoning, 4)},
        },
        "total_cost_cents": round(total_cents, 2),
        "total_cost_usd":  f"${total_cents / 100:.4f}",
    }
