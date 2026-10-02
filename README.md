# Usage Metering & Billing Engine

A production-grade backend service that answers three critical SaaS questions:

1. **How much has this customer used?** — Real-time usage tracking with monthly rollups.
2. **Have they reached their plan limits?** — Quota enforcement returning `429` when exceeded.
3. **How much should they pay?** — Per-token-category cost calculation with a monthly invoice endpoint.

---

## Architecture

```
┌───────────┐       POST /generate        ┌──────────────────────┐
│  Client   │ ──────────────────────────▶  │  FastAPI Application │
│  (curl)   │ ◀──────────────────────────  │                      │
└───────────┘  200 / 402 / 429            │  ┌────────────────┐  │
                                           │  │  Billing Layer │  │
              GET /usage                   │  │  ─ quota check │  │
              GET /cost                    │  │  ─ idempotency │  │
                                           │  │  ─ cost calc   │  │
┌───────────┐  POST /checkout              │  └───────┬────────┘  │
│  Stripe   │ ◀──────────────────────────  │          │           │
│  (test)   │ ──────────────────────────▶  │  ┌───────▼────────┐  │
└───────────┘  POST /webhooks/stripe       │  │   SQLAlchemy    │  │
              (signature verified,         │  │   (SQLite /     │  │
               deduplicated)               │  │    PostgreSQL)  │  │
                                           │  └────────────────┘  │
                                           └──────────────────────┘
```

## Quick Start

```bash
# 1. Create & activate a virtual environment
python -m venv venv
.\venv\Scripts\activate        # Windows
source venv/bin/activate       # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Seed test data (Free + Pro plans, two tenants)
python scripts/seed.py

# 4. Start the server
uvicorn app.main:app --port 8000
```

## API Endpoints

| Method | Path                | Description                          |
|--------|---------------------|--------------------------------------|
| POST   | `/generate`         | Dummy billable AI endpoint           |
| GET    | `/usage`            | Current-month usage summary          |
| GET    | `/cost`             | Monthly cost rollup with line items  |
| POST   | `/checkout`         | Create Stripe checkout session       |
| POST   | `/webhooks/stripe`  | Stripe webhook (signature-verified)  |

### Example: POST /generate

```bash
curl -X POST http://localhost:8000/generate \
  -H "X-Tenant-Id: 11111111-1111-1111-1111-111111111111" \
  -H "Idempotency-Key: req-001" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Hello","input_tokens":500,"cached_tokens":200,"output_tokens":100,"reasoning_tokens":50}'
```

**Response:**
```json
{
  "status": "success",
  "message": "AI generated successfully",
  "tokens_used": 850,
  "request_cost_cents": 2.6
}
```

## Pricing Table

| Token Type        | Cost per 1,000 tokens |
|-------------------|-----------------------|
| Input tokens      | 1.5¢                  |
| Cached tokens     | 0.75¢ (50% discount)  |
| Output tokens     | 6.0¢                  |
| Reasoning tokens  | 12.0¢                 |
| API call (flat)   | 0.5¢ each             |

## Key Design Decisions

- **Idempotency**: Composite `UNIQUE(tenant_id, idempotency_key)` constraint on `usage_events` prevents double-counting on retries.
- **Quota Enforcement**: Checked per-request against the plan's monthly limits. Returns `429 Too Many Requests` when exceeded.
- **Stripe Webhooks**: Signature verification via `stripe.Webhook.construct_event`. Event IDs stored in a `stripe_events` table to deduplicate replayed webhooks.
- **Cost Rollup**: The `GET /cost` endpoint iterates usage events for the current billing period and applies the pricing table above.

## Test Tenants (seeded)

| Tenant            | ID                                     | Plan |
|-------------------|----------------------------------------|------|
| Startup Inc       | `11111111-1111-1111-1111-111111111111`| Free |
| Enterprise LLC    | `22222222-2222-2222-2222-222222222222`| Pro  |

## Limitations

- Uses SQLite locally (PostgreSQL supported via `DATABASE_URL` env var).
- Only Stripe test mode is supported.
- Does not handle mid-cycle plan downgrades/prorations.
- Monthly billing period is calendar-month (1st to 1st).
