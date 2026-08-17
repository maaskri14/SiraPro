# repair_paddle.py
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SERVER_PY = ROOT / "server.py"
PADDLE_PY = ROOT / "paddle.py"
ENV_FILE = ROOT / ".env"


ENV_DEFAULTS = {
    "CV_PADDLE_ENVIRONMENT": "sandbox",
    "CV_PADDLE_SELLER_ID": "99648",
    "CV_PADDLE_CLIENT_TOKEN": "test_45ddaa8cdb6d1f48b59a91cda9e",
    "CV_PADDLE_PRICE_MONTHLY": "pri_01kzknvgbrggy0fyh52x60x516",
    "CV_PADDLE_PRICE_ANNUAL": "pri_01kzknx5nrsjte790mp4fefkjm",
    "CV_PADDLE_WEBHOOK_SECRET": "REMPLACEZ_PAR_LE_SIGNING_SECRET_PADDLE",
    "CV_PADDLE_DEBUG": "1",
}


SERVER_CODE = r'''
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

try:
    import paddle
    PADDLE_IMPORT_ERROR = None
except Exception as exc:
    paddle = None
    PADDLE_IMPORT_ERROR = str(exc)

EXPORTERS = {
    "pdf": (export_pdf, "application/pdf"),
    "docx": (
        export_docx,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ),
    "html": (export_html, "text/html; charset=utf-8"),
    "txt": (export_txt, "text/plain; charset=utf-8"),
    "json": (export_json, "application/json; charset=utf-8"),
}

PADDLE_TEST_HTML = """<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Test Paddle - SiraPro</title>
  <script src="https://cdn.paddle.com/paddle/v2/paddle.js"></script>
  <style>
    body {
      font-family: system-ui, Arial, sans-serif;
      background: #f5f7fb;
      margin: 0;
      padding: 40px 20px;
      display: flex;
      justify-content: center;
    }
    .card {
      background: white;
      width: 100%;
      max-width: 480px;
      border-radius: 16px;
      padding: 28px;
      box-shadow: 0 12px 32px rgba(0,0,0,0.12);
    }
    h1 {
      margin-top: 0;
      font-size: 24px;
    }
    label {
      display: block;
      font-weight: 600;
      margin: 18px 0 6px;
    }
    input {
      width: 100%;
      padding: 12px;
      border: 1px solid #ccd3e0;
      border-radius: 10px;
      font-size: 16px;
      box-sizing: border-box;
    }
    .plan {
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      padding: 14px;
      margin-top: 14px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
    }
    button {
      border: 0;
      border-radius: 10px;
      padding: 11px 16px;
      font-weight: 700;
      cursor: pointer;
      color: white;
      background: #2563eb;
    }
    button.green {
      background: #16a34a;
    }
    .hint {
      color: #64748b;
      font-size: 14px;
      line-height: 1.45;
      margin-top: 18px;
    }
    code {
      background: #f1f5f9;
      padding: 2px 5px;
      border-radius: 5px;
    }
  </style>
</head>
<body>
  <div class="card">
    <h1>🚀 Test Paddle Sandbox</h1>
    <p>Cette page sert uniquement à tester le paiement SiraPro Premium.</p>

    <label for="email">E-mail du client</label>
    <input id="email" type="email" placeholder="client@example.com">

    <div class="plan">
      <div>
        <strong>Premium mensuel</strong><br>
        5 USD / mois
      </div>
      <button class="green" onclick="ouvrirPaiementPaddle('monthly')">Payer</button>
    </div>

    <div class="plan">
      <div>
        <strong>Premium annuel</strong><br>
        50 USD / an
      </div>
      <button onclick="ouvrirPaiementPaddle('annual')">Payer</button>
    </div>

    <p class="hint">
      Après paiement, regardez la console du serveur Python :
      la clé de licence doit s'afficher si <code>CV_PADDLE_DEBUG=1</code>.
    </p>
  </div>

  <script>
    async function ouvrirPaiementPaddle(plan) {
      try {
        const email = document.getElementById("email").value.trim();

        if (!email || !email.includes("@")) {
          alert("Veuillez entrer un e-mail valide.");
          return;
        }

        const response = await fetch("/api/checkout", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            provider: "paddle",
            plan: plan,
            email: email
          })
        });

        const config = await response.json();

        if (!response.ok || config.error) {
          alert(config.error || "Erreur de configuration Paddle.");
          return;
        }

        if (!window.Paddle) {
          alert("Paddle JS n'est pas chargé. Vérifiez votre connexion internet.");
          return;
        }

        Paddle.Setup({
          seller: config.seller,
          token: config.client_token,
          environment: config.environment
        });

        Paddle.Checkout.open({
          items: [
            {
              priceId: config.price_id,
              quantity: 1
            }
          ],
          customer: {
            email: email
          },
          customData: {
            app: "sirapro",
            plan: plan
          },
          settings: {
            displayMode: "overlay",
            theme: "light",
            locale: "fr"
          }
        });
      } catch (error) {
        console.error(error);
        alert("Impossible d'ouvrir le paiement Paddle.");
      }
    }
  </script>
</body>
</html>
"""


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

        if self.path == "/paddle-test":
            self._send_html(PADDLE_TEST_HTML)
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

                provider = str(data.get("provider", "paddle")).lower()
                plan = str(data.get("plan", "annual")).lower()

                if provider == "paddle":
                    client_token = os.getenv("CV_PADDLE_CLIENT_TOKEN", "")
                    seller_raw = os.getenv("CV_PADDLE_SELLER_ID", "")
                    price_id = os.getenv(f"CV_PADDLE_PRICE_{plan.upper()}", "")

                    missing = []

                    if not client_token:
                        missing.append("CV_PADDLE_CLIENT_TOKEN")

                    if not seller_raw:
                        missing.append("CV_PADDLE_SELLER_ID")

                    if not price_id:
                        missing.append(f"CV_PADDLE_PRICE_{plan.upper()}")

                    if missing:
                        self._send_json(
                            {
                                "error": "Paddle mal configuré. Variables manquantes : " + ", ".join(missing)
                            },
                            503
                        )
                        return

                    try:
                        seller = int(seller_raw)
                    except ValueError:
                        self._send_json({"error": "CV_PADDLE_SELLER_ID doit être un nombre"}, 500)
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
            if paddle is None:
                self._send_json(
                    {
                        "error": "paddle.py impossible à importer",
                        "details": PADDLE_IMPORT_ERROR
                    },
                    500
                )
                return

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

    def _send_html(self, html: str, status: int = 200) -> None:
        payload = html.encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
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
    print("Page de test Paddle : http://localhost:8000/paddle-test")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
'''


PADDLE_CODE = r'''
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


WEBHOOK_SECRET = os.getenv("CV_PADDLE_WEBHOOK_SECRET", "")

MONTHLY_PRICE_ID = os.getenv(
    "CV_PADDLE_PRICE_MONTHLY",
    "pri_01kzknvgbrggy0fyh52x60x516"
)

ANNUAL_PRICE_ID = os.getenv(
    "CV_PADDLE_PRICE_ANNUAL",
    "pri_01kzknx5nrsjte790mp4fefkjm"
)

DEBUG = os.getenv("CV_PADDLE_DEBUG", "") == "1"


def verify_paddle_signature(
    raw_body: bytes,
    signature_header: str,
    secret: Optional[str] = None
) -> bool:
    secret = secret or WEBHOOK_SECRET

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
        if abs(time.time() - int(ts)) > 7 * 86400:
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


def _ensure_tables() -> None:
    with connect() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS paddle_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT,
                email TEXT,
                plan TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
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


def _find_email(obj: Any) -> Optional[str]:
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
            found = _find_email(value)
            if found:
                return found

    elif isinstance(obj, list):
        for value in obj:
            found = _find_email(value)
            if found:
                return found

    return None


def _find_price_ids(obj: Any, out: list[str]) -> None:
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
            _find_price_ids(value, out)

    elif isinstance(obj, list):
        for value in obj:
            _find_price_ids(value, out)


def _find_subscription_id(obj: Any) -> Optional[str]:
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
            found = _find_subscription_id(value)
            if found:
                return found

    elif isinstance(obj, list):
        for value in obj:
            found = _find_subscription_id(value)
            if found:
                return found

    return None


def extract_plan(data: dict[str, Any]) -> Optional[str]:
    price_ids: list[str] = []
    _find_price_ids(data, price_ids)

    for price_id in price_ids:
        if price_id == ANNUAL_PRICE_ID:
            return "annual"

        if price_id == MONTHLY_PRICE_ID:
            return "monthly"

    custom_data = data.get("custom_data") or {}

    if isinstance(custom_data, dict):
        plan = custom_data.get("plan")

        if plan in {"monthly", "annual"}:
            return plan

    return None


def _create_license_safe(
    email: str,
    plan: str,
    days: int,
    provider: str,
    provider_ref: str
) -> str:
    attempts = [
        plan,
        plan.strip(),
        plan + " "
    ]

    last_error = None

    for attempt in attempts:
        try:
            return create_license(
                email,
                attempt,
                days,
                provider=provider,
                provider_ref=provider_ref
            )
        except Exception as exc:
            last_error = exc

    try:
        return create_license(email, plan, days)
    except Exception:
        raise last_error


def _find_license_by_provider_ref(provider_ref: str):
    with connect() as db:
        row = db.execute(
            """
            SELECT id, expires_at
            FROM licenses
            WHERE provider = 'paddle'
              AND provider_ref = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (provider_ref,)
        ).fetchone()

    return row


def _extend_license(license_id: int, plan: str, days: int) -> bool:
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
            return False

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

    return True


def handle_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    _ensure_tables()

    event_id = _event_id_from_payload(payload)

    if _is_processed(event_id):
        return {"status": "duplicate"}

    event_type = str(payload.get("event_type", ""))
    data = payload.get("data") or {}

    if event_type != "transaction.completed":
        _mark_processed(event_id, event_type)

        return {
            "status": "ignored_event",
            "event_type": event_type
        }

    transaction_status = str(data.get("status", "completed")).lower()

    if transaction_status not in {"completed", "paid", "success"}:
        _mark_processed(event_id, event_type)

        return {
            "status": "ignored_transaction_status",
            "transaction_status": transaction_status
        }

    email = _find_email(data)
    plan = extract_plan(data)

    if not email or not plan:
        _mark_processed(event_id, event_type)

        return {"status": "missing_email_or_plan"}

    subscription_id = _find_subscription_id(data)
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

    key = _create_license_safe(
        email,
        plan,
        days,
        "paddle",
        provider_ref
    )

    print(f"[PADDLE] Licence créée pour {email} ({plan})")

    if DEBUG:
        print(f"[PADDLE][DEBUG] Clé de licence : {key}")

    _mark_processed(event_id, event_type, email=email, plan=plan)

    return {
        "status": "license_created",
        "email": email,
        "plan": plan
    }
'''


def backup(path: Path) -> None:
    if not path.exists():
        return

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = path.with_name(path.name + f".bak-{stamp}")
    shutil.copy2(path, target)
    print(f"✅ Backup créé : {target.name}")


def ensure_env() -> None:
    lines = []

    if ENV_FILE.exists():
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines()

    existing_keys = set()

    for line in lines:
        cleaned = line.strip()

        if not cleaned or cleaned.startswith("#") or "=" not in cleaned:
            continue

        if cleaned.startswith("export "):
            cleaned = cleaned[7:]

        existing_keys.add(cleaned.split("=", 1)[0].strip())

    missing = [
        f"{key}={value}"
        for key, value in ENV_DEFAULTS.items()
        if key not in existing_keys
    ]

    if missing:
        if lines and lines[-1].strip():
            lines.append("")

        lines.append("# Configuration Paddle ajoutée automatiquement")
        lines.extend(missing)

        ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("✅ Variables Paddle ajoutées dans .env")
    else:
        print("ℹ️ .env contient déjà les variables Paddle")


def main() -> None:
    print("=== Réparation Paddle SiraPro ===")

    ensure_env()

    backup(SERVER_PY)
    backup(PADDLE_PY)

    try:
        SERVER_PY.write_text(SERVER_CODE.lstrip("\n"), encoding="utf-8")
        PADDLE_PY.write_text(PADDLE_CODE.lstrip("\n"), encoding="utf-8")
    except PermissionError:
        print()
        print("❌ Impossible d'écrire sur server.py ou paddle.py.")
        print("   Fermez le serveur Python avec Ctrl + C, puis relancez ce script.")
        raise SystemExit(1)

    print()
    print("✅ server.py réparé avec support Paddle.")
    print("✅ paddle.py créé/mis à jour.")
    print("✅ .env vérifié.")
    print()
    print("Maintenant :")
    print("1. Lancez : python server.py")
    print("2. Ouvrez : http://localhost:8000/paddle-test")
    print("3. Cliquez sur un bouton Payer.")
    print()
    print("Important : n'utilisez plus les anciens boutons Chargily pour tester Paddle.")


if __name__ == "__main__":
    main()