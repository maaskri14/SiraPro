# fix_paddle_now.py

from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SERVER_PY = ROOT / "server.py"
PADDLE_PY = ROOT / "paddle.py"
ENV_FILE = ROOT / ".env"

FORCE = "--force" in sys.argv


SERVER_PY_CONTENT = r'''
from __future__ import annotations

import json
import mimetypes
import os
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"

# ------------------------------------------------------------
# Chargement optionnel du fichier .env
# ------------------------------------------------------------
ENV_FILE = ROOT / ".env"

if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        if line.startswith("export "):
            line = line[7:]

        key, value = line.split("=", 1)

        os.environ.setdefault(
            key.strip(),
            value.strip().strip('"').strip("'")
        )

from exporters import export_docx, export_html, export_json, export_pdf, export_txt
from licensing import activate, authorization_token, verify_token

import paddle


EXPORTERS = {
    "pdf": (export_pdf, "application/pdf"),
    "docx": (export_docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    "html": (export_html, "text/html; charset=utf-8"),
    "txt": (export_txt, "text/plain; charset=utf-8"),
    "json": (export_json, "application/json; charset=utf-8"),
}


def safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^\w-]+", "-", name.strip(), flags=re.UNICODE).strip("-")
    return cleaned or "professional-cv"


class AppHandler(SimpleHTTPRequestHandler):

    def translate_path(self, path: str) -> str:
        relative = urlparse(path).path.lstrip("/") or "index.html"
        return str(STATIC / relative)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json({"status": "ok"})
            return

        if self.path == "/api/license/status":
            license_info = verify_token(authorization_token(self.headers))
            self._send_json(license_info or {"active": False, "mode": "trial"})
            return

        if self.path == "/api/payment/config":
            self._send_payment_config()
            return

        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path

        if path == "/api/license/activate":
            try:
                data = self._read_json()
                result = activate(
                    str(data.get("email", "")),
                    str(data.get("license_key", "")),
                    str(data.get("device_id", "")),
                    str(data.get("device_name", ""))
                )
                self._send_json({"active": True, **result})
            except ValueError as exc:
                self._send_json({"error": str(exc)}, 400)
            return

        if path == "/api/checkout":
            try:
                data = self._read_json()

                provider = str(data.get("provider", "chargily")).lower()
                plan = str(data.get("plan", "annual")).lower()

                if provider == "paddle":
                    self._handle_paddle_checkout(plan)
                    return

                provider = provider.upper()
                plan = plan.upper()

                url = os.getenv(f"CV_{provider}_{plan}_URL", "")

                if not url:
                    self._send_json(
                        {
                            "error": "Paiement en mode test. Configurez l'URL de paiement dans .env."
                        },
                        503
                    )
                else:
                    self._send_json({"checkout_url": url})

            except ValueError as exc:
                self._send_json({"error": str(exc)}, 400)

            return

        if path == "/webhooks/paddle":
            self._handle_paddle_webhook()
            return

        match = re.fullmatch(r"/api/export/(pdf|docx|html|txt|json)", path)

        if not match:
            self.send_error(404)
            return

        try:
            license_info = verify_token(authorization_token(self.headers))

            if not license_info:
                self._send_json(
                    {
                        "error": "Abonnement requis",
                        "code": "LICENSE_REQUIRED"
                    },
                    403
                )
                return

            data = self._read_json()

            if not isinstance(data, dict) or not str(data.get("fullName", "")).strip():
                raise ValueError("الاسم الكامل مطلوب")

            extension = match.group(1)
            exporter, content_type = EXPORTERS[extension]
            payload = exporter(data)

            filename = f"professional-cv.{extension}"

            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json({"error": str(exc)}, 400)

        except Exception:
            self._send_json(
                {
                    "error": "تعذر إنشاء الملف. تحقق من البيانات وحاول مجددًا."
                },
                500
            )

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
                    "error": "Paddle non configuré. Définissez CV_PADDLE_CLIENT_TOKEN, CV_PADDLE_SELLER_ID et CV_PADDLE_PRICE_MONTHLY/ANNUAL dans .env."
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

        except Exception as exc:
            print(f"[PADDLE] Erreur webhook : {exc}")
            self._send_json({"error": "invalid_webhook"}, 400)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))

        if length <= 0 or length > 2_000_000:
            raise ValueError("Données invalides")

        data = json.loads(self.rfile.read(length).decode("utf-8"))

        if not isinstance(data, dict):
            raise ValueError("Données invalides")

        return data

    def _send_json(self, body: dict, status: int = 200) -> None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args) -> None:
        print(f"[CV] {self.address_string()} - {format % args}")


if __name__ == "__main__":
    mimetypes.add_type("text/css", ".css")
    mimetypes.add_type("application/javascript", ".js")

    server = ThreadingHTTPServer(("0.0.0.0", 8000), AppHandler)

    print("منشئ السيرة يعمل على http://localhost:8000")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
'''


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


ENV_CONTENT = r'''
CV_PADDLE_ENVIRONMENT=sandbox
CV_PADDLE_SELLER_ID=99648
CV_PADDLE_CLIENT_TOKEN=test_45ddaa8cdb6d1f48b59a91cda9e

CV_PADDLE_PRICE_MONTHLY=pri_01kzknvgbrggy0fyh52x60x516
CV_PADDLE_PRICE_ANNUAL=pri_01kzknx5nrsjte790mp4fefkjm

# Remplacez cette valeur par le signing secret Paddle
CV_PADDLE_WEBHOOK_SECRET=REMPLACEZ_PAR_LE_SIGNING_SECRET_PADDLE

# Affiche la clé de licence dans la console pendant les tests
CV_PADDLE_DEBUG=1
'''


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def backup(path: Path) -> None:
    if path.exists():
        backup_path = path.with_suffix(path.suffix + f".backup-{timestamp()}")
        shutil.copy2(path, backup_path)
        print(f"✅ Backup créé : {backup_path.name}")


def write_file(path: Path, content: str) -> None:
    backup(path)
    path.write_text(content.lstrip("\n"), encoding="utf-8")
    print(f"✅ Fichier écrit : {path.name}")


def main() -> None:
    print("=== Correction Paddle pour SiraPro ===")

    write_file(SERVER_PY, SERVER_PY_CONTENT)
    write_file(PADDLE_PY, PADDLE_PY_CONTENT)

    if ENV_FILE.exists() and not FORCE:
        print("ℹ️  Fichier .env déjà présent. Il n'a pas été écrasé.")
    else:
        write_file(ENV_FILE, ENV_CONTENT)

    print()
    print("✅ Terminé.")
    print()
    print("Maintenant :")
    print("1. Ouvrez .env et remplacez CV_PADDLE_WEBHOOK_SECRET si vous avez déjà le secret Paddle.")
    print("2. Lancez : python server.py")
    print()
    print("Test API Paddle :")
    print('POST http://localhost:8000/api/checkout')
    print('{"provider":"paddle","plan":"monthly"}')


if __name__ == "__main__":
    main()