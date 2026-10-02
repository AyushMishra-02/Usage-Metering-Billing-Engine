from fastapi import FastAPI, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session
import uuid
import logging

from app.database import get_db, engine, Base
from app.schemas import GenerateRequest, CheckoutRequest
from app.stripe_service import create_checkout_session, verify_webhook_signature
from app.billing import check_quota_and_record_usage, get_cost_rollup
from app.models import Tenant

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create tables if not exist (in production use Alembic)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Usage Metering & Billing Engine")

@app.post("/generate")
def generate_ai_response(
    req: GenerateRequest,
    x_tenant_id: str = Header(...),
    idempotency_key: str = Header(...),
    db: Session = Depends(get_db)
):
    try:
        tenant_uuid = uuid.UUID(x_tenant_id)
        tenant_id_str = str(tenant_uuid)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant ID format")
        
    # Check if tenant exists
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id_str).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
        
    total_tokens = req.input_tokens + req.cached_tokens + req.output_tokens + req.reasoning_tokens
    if total_tokens <= 0:
        raise HTTPException(status_code=400, detail="At least one token category must be > 0")

    # 1. Record API call usage (quantity = 1)
    is_retry_api = check_quota_and_record_usage(
        db=db, tenant_id=tenant_id_str, event_type="api_call",
        quantity=1, idempotency_key=f"{idempotency_key}-api",
    )

    # 2. Record each token category separately (quota checks against total ai_token budget)
    token_categories = [
        ("input_tokens",     req.input_tokens),
        ("cached_tokens",    req.cached_tokens),
        ("output_tokens",    req.output_tokens),
        ("reasoning_tokens", req.reasoning_tokens),
    ]
    is_retry = is_retry_api
    for cat, qty in token_categories:
        if qty > 0:
            # Quota enforcement is against the combined ai_token limit
            check_quota_and_record_usage(
                db=db, tenant_id=tenant_id_str, event_type="ai_token",
                quantity=qty, idempotency_key=f"{idempotency_key}-{cat}",
            )
            # Also record the granular event for cost rollup
            ret = check_quota_and_record_usage(
                db=db, tenant_id=tenant_id_str, event_type=cat,
                quantity=qty, idempotency_key=f"{idempotency_key}-{cat}-detail",
            )
            is_retry = is_retry or ret

    from app.billing import calculate_token_cost_cents, COST_API_CALL_CENTS
    request_cost = calculate_token_cost_cents(
        req.input_tokens, req.cached_tokens, req.output_tokens, req.reasoning_tokens
    ) + COST_API_CALL_CENTS

    return {
        "status": "success",
        "message": "AI generated successfully" if not is_retry else "Idempotent request (already processed)",
        "tokens_used": total_tokens,
        "request_cost_cents": round(request_cost, 4),
    }

@app.get("/usage")
def get_usage(x_tenant_id: str = Header(...), db: Session = Depends(get_db)):
    # Simple endpoint to view current usage (for validation)
    from app.models import Subscription, UsageEvent
    from sqlalchemy import func
    import datetime
    
    try:
        tenant_uuid = uuid.UUID(x_tenant_id)
        tenant_id_str = str(tenant_uuid)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant ID format")
        
    subscription = db.query(Subscription).filter(Subscription.tenant_id == tenant_id_str).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
        
    now = datetime.datetime.now(datetime.timezone.utc)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    api_usage = db.query(func.sum(UsageEvent.quantity)).filter(
        UsageEvent.tenant_id == tenant_id_str,
        UsageEvent.event_type == 'api_call',
        UsageEvent.timestamp >= start_of_month
    ).scalar() or 0
    
    token_usage = db.query(func.sum(UsageEvent.quantity)).filter(
        UsageEvent.tenant_id == tenant_id_str,
        UsageEvent.event_type == 'ai_token',
        UsageEvent.timestamp >= start_of_month
    ).scalar() or 0
    
    plan = subscription.plan
    
    return {
        "tenant_id": str(tenant_uuid),
        "plan": plan.id,
        "api_calls": {
            "used": api_usage,
            "limit": plan.api_call_limit
        },
        "ai_tokens": {
            "used": token_usage,
            "limit": plan.ai_token_limit
        }
    }

@app.get("/cost")
def get_cost(x_tenant_id: str = Header(...), db: Session = Depends(get_db)):
    """Monthly cost rollup for a tenant."""
    try:
        tenant_id_str = str(uuid.UUID(x_tenant_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant ID format")
    return get_cost_rollup(db, tenant_id_str)

@app.post("/checkout")
def create_checkout(req: CheckoutRequest, db: Session = Depends(get_db)):
    url = create_checkout_session(
        tenant_id=req.tenant_id,
        plan_id=req.plan_id,
        success_url="http://localhost:8000/success",
        cancel_url="http://localhost:8000/cancel"
    )
    return {"url": url}

@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    from app.models import StripeEvent, Subscription
    
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    
    event = verify_webhook_signature(payload, sig_header)
    
    # Deduplicate event
    existing_event = db.query(StripeEvent).filter(StripeEvent.id == event.id).first()
    if existing_event:
        return {"status": "ignored", "reason": "duplicate"}
        
    # Process event
    if event.type == 'checkout.session.completed':
        session = event.data.object
        
        tenant_id = None
        plan_id = None
        
        if hasattr(session, 'metadata') and session.metadata:
            meta_dict = session.metadata.to_dict()
            tenant_id = meta_dict.get("tenant_id")
            plan_id = meta_dict.get("plan_id")
            
        if tenant_id and plan_id:
            # Update subscription
            subscription = db.query(Subscription).filter(Subscription.tenant_id == tenant_id).first()
            if subscription:
                subscription.plan_id = plan_id
                
    # Record event to prevent duplicate processing
    db.add(StripeEvent(id=event.id))
    db.commit()
        
    return {"status": "success"}
