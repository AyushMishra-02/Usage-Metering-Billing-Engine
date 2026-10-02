# Phase 2: Core Billing Logic

[x] Idempotent usage tracking with duplicate prevention
- Proof:
```
PROBE 1: First Request
{"status":"success","message":"AI generated successfully","tokens_used":1000}

PROBE 1: Second Request (Duplicate)
{"status":"success","message":"Idempotent request successful (already processed)","tokens_used":1000}
```

[x] Quota enforcement with correct status codes
- Proof:
```
PROBE 2: Hitting exact boundary
{"status":"success","message":"AI generated successfully","tokens_used":99000}

PROBE 2: Exceeding boundary
{"detail":"Quota exceeded for ai_token. Used: 100000, Requested: 1, Limit: 100000"}
HTTP_STATUS:429
```

# Phase 3: Stripe Integration

[x] Checkout flow in test mode
- Proof: Implementation present in `app/stripe_service.py` via `create_checkout_session`

[x] Webhook verification + deduplication
- Proof:
```
Sending invalid signature...
Invalid signature response: 400 {"detail":"Invalid signature"}

Replaying same event...
Replayed event response: 200 {"status":"ignored","reason":"duplicate"}
```

[x] Subscription/plan synchronization
- Proof:
```
Sending valid signature (Free -> Pro)...
Valid signature response: 200 {"status":"success"}

Checking usage limits...
Usage limits: {'tenant_id': '11111111-1111-1111-1111-111111111111', 'plan': 'pro', 'api_calls': {'used': 3, 'limit': 10000}, 'ai_tokens': {'used': 100000, 'limit': 5000000}}
```

# Phase 4: Cost & Finalization

[x] Cost rollups with the AI-token rules
- Proof:
```json
// POST /generate with mixed token types
{"status":"success","message":"AI generated successfully","tokens_used":850,"request_cost_cents":2.6}

// POST /generate with heavy reasoning
{"status":"success","message":"AI generated successfully","tokens_used":3500,"request_cost_cents":29.0}

// GET /cost — full monthly rollup
{
  "period_start": "2026-10-01T00:00:00+00:00",
  "period_end": "2026-10-02T13:05:28.082270+00:00",
  "line_items": {
    "api_calls":        {"quantity": 2,    "cost_cents": 1.0},
    "input_tokens":     {"quantity": 5850, "cost_cents": 8.775},
    "cached_tokens":    {"quantity": 200,  "cost_cents": 0.15},
    "output_tokens":    {"quantity": 600,  "cost_cents": 3.6},
    "reasoning_tokens": {"quantity": 2050, "cost_cents": 24.6}
  },
  "total_cost_cents": 38.12,
  "total_cost_usd": "$0.3812"
}
```

[x] README + diagram + EVIDENCE.md filled as you go
- Proof: This file and README.md
