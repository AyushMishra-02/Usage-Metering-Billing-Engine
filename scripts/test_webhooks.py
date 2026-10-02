import os
import time
import hmac
import hashlib
import json
import requests
import stripe

webhook_secret = "whsec_mock"
stripe.api_key = "sk_test_mock"

# Tenant ID of the free tenant we created in seed
tenant_id = '11111111-1111-1111-1111-111111111111'

payload = {
    "id": "evt_test_webhook_123",
    "object": "event",
    "type": "checkout.session.completed",
    "data": {
        "object": {
            "id": "cs_test_123",
            "object": "checkout.session",
            "metadata": {
                "tenant_id": tenant_id,
                "plan_id": "pro"
            }
        }
    }
}

payload_str = json.dumps(payload, separators=(',', ':'))
timestamp = str(int(time.time()))
signed_payload = f"{timestamp}.{payload_str}"
signature = hmac.new(
    webhook_secret.encode('utf-8'),
    signed_payload.encode('utf-8'),
    hashlib.sha256
).hexdigest()

stripe_signature = f"t={timestamp},v1={signature}"

headers = {
    "stripe-signature": stripe_signature,
    "Content-Type": "application/json"
}

# 1. Send invalid signature (Probe 4)
print("Sending invalid signature...")
bad_headers = {"stripe-signature": "t=123,v1=bad_sig", "Content-Type": "application/json"}
res = requests.post("http://localhost:8000/webhooks/stripe", data=payload_str, headers=bad_headers)
print("Invalid signature response:", res.status_code, res.text)

# 2. Send valid signature (Probe 3)
print("\nSending valid signature (Free -> Pro)...")
res = requests.post("http://localhost:8000/webhooks/stripe", data=payload_str, headers=headers)
print("Valid signature response:", res.status_code, res.text)

# 3. Check Usage to see limits changed (Probe 3)
print("\nChecking usage limits...")
res = requests.get("http://localhost:8000/usage", headers={"x-tenant-id": tenant_id})
print("Usage limits:", res.json())

# 4. Replay event twice (Probe 4)
print("\nReplaying same event...")
res = requests.post("http://localhost:8000/webhooks/stripe", data=payload_str, headers=headers)
print("Replayed event response:", res.status_code, res.text)
