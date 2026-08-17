# apply_paddle_integration.py

#!/usr/bin/env python3
"""
Application automatique de l'intégration Paddle Sandbox pour SiraPro.

Utilisation :
    python apply_paddle_integration.py

Option :
    python apply_paddle_integration.py --force

Ce script :
- crée paddle.py
- crée paddle_tests.py
- crée env.paddle.example
- patche server.py
- effectue une sauvegarde de server.py avant modification
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SERVER_PY = ROOT / "server.py"
PADDLE_PY = ROOT / "paddle.py"
PADDLE_TESTS_PY = ROOT / "paddle_tests.py"
ENV_EXAMPLE = ROOT / "env.paddle.example"

FORCE = "--force" in sys.argv


PADDLE_PY_CONTENT = r'''
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from licensing import connect, create_license


PADDLE_WEBHOOK_SECRET = os.getenv("CV_PADDLE_WEBHOOK_SECRET", "")

PADDLE_MONTHLY_PRICE_ID = os.getenv(
    "CV_PADDLE_PRICE_MONTHLY",
    "pri_01kzknvgbrggy0fyh52x60x516"
)

PADDLE_ANNUAL_PRICE_ID = os.getenv(
    "CV_PADDLE_PRICE_ANNUAL",
    "pri_01kzknx5nrsjte790mp4fefkjm"
)

DEBUG = os.getenv("CV_PADDLE_DEBUG", "") == "1"


def verify_paddle_signature(
    raw_body: bytes,
    signature_header: str,
    secret: Optional[str] = None
) -> bool:
    """
    Vérifie la signature envoyée par Paddle dans le header :
    Paddle-Signature: ts=...;h=...
    """

    secret = secret or PADDLE_WEBHOOK_SECRET

    if not raw_body or not signature_header or not secret:
        return False

    parts = {}

    for chunk in signature_header.split(";"):
        if "=" in chunk:
            key, value = chunk.split("=", 1)
            parts[key.strip()] = value.strip()

    ts = parts.get("ts")
    received = parts.get("h")

    if not ts or not received:
        return False

    # Protection simple contre les webhooks très anciens.
    try:
        if abs(time.time() - int(ts)) > 86400:
            return False
    except ValueError:
        pass

    signed_payload = ts.encode("utf-8") + b":" + raw_body

    digest = hmac.new(
        secret.encode("utf-8"),
        signed_payload,
        hashlib.sha256
    )

    expected_hex = digest.hexdigest()
    expected_base64 = base64.b64encode(digest.digest()).decode("utf-8")

    return (
        hmac.compare_digest(expected_hex, received)
        or hmac.compare_digest(expected_base64, received)
    )


def _ensure_tables(db) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS paddle_events (
            event_id TEXT PRIMARY KEY,
            event_type TEXT,
            email TEXT,
            plan TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS paddle_subscriptions (
            subscription_id TEXT PRIMARY KEY,
            email TEXT,
            plan TEXT,
            status TEXT,
            updated_at TEXT
        );
        """
    )


def _event_id_from_payload(payload: dict[str, Any]) -> str:
    event_id = (
        payload.get("event_id")
        or payload.get("notification_id")
        or payload.get("id")
    )

    if event_id:
        return str(event_id)

    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _is_processed(event_id: str) -> bool:
    with connect() as db:
        _ensure_tables(db)

        row = db.execute(
            """
            SELECT 1
            FROM paddle_events
            WHERE event_id = ?
            """,
            (event_id,)
        ).fetchone()

    return row is not None


def _mark_processed(
    event_id: str,
    event_type: str,
    email: Optional[str] = None,
    plan: Optional[str] = None
) -> None:
    with connect() as db:
        _ensure_tables(db)

        db.execute(
            """
            INSERT OR IGNORE INTO paddle_events (
                event_id,
                event_type,
                email,
                plan
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                event_id,
                event_type,
                email,
                plan
            )
        )


def _collect_price_ids(obj: Any, out: list[str]) -> None:
    if isinstance(obj, dict):
        price_id = obj.get("price_id")

        if isinstance(price_id, str):
            out.append(price_id)

        price = obj.get("price")

        if isinstance(price, dict):
            pid = price.get("id")
            if isinstance(pid, str):
                out.append(pid)

        for value in obj.values():
            _collect_price_ids(value, out)

    elif isinstance(obj, list):
        for value in obj:
            _collect_price_ids(value, out)


def _collect_email(obj: Any) -> Optional[str]:
    email_keys = {
        "email",
        "customer_email",
        "billing_email"
    }

    if isinstance(obj, dict):
        for key, value in obj.items():
            if key.lower() in email_keys:
                if isinstance(value, str) and "@" in value:
                    return value.strip().lower()

        for value in obj.values():
            found = _collect_email(value)
            if found:
                return found

    elif isinstance(obj, list):
        for value in obj:
            found = _collect_email(value)
            if found:
                return found

    return None


def extract_email(data: dict[str, Any]) -> Optional[str]:
    return _collect_email(data)


def extract_plan(data: dict[str, Any]) -> Optional[str]:
    price_ids: list[str] = []
    _collect_price_ids(data, price_ids)

    for price_id in price_ids:
        if price_id == PADDLE_ANNUAL_PRICE_ID:
            return "annual"

        if price_id == PADDLE_MONTHLY_PRICE_ID:
            return "monthly"

    custom_data = data.get("custom_data") or {}

    if isinstance(custom_data, dict):
        plan = custom_data.get("plan")

        if plan in {"monthly", "annual"}:
            return plan

    return None


def extract_subscription_id(data: dict[str, Any]) -> Optional[str]:
    def walk(obj: Any) -> Optional[str]:
        if isinstance(obj, dict):
            subscription_id = obj.get("subscription_id")

            if isinstance(subscription_id, str) and subscription_id:
                return subscription_id

            subscription = obj.get("subscription")

            if isinstance(subscription, dict):
                sub_id = subscription.get("id")
                if isinstance(sub_id, str) and sub_id:
                    return sub_id

            for value in obj.values():
                found = walk(value)
                if found:
                    return found

        elif isinstance(obj, list):
            for value in obj:
                found = walk(value)
                if found:
                    return found

        return None

    return walk(data)


def _find_license_by_provider_ref(provider_ref: str):
    with connect() as db:
        _ensure_tables(db)

        row = db.execute(
            """
            SELECT id, email, plan, status, expires_at
            FROM licenses
            WHERE provider = 'paddle'
              AND provider_ref = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (provider_ref,)
        ).fetchone()

    return row


def _extend_license(license_id: int, plan: str, days: int) -> None:
    with connect() as db:
        row = db.execute(
            """
            SELECT expires_at
            FROM licenses
            WHERE id = ?
            """,
            (license_id,)
        ).fetchone()

        if not row:
            return

        now = datetime.now(timezone.utc)

        try:
            current_expiry = datetime.fromisoformat(row["expires_at"])

            if current_expiry.tzinfo is None:
                current_expiry = current_expiry.replace(tzinfo=timezone.utc)

        except Exception:
            current_expiry = now

        base = current_expiry if current_expiry > now else now
        new_expiry = base + timedelta(days=days)

        db.execute(
            """
            UPDATE licenses
            SET status = 'active',
                plan = ?,
                expires_at = ?
            WHERE id = ?
            """,
            (
                plan,
                new_expiry.isoformat(),
                license_id
            )
        )


def deliver_license(email: str, plan: str, key: str) -> None:
    """
    En production, cette fonction doit envoyer la licence par e-mail.

    Pour le sandbox, on peut afficher la clé dans la console si
    CV_PADDLE_DEBUG=1.
    """

    print(f"[PADDLE] Licence créée pour {email} ({plan})")

    if DEBUG:
        print(f"[PADDLE][DEBUG] Clé de licence : {key}")


def handle_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    event_type = str(payload.get("event_type", ""))
    data = payload.get("data") or {}

    event_id = _event_id_from_payload(payload)

    if _is_processed(event_id):
        return {
            "status": "duplicate"
        }

    # Pour l'instant, on crée/étend une licence uniquement
    # lorsque la transaction est terminée.
    if event_type != "transaction.completed":
        _mark_processed(event_id, event_type)

        return {
            "status": "ignored_event",
            "event_type": event_type
        }

    transaction_status = str(
        data.get("status", "completed")
    ).lower()

    if transaction_status not in {"completed", "paid", "success"}:
        _mark_processed(event_id, event_type)

        return {
            "status": "ignored_transaction_status",
            "transaction_status": transaction_status
        }

    email = extract_email(data)
    plan = extract_plan(data)

    if not email or not plan:
        _mark_processed(event_id, event_type)

        return {
            "status": "missing_email_or_plan"
        }

    subscription_id = extract_subscription_id(data)
    transaction_id = str(data.get("id") or event_id)

    # Si on a un subscription_id, on l'utilise comme référence.
    # Cela permet d'étendre la même licence à chaque renouvellement.
    provider_ref = subscription_id or transaction_id

    days = 31 if plan == "monthly" else 366

    existing = _find_license_by_provider_ref(provider_ref)

    if existing:
        _extend_license(existing["id"], plan, days)
        _mark_processed(event_id, event_type, email=email, plan=plan)

        return {
            "status": "license_extended",
            "email": email,
            "plan": plan
        }

    key = create_license(
        email,
        plan,
        days,
        provider="paddle",
        provider_ref=provider_ref
    )

    deliver_license(email, plan, key)

    _mark_processed(event_id, event_type, email=email, plan=plan)

    return {
        "status": "license_created",
        "email": email,
        "plan": plan
    }
'''


PADDLE_TESTS_CONTENT = r'''
import hashlib
import hmac
import unittest

import paddle


class PaddleSignatureTests(unittest.TestCase):

    def make_signature(self, secret: str, ts: str, body: bytes) -> str:
        signed_payload = f"{ts}:".encode("utf-8") + body

        signature = hmac.new(
            secret.encode("utf-8"),
            signed_payload,
            hashlib.sha256
        ).hexdigest()

        return f"ts={ts};h={signature}"

    def test_valid_signature(self):
        secret = "test-secret"
        body = b'{"event_type":"transaction.completed"}'
        ts = "1700000000"

        header = self.make_signature(secret, ts, body)

        self.assertTrue(
            paddle.verify_paddle_signature(
                body,
                header,
                secret
            )
        )

    def test_invalid_signature(self):
        secret = "test-secret"
        body = b'{"event_type":"transaction.completed"}'

        header = "ts=1700000000;h=wrong"

        self.assertFalse(
            paddle.verify_paddle_signature(
                body,
                header,
                secret
            )
        )


if __name__ == "__main__":
    unittest.main()
'''


ENV_EXAMPLE_CONTENT = r'''
# Paddle Sandbox
CV_PADDLE_ENVIRONMENT=sandbox
CV_PADDLE_SELLER_ID=99648
CV_PADDLE_CLIENT_TOKEN=test_45ddaa8cdb6d1f48b59a91cda9e

CV_PADDLE_PRICE_MONTHLY=pri_01kzknvgbrggy0fyh52x60x516
CV_PADDLE_PRICE_ANNUAL=pri_01kzknx5nrsjte790mp4fefkjm

# A récupérer dans Paddle :
# Developer Tools -> Notifications -> Votre destination -> Signing secret
CV_PADDLE_WEBHOOK_SECRET=REMPLACEZ_PAR_LE_SIGNING_SECRET_PADDLE

# Optionnel, seulement pour afficher la clé en sandbox pendant les tests
CV_PADDLE_DEBUG=1
'''


METHODS_BLOCK = '''
# PADDLE-INTEGRATION:methods

def _send_payment_config(self) -> None:
    try:
        seller = int(os.getenv("CV_PADDLE_SELLER_ID", "99648"))
    except ValueError:
        seller = None

    self._send_json(
        {
            "paddle": {
                "environment": os.getenv("CV_PADDLE_ENVIRONMENT", "sandbox"),
                "seller": seller,
                "client_token": os.getenv("CV_PADDLE_CLIENT_TOKEN", ""),
                "prices": {
                    "monthly": os.getenv("CV_PADDLE_PRICE_MONTHLY", ""),
                    "annual": os.getenv("CV_PADDLE_PRICE_ANNUAL", "")
                }
            },
            "chargily": {
                "monthly_configured": bool(os.getenv("CV_CHARGILY_MONTHLY_URL", "")),
                "annual_configured": bool(os.getenv("CV_CHARGILY_ANNUAL_URL", ""))
            }
        }
    )


def _handle_paddle_checkout(self, plan: str) -> None:
    plan = plan.lower()

    if plan not in {"monthly", "annual"}:
        self._send_json({"error": "Plan invalide"}, 400)
        return

    client_token = os.getenv("CV_PADDLE_CLIENT_TOKEN", "")
    seller_raw = os.getenv("CV_PADDLE_SELLER_ID", "")
    price_id = os.getenv(f"CV_PADDLE_PRICE_{plan.upper()}", "")

    if not client_token or not seller_raw or not price_id:
        self._send_json(
            {
                "error": "Paddle non configuré. Définissez CV_PADDLE_CLIENT_TOKEN, CV_PADDLE_SELLER_ID et CV_PADDLE_PRICE_MONTHLY/ANNUAL."
            },
            503
        )
        return

    try:
        seller = int(seller_raw)
    except ValueError:
        self._send_json({"error": "CV_PADDLE_SELLER_ID invalide"}, 500)
        return

    self._send_json(
        {
            "provider": "paddle",
            "environment": os.getenv("CV_PADDLE_ENVIRONMENT", "sandbox"),
            "seller": seller,
            "client_token": client_token,
            "price_id": price_id,
            "plan": plan
        }
    )


def _handle_paddle_webhook(self) -> None:
    try:
        length = int(self.headers.get("Content-Length", "0"))

        if length <= 0 or length > 2_000_000:
            raise ValueError("Payload invalide")

        raw_body = self.rfile.read(length)

        signature = self.headers.get("Paddle-Signature", "")

        if not paddle.verify_paddle_signature(raw_body, signature):
            self._send_json({"error": "invalid_signature"}, 400)
            return

        payload = json.loads(raw_body.decode("utf-8"))

        if not isinstance(payload, dict):
            raise ValueError("Payload invalide")

        result = paddle.handle_webhook(payload)
        self._send_json(result)

    except json.JSONDecodeError:
        self._send_json({"error": "invalid_json"}, 400)

    except Exception:
        self._send_json({"error": "invalid_webhook"}, 400)
'''


def fail(message: str) -> None:
    raise SystemExit(f"❌ {message}")


def backup(path: Path) -> None:
    if not path.exists():
        return

    backup_path = path.with_suffix(path.suffix + ".bak-paddle")

    if not backup_path.exists():
        shutil.copy2(path, backup_path)
        print(f"✅ Backup créé : {backup_path.name}")


def write_file(path: Path, content: str, overwrite: bool = False) -> None:
    if path.exists() and not overwrite:
        print(f"ℹ️  Fichier déjà présent : {path.name}")
        return

    path.write_text(content.lstrip("\n"), encoding="utf-8")
    print(f"✅ Fichier écrit : {path.name}")


def indent_block(block: str, indent: str) -> str:
    lines = []

    for line in block.splitlines():
        if line.strip():
            lines.append(indent + line)
        else:
            lines.append("")

    return "\n".join(lines)


def ensure_import(content: str) -> str:
    if re.search(r"^import paddle\s*$", content, flags=re.M):
        return content

    pattern = re.compile(r"^from licensing import .*$", flags=re.M)

    if pattern.search(content):
        return pattern.sub(
            lambda match: match.group(0) + "\nimport paddle",
            content,
            count=1
        )

    lines = content.splitlines(keepends=True)

    for index, line in enumerate(lines):
        if line.startswith(("import ", "from ")):
            lines.insert(index + 1, "import paddle\n")
            return "".join(lines)

    return "import paddle\n" + content


def ensure_payment_config_route(content: str) -> str:
    if '"/api/payment/config"' in content:
        return content

    pattern = re.compile(r"^([ \t]*)super\(\)\.do_GET\(\)", flags=re.M)
    match = pattern.search(content)

    if not match:
        fail("Impossible de localiser super().do_GET() dans server.py")

    indent = match.group(1)

    replacement = (
        f'{indent}if self.path == "/api/payment/config":\n'
        f'{indent}    self._send_payment_config()\n'
        f'{indent}    return\n\n'
        f'{indent}super().do_GET()'
    )

    return pattern.sub(replacement, content, count=1)


def ensure_checkout_patch(content: str) -> str:
    if 'if provider == "paddle":' in content:
        return content

    pattern = re.compile(
        r'^([ \t]*)provider\s*=\s*str\(data\.get\(\s*[\'"]provider[\'"]\s*,\s*[\'"]chargily[\'"]\s*\)\)\.upper\(\)\s*\n'
        r'(?:[ \t]*\n)*'
        r'\1plan\s*=\s*str\(data\.get\(\s*[\'"]plan[\'"]\s*,\s*[\'"]annual[\'"]\s*\)\)\.upper\(\)',
        flags=re.M
    )

    match = pattern.search(content)

    if not match:
        fail(
            "Impossible de localiser le bloc /api/checkout existant dans server.py.\n"
            "Vérifiez que server.py contient bien la ligne provider = str(data.get(...)).upper()."
        )

    indent = match.group(1)

    replacement = (
        f'{indent}provider = str(data.get("provider", "chargily")).lower()\n'
        f'{indent}plan = str(data.get("plan", "annual")).lower()\n\n'
        f'{indent}# PADDLE-INTEGRATION:checkout-patch\n'
        f'{indent}if provider == "paddle":\n'
        f'{indent}    self._handle_paddle_checkout(plan)\n'
        f'{indent}    return\n\n'
        f'{indent}provider = provider.upper()\n'
        f'{indent}plan = plan.upper()'
    )

    return pattern.sub(replacement, content, count=1)


def ensure_webhook_route(content: str) -> str:
    if '"/webhooks/paddle"' in content:
        return content

    pattern = re.compile(
        r'^([ \t]*)match\s*=\s*re\.fullmatch\(r"/api/export/\(pdf\|docx\|html\|txt\|json\)", path\)',
        flags=re.M
    )

    match = pattern.search(content)

    if not match:
        fail(
            "Impossible de localiser la route /api/export/... dans server.py.\n"
            "Vérifiez que server.py contient bien match = re.fullmatch(...)."
        )

    indent = match.group(1)

    replacement = (
        f'{indent}if path == "/webhooks/paddle":\n'
        f'{indent}    self._handle_paddle_webhook()\n'
        f'{indent}    return\n\n'
        + match.group(0)
    )

    return pattern.sub(replacement, content, count=1)


def ensure_methods(content: str) -> str:
    if "def _handle_paddle_webhook(self)" in content:
        return content

    pattern = re.compile(r"^([ \t]*)def _read_json\(self\)", flags=re.M)
    match = pattern.search(content)

    if match:
        indent = match.group(1) or "    "
        insertion = indent_block(METHODS_BLOCK.strip("\n"), indent) + "\n\n"
        return content[:match.start()] + insertion + content[match.start():]

    main_pattern = re.compile(r"^if\s+__name__\s*==", flags=re.M)
    main_match = main_pattern.search(content)

    if main_match:
        insertion = indent_block(METHODS_BLOCK.strip("\n"), "    ") + "\n\n"
        return content[:main_match.start()] + insertion + content[main_match.start():]

    fail("Impossible de localiser une position pour insérer les méthodes Paddle dans server.py")
    return content


def patch_server() -> None:
    if not SERVER_PY.exists():
        fail("server.py introuvable. Exécutez ce script depuis le dossier du projet.")

    backup(SERVER_PY)

    content = SERVER_PY.read_text(encoding="utf-8")
    original = content

    content = ensure_import(content)
    content = ensure_payment_config_route(content)
    content = ensure_checkout_patch(content)
    content = ensure_webhook_route(content)
    content = ensure_methods(content)

    if content == original:
        print("ℹ️  server.py semble déjà patché.")
        return

    SERVER_PY.write_text(content, encoding="utf-8")
    print("✅ server.py patché avec succès.")


def main() -> None:
    print("=== Intégration Paddle SiraPro ===")

    write_file(PADDLE_PY, PADDLE_PY_CONTENT, overwrite=FORCE)
    write_file(PADDLE_TESTS_PY, PADDLE_TESTS_CONTENT, overwrite=FORCE)
    write_file(ENV_EXAMPLE, ENV_EXAMPLE_CONTENT, overwrite=False)

    patch_server()

    print()
    print("✅ Intégration terminée.")
    print()
    print("Prochaines étapes :")
    print("1. Définissez les variables d'environnement Paddle.")
    print("   Exemple PowerShell :")
    print()
    print('   $env:CV_PADDLE_ENVIRONMENT="sandbox"')
    print('   $env:CV_PADDLE_SELLER_ID="99648"')
    print('   $env:CV_PADDLE_CLIENT_TOKEN="test_45ddaa8cdb6d1f48b59a91cda9e"')
    print('   $env:CV_PADDLE_PRICE_MONTHLY="pri_01kzknvgbrggy0fyh52x60x516"')
    print('   $env:CV_PADDLE_PRICE_ANNUAL="pri_01kzknx5nrsjte790mp4fefkjm"')
    print('   $env:CV_PADDLE_WEBHOOK_SECRET="votre_signing_secret"')
    print('   $env:CV_PADDLE_DEBUG="1"')
    print()
    print("2. Lancez le serveur :")
    print("   python server.py")
    print()
    print("3. Configurez le webhook Paddle vers :")
    print("   https://votre-domaine/webhooks/paddle")
    print()
    print("4. En local, utilisez ngrok ou cloudflared :")
    print("   ngrok http 8000")
    print("   puis configurez https://xxxx.ngrok-free.app/webhooks/paddle")


if __name__ == "__main__":
    main()