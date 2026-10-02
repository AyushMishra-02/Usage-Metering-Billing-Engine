# Usage Metering & Billing Engine Design

## 1. Plans + Quotas Defined
We offer two plans to keep things simple:
* **Free**: 1,000 API calls / month, 100,000 AI tokens / month
* **Pro**: 10,000 API calls / month, 5,000,000 AI tokens / month

## 2. Database Schema (PostgreSQL)

**tenants**
- `id`: UUID (Primary Key)
- `name`: String

**plans**
- `id`: String (Primary Key, e.g., 'free', 'pro')
- `api_call_limit`: Integer
- `ai_token_limit`: Integer

**subscriptions**
- `id`: UUID (Primary Key)
- `tenant_id`: UUID (Foreign Key -> tenants)
- `plan_id`: String (Foreign Key -> plans)
- `stripe_customer_id`: String (Nullable)
- `stripe_subscription_id`: String (Nullable)
- `status`: String (e.g., 'active', 'canceled')

**usage_events**
- `id`: UUID (Primary Key)
- `tenant_id`: UUID (Foreign Key -> tenants)
- `event_type`: String (e.g., 'api_call', 'ai_token')
- `quantity`: Integer
- `idempotency_key`: String (Unique constraint with tenant_id)
- `timestamp`: DateTime

## 3. Metering API Contract & Dummy Billable Endpoint
**Endpoint:** `POST /generate` (Dummy Billable Endpoint)
**Headers:**
- `X-Tenant-Id`: <UUID>
- `Idempotency-Key`: <String>

**Payload:**
```json
{
  "prompt": "Hello AI",
  "simulate_tokens": 2500
}
```

**Responses:**
- `200 OK`: Request successful, usage event recorded.
- `429 Too Many Requests`: Usage quota exceeded for plan.
- `402 Payment Required`: Subscription lapsed or payment required.

## 4. Idempotency Strategy
The database will have a composite `UNIQUE` constraint on `(tenant_id, idempotency_key)` in the `usage_events` table. 
1. When a billable request arrives, we calculate usage.
2. We attempt to insert the `usage_events` record.
3. If it throws a unique constraint violation, we catch the error, meaning this `idempotency_key` was already processed. We return a successful response without incrementing usage twice.
