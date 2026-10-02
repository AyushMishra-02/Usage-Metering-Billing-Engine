import stripe
import os
from fastapi import HTTPException

# Configure Stripe with test mode key
stripe.api_key = os.getenv("STRIPE_API_KEY", "sk_test_mock")
webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_mock")

def create_checkout_session(tenant_id: str, plan_id: str, success_url: str, cancel_url: str):
    # Map your local plans to Stripe Price IDs in a real scenario
    # For test mode, we can just create an inline price
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f"{plan_id.capitalize()} Plan",
                    },
                    'unit_amount': 2000 if plan_id == "pro" else 0,
                    'recurring': {'interval': 'month'},
                },
                'quantity': 1,
            }],
            mode='subscription',
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=tenant_id,
            metadata={"tenant_id": tenant_id, "plan_id": plan_id}
        )
        return session.url
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def verify_webhook_signature(payload: bytes, sig_header: str):
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
        return event
    except ValueError as e:
        # Invalid payload
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        raise HTTPException(status_code=400, detail="Invalid signature")
