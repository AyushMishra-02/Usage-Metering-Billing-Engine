from fastapi import FastAPI, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session
import uuid
import logging

from app.database import get_db, engine, Base
from app.schemas import GenerateRequest
from app.billing import check_quota_and_record_usage
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
        
    # 1. First record API call usage (quantity = 1)
    is_retry_api = check_quota_and_record_usage(
        db=db, 
        tenant_id=tenant_id_str, 
        event_type="api_call", 
        quantity=1, 
        idempotency_key=f"{idempotency_key}-api"
    )
    
    # 2. Then record AI token usage
    is_retry_ai = check_quota_and_record_usage(
        db=db, 
        tenant_id=tenant_id_str, 
        event_type="ai_token", 
        quantity=req.simulate_tokens, 
        idempotency_key=f"{idempotency_key}-token"
    )
    
    return {
        "status": "success", 
        "message": "AI generated successfully" if not is_retry_ai else "Idempotent request successful (already processed)",
        "tokens_used": req.simulate_tokens
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
