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

[ ] Checkout flow in test mode
- Proof:

[ ] Webhook verification + deduplication
- Proof:

[ ] Subscription/plan synchronization
- Proof:

# Phase 4: Cost & Finalization

[ ] Cost rollups with the AI-token rules
- Proof:

[ ] README + diagram + EVIDENCE.md filled as you go
- Proof:
