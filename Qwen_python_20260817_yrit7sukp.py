# add_chargily_webhook.py
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SERVER_PY = ROOT / "server.py"
CHARGILY_PY = ROOT / "chargily.py"
ENV_FILE = ROOT / ".env"

# ------------------------------------------------------------
# 1) Module chargily.py (vérification + création de licence)
# ------------------------------------------------------------
CHARGILY_CODE = r'''
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from typing import Any, Optional

from licensing import connect, create_license

WEBHOOK_SECRET = os.getenv("CV_CHARGILY_WEBHOOK_SECRET", "")
MONTHLY_LINK_ID = os.getenv("CV_CHARGILY_MONTHLY_LINK_ID", "01m06dtq2agwsggna21bmfcvbc")
ANNUAL_LINK_ID = os.getenv("CV_CHARGILY_ANNUAL_LINK_ID", "01m06dsac6mshf2y9fbyfhfy1f")
DEBUG = os.getenv("CV_CHARGILY_DEBUG", "1") == "1"

SIGNATURE_HEADERS = (
    "x-chargily-signature",
    "x-chargily-webhook-signature",
    "chargily-signature",
    "x-signature",
)


def verify_chargily_signature(raw_body: bytes, headers: Any, secret: Optional[str] = None) -> bool:
    secret = secret or WEBHOOK_SECRET

    if not secret:
        print("[CHARGILY] Attention : aucun secret configuré, signature non vérifiée.")
        return True

    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256)
    expected_hex = digest.hexdigest()
    expected_b64 = base64.b64encode(digest.digest()).decode("utf-8")

    for header in SIGNATURE_HEADERS:
        sig = headers.get(header)
        if not sig:
            continue
        candidates = [sig]
        if "=" in sig:
            candidates.append(sig.split("=", 1)[1])
        for cand in candidates:
            if hmac.compare_digest(expected_hex, cand.strip()):
                return True
            if hmac.compare_digest(expected_b64, cand.strip()):
                return True
    return False


def _ensure_tables() -> None:
    with connect() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS chargily_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT,
                email TEXT,
                plan TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def _is_processed(event_id: str) -> bool:
    with connect() as db:
        row = db.execute(
            "SELECT 1 FROM chargily_events WHERE event_id = ?", (event_id,)
        ).fetchone()
    return row is not None


def _mark_processed(event_id: str, event_type: str, email: Optional[str] = None, plan: Optional[str] = None) -> None:
    with connect() as db:
        db.execute(
            "INSERT OR IGNORE INTO chargily_events (event_id, event_type, email, plan) VALUES (?, ?, ?, ?)",
            (event_id, event_type, email, plan),
        )


def _find_email(obj: Any) -> Optional[str]:
    keys = {"email", "customer_email", "payer_email", "billing_email"}
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key.lower() in keys and isinstance(value, str) and "@" in value:
                return value.strip().lower()
        for value in obj.values():
            found = _find_email(value)
            if found:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = _find_email(value)
            if found:
                return found
    return None


def _find_amounts(obj: Any, out: list) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key.lower() in {"amount", "total", "price"} and isinstance(value, (int, float)):
                out.append(int(value))
            else:
                _find_amounts(value, out)
    elif isinstance(obj, list):
        for value in obj:
            _find_amounts(value, out)


def extract_plan(payload: dict) -> Optional[str]:
    text = json.dumps(payload)

    if ANNUAL_LINK_ID and ANNUAL_LINK_ID in text:
        return "annual"
    if MONTHLY_LINK_ID and MONTHLY_LINK_ID in text:
        return "monthly"

    amounts: list = []
    _find_amounts(payload, amounts)
    for amount in amounts:
        if amount in (5000, 500000):
            return "annual"
        if amount in (500, 50000):
            return "monthly"

    plan = payload.get("plan")
    if plan in ("monthly", "annual"):
        return plan
    return None


def is_success(payload: dict) -> bool:
    event_type = str(
        payload.get("type") or payload.get("event") or payload.get("event_type") or ""
    ).lower()
    if "payment" in event_type and any(w in event_type for w in ("success", "succeeded", "completed", "paid")):
        return True

    text = json.dumps(payload).lower()
    return any(
        marker in text
        for marker in (
            '"status":"paid"',
            '"status":"succeeded"',
            '"status":"completed"',
            '"status":"success"',
            '"state":"paid"',
        )
    )


def handle_webhook(payload: dict) -> dict:
    _ensure_tables()

    event_id = str(
        payload.get("id")
        or payload.get("event_id")
        or payload.get("uuid")
        or hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    )

    if _is_processed(event_id):
        return {"status": "duplicate"}

    event_type = str(payload.get("type") or payload.get("event") or "payment")

    if not is_success(payload):
        _mark_processed(event_id, event_type)
        return {"status": "ignored_not_success"}

    email = _find_email(payload)
    plan = extract_plan(payload)

    if not email or not plan:
        _mark_processed(event_id, event_type)
        return {"status": "missing_email_or_plan"}

    days = 31 if plan == "monthly" else 366

    key = create_license(email, plan, days, provider="chargily", provider_ref=event_id)

    print(f"[CHARGILY] Licence créée pour {email} ({plan})")
    if DEBUG:
        print(f"[CHARGILY][DEBUG] Clé de licence : {key}")

    _mark_processed(event_id, event_type, email=email, plan=plan)
    return {"status": "license_created", "email": email, "plan": plan}
'''

CHARGILY_PY.write_text(CHARGILY_CODE.lstrip("\n"), encoding="utf-8")
print("✅ chargily.py créé")

# ------------------------------------------------------------
# 2) Patch de server.py (route /webhooks/chargily)
# ------------------------------------------------------------
content = SERVER_PY.read_text(encoding="utf-8")
original = content

if "CHARGILY-WEBHOOK:route" not in content:
    m = re.search(r'^([ \t]*)match = re\.fullmatch\(r"/api/export/', content, re.M)
    if not m:
        raise SystemExit("❌ Anchor /api/export introuvable dans server.py")
    ind = m.group(1)
    route = (
        f'{ind}# CHARGILY-WEBHOOK:route\n'
        f'{ind}if path == "/webhooks/chargily":\n'
        f'{ind}    self._handle_chargily_webhook()\n'
        f'{ind}    return\n\n'
    )
    content = content[:m.start()] + route + content[m.start():]

if "CHARGILY-WEBHOOK:method" not in content:
    m = re.search(r"^([ \t]*)def _read_json", content, re.M)
    if not m:
        raise SystemExit("❌ Anchor _read_json introuvable dans server.py")
    ind = m.group(1)
    method = (
        f'{ind}# CHARGILY-WEBHOOK:method\n'
        f'{ind}def _handle_chargily_webhook(self) -> None:\n'
        f'{ind}    try:\n'
        f'{ind}        import chargily\n'
        f'{ind}    except ImportError:\n'
        f'{ind}        self._send_json({{"error": "Module chargily manquant"}}, 500)\n'
        f'{ind}        return\n'
        f'{ind}    try:\n'
        f'{ind}        length = int(self.headers.get("Content-Length", "0"))\n'
        f'{ind}        raw_body = self.rfile.read(length)\n'
        f'{ind}        if not chargily.verify_chargily_signature(raw_body, self.headers):\n'
        f'{ind}            self._send_json({{"error": "invalid_signature"}}, 400)\n'
        f'{ind}            return\n'
        f'{ind}        payload = json.loads(raw_body.decode("utf-8"))\n'
        f'{ind}        if not isinstance(payload, dict):\n'
        f'{ind}            raise ValueError("Payload invalide")\n'
        f'{ind}        self._send_json(chargily.handle_webhook(payload))\n'
        f'{ind}    except Exception as exc:\n'
        f'{ind}        print(f"[CHARGILY] Erreur webhook : {{exc}}")\n'
        f'{ind}        self._send_json({{"error": "invalid_webhook"}}, 400)\n\n'
    )
    content = content[:m.start()] + method + content[m.start():]

if content != original:
    shutil.copy2(SERVER_PY, SERVER_PY.with_suffix(".py.bak-chargily"))
    SERVER_PY.write_text(content, encoding="utf-8")
    print("✅ server.py patché (backup : server.py.bak-chargily)")
else:
    print("ℹ️ server.py déjà patché")

# ------------------------------------------------------------
# 3) Mise à jour du .env
# ------------------------------------------------------------
env_lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
existing = {line.split("=", 1)[0].strip() for line in env_lines if "=" in line and not line.strip().startswith("#")}

additions = []
for key, value in {
    "CV_CHARGILY_WEBHOOK_SECRET": "",
    "CV_CHARGILY_MONTHLY_LINK_ID": "01m06dtq2agwsggna21bmfcvbc",
    "CV_CHARGILY_ANNUAL_LINK_ID": "01m06dsac6mshf2y9fbyfhfy1f",
    "CV_CHARGILY_DEBUG": "1",
}.items():
    if key not in existing:
        additions.append(f"{key}={value}")

if additions:
    ENV_FILE.write_text("\n".join(env_lines + additions) + "\n", encoding="utf-8")
    print("✅ .env complété (webhook Chargily)")

print("\n👉 Redémarrez : python server.py")