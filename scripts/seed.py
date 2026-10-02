import os
import sys
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine, Base
from app.models import Tenant, Plan, Subscription

def seed_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # Check if already seeded
    if db.query(Plan).count() > 0:
        print("Database already seeded.")
        return

    print("Seeding database...")
    
    # 1. Create Plans
    free_plan = Plan(id="free", name="Free Plan", api_call_limit=1000, ai_token_limit=100000)
    pro_plan = Plan(id="pro", name="Pro Plan", api_call_limit=10000, ai_token_limit=5000000)
    
    db.add(free_plan)
    db.add(pro_plan)
    db.commit()
    
    # 2. Create Tenants
    tenant1_id = '11111111-1111-1111-1111-111111111111'
    tenant1 = Tenant(id=tenant1_id, name="Startup Inc")
    
    tenant2_id = '22222222-2222-2222-2222-222222222222'
    tenant2 = Tenant(id=tenant2_id, name="Enterprise LLC")
    
    db.add(tenant1)
    db.add(tenant2)
    db.commit()
    
    # 3. Create Subscriptions
    sub1 = Subscription(tenant_id=tenant1.id, plan_id="free", status="active")
    sub2 = Subscription(tenant_id=tenant2.id, plan_id="pro", status="active")
    
    db.add(sub1)
    db.add(sub2)
    db.commit()
    
    print(f"Seeded Tenant 1 (Free): {tenant1_id}")
    print(f"Seeded Tenant 2 (Pro): {tenant2_id}")

if __name__ == "__main__":
    seed_db()
