import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.models import Tenant, Subscription, Plan, UsageEvent

# Pricing Constants
PRICING_API_CALL_CENTS = 1
PRICING_AI_TOKEN_PER_1K_CENTS = 2

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
