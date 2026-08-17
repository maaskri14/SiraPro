# test_chargily_webhook.py
import hashlib, hmac, json, urllib.request
from pathlib import Path

env = {}
for line in (Path(__file__).resolve().parent / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

payload = {
    "id": "chg_test_000123",
    "event": "payment.succeeded",
    "data": {
        "payment_link_id": env.get("CV_CHARGILY_MONTHLY_LINK_ID", ""),
        "amount": 500,
        "currency": "DZD",
        "status": "paid",
        "customer": {"email": "test@example.com", "name": "Client Test"}
    }
}

body = json.dumps(payload).encode("utf-8")
headers = {"Content-Type": "application/json"}
secret = env.get("CV_CHARGILY_WEBHOOK_SECRET", "")
if secret:
    headers["X-Chargily-Signature"] = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

req = urllib.request.Request("http://localhost:8000/webhooks/chargily", data=body, headers=headers, method="POST")
print(urllib.request.urlopen(req).read().decode())