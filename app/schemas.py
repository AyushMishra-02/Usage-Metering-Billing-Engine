from pydantic import BaseModel
from typing import Optional
import uuid

class GenerateRequest(BaseModel):
    prompt: str
    simulate_tokens: int

class UsageResponse(BaseModel):
    message: str
    used: int
    limit: int
    cost_cents: int = 0

class CheckoutRequest(BaseModel):
    tenant_id: str
    plan_id: str
