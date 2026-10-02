# Usage Metering & Billing Engine

This is the backend service that answers three critical SaaS questions:
1. How much has this customer used?
2. How much should they pay?
3. Have they reached their plan limits?

## Architecture
(Architecture diagram will be added here later)

## Setup Instructions
1. Run `docker compose up -d` to start PostgreSQL.
2. Install dependencies: `pip install -r requirements.txt`
3. Set up `.env` from `.env.example`
4. Run server: `fastapi dev app/main.py`
5. Seed data: `python scripts/seed.py`

## Limitations
- Only Stripe test mode is supported.
- Does not handle mid-cycle plan downgrades/prorations.
