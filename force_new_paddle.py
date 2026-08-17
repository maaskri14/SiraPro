# force_new_paddle.py
import os
import sys
import time
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
SERVER_PY = ROOT / "server.py"
ENV_FILE = ROOT / ".env"

print("=== Correction forcée Paddle ===\n")

# 1. Tuer tous les processus Python sur le port 8000
print("1. Arrêt des serveurs Python...")
try:
    subprocess.run(
        ["powershell", "-Command", 
         "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"],
        capture_output=True
    )
    time.sleep(1)
    print("   ✅ Serveurs arrêtés\n")
except:
    print("   ⚠️ Aucun serveur actif\n")

# 2. Écrire le fichier .env avec les NOUVELLES valeurs
print("2. Écriture du fichier .env...")
ENV_FILE.write_text(r'''# Paddle Sandbox (NOUVEAU COMPTE)
CV_PADDLE_ENVIRONMENT=sandbox
CV_PADDLE_SELLER_ID=99817
CV_PADDLE_CLIENT_TOKEN=test_be4a1e706b368e04921ee1ab05c
CV_PADDLE_PRICE_MONTHLY=pri_01kzmhf0vyr7ep5sxxj31wdkzn
CV_PADDLE_PRICE_ANNUAL=pri_01kzmhgk71crn2v1xqwwjfhrce
CV_PADDLE_WEBHOOK_SECRET=
CV_PADDLE_DEBUG=1

# Autres
CV_LICENSE_SECRET=change-this-secret-before-production
CV_CHARGILY_MONTHLY_URL=
CV_CHARGILY_ANNUAL_URL=
''', encoding="utf-8")
print("   ✅ .env mis à jour avec Seller ID 99817\n")

# 3. Réécrire server.py avec lecture FORCÉE du .env
print("3. Réécriture de server.py...")
SERVER_PY.write_text(r'''from __future__ import annotations
import json
import mimetypes
import os
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from exporters import export_docx, export_html, export_json, export_pdf, export_txt
from licensing import activate, authorization_token, verify_token

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"

# ============================================================
# LECTURE FORCÉE DU FICHIER .ENV (écrase les variables $env:)
# ============================================================
ENV_FILE = ROOT / ".env"
if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:]
        key, value = line.split("=", 1)
        # os.environ[key] au lieu de setdefault = ÉCRASE les vieilles valeurs
        os.environ[key.strip()] = value.strip().strip('"').strip("'")

EXPORTERS = {
    "pdf": (export_pdf, "application/pdf"),
    "docx": (export_docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    "html": (export_html, "text/html; charset=utf-8"),
    "txt": (export_txt, "text/plain; charset=utf-8"),
    "json": (export_json, "application/json; charset=utf-8"),
}

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
        if self.path == "/paddle-debug.html":
            super().do_GET()
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

                # Fallback Chargily
                url = os.getenv(f"CV_{provider.upper()}_{plan.upper()}_URL", "")
                if not url:
                    self._send_json({"error": "Paiement en mode test."}, 503)
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
                self._send_json({"error": "Abonnement requis", "code": "LICENSE_REQUIRED"}, 403)
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
            self._send_json({"error": "تعذر إنشاء الملف. تحقق من البيانات وحاول مجددًا."}, 500)

    def _send_payment_config(self) -> None:
        try:
            seller = int(os.getenv("CV_PADDLE_SELLER_ID", "99817"))
        except ValueError:
            seller = None
        self._send_json({
            "paddle": {
                "environment": os.getenv("CV_PADDLE_ENVIRONMENT", "sandbox"),
                "seller": seller,
                "client_token": os.getenv("CV_PADDLE_CLIENT_TOKEN", ""),
                "prices": {
                    "monthly": os.getenv("CV_PADDLE_PRICE_MONTHLY", ""),
                    "annual": os.getenv("CV_PADDLE_PRICE_ANNUAL", "")
                }
            }
        })

    def _handle_paddle_checkout(self, plan: str) -> None:
        plan = plan.lower()
        if plan not in {"monthly", "annual"}:
            self._send_json({"error": "Plan invalide"}, 400)
            return

        seller = int(os.getenv("CV_PADDLE_SELLER_ID", "99817"))
        client_token = os.getenv("CV_PADDLE_CLIENT_TOKEN", "")
        price_id = os.getenv(f"CV_PADDLE_PRICE_{plan.upper()}", "")

        if not client_token or not price_id:
            self._send_json({"error": "Paddle non configuré dans .env"}, 503)
            return

        self._send_json({
            "provider": "paddle",
            "environment": os.getenv("CV_PADDLE_ENVIRONMENT", "sandbox"),
            "seller": seller,
            "client_token": client_token,
            "price_id": price_id,
            "plan": plan
        })

    def _handle_paddle_webhook(self) -> None:
        # Importation conditionnelle pour éviter l'erreur si paddle.py n'existe pas
        try:
            import paddle
        except ImportError:
            self._send_json({"error": "Module paddle manquant"}, 500)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length)
            signature = self.headers.get("Paddle-Signature", "")
            if not paddle.verify_paddle_signature(raw_body, signature):
                self._send_json({"error": "invalid_signature"}, 400)
                return
            payload = json.loads(raw_body.decode("utf-8"))
            result = paddle.handle_webhook(payload)
            self._send_json(result)
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
    print("=== SERVEUR SIRA PRO DÉMARRÉ ===")
    print(f"Seller ID : {os.getenv('CV_PADDLE_SELLER_ID', 'NON DÉFINI')}")
    print(f"Client token : {os.getenv('CV_PADDLE_CLIENT_TOKEN', 'NON DÉFINI')[:15]}...")
    print(f"URL : http://localhost:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
''', encoding="utf-8")
print("   ✅ server.py réécrit avec lecture forcée du .env\n")

# 4. Créer paddle.py si absent
PADDLE_PY = ROOT / "paddle.py"
if not PADDLE_PY.exists():
    print("4. Création de paddle.py...")
    PADDLE_PY.write_text(r'''from __future__ import annotations
import base64, hashlib, hmac, json, os, time
from datetime import datetime, timedelta, timezone
from licensing import connect, create_license

PADDLE_WEBHOOK_SECRET = os.getenv("CV_PADDLE_WEBHOOK_SECRET", "")
PADDLE_MONTHLY_PRICE_ID = os.getenv("CV_PADDLE_PRICE_MONTHLY", "")
PADDLE_ANNUAL_PRICE_ID = os.getenv("CV_PADDLE_PRICE_ANNUAL", "")
DEBUG = os.getenv("CV_PADDLE_DEBUG", "") == "1"

def verify_paddle_signature(raw_body: bytes, signature_header: str, secret: str = None) -> bool:
    secret = secret or PADDLE_WEBHOOK_SECRET
    if not raw_body or not signature_header or not secret:
        return False
    parts = {}
    for chunk in signature_header.split(";"):
        if "=" in chunk:
            k, v = chunk.split("=", 1)
            parts[k.strip()] = v.strip()
    ts, received = parts.get("ts"), parts.get("h")
    if not ts or not received:
        return False
    try:
        if abs(time.time() - int(ts)) > 86400:
            return False
    except:
        pass
    signed_payload = ts.encode("utf-8") + b":" + raw_body
    digest = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256)
    expected_hex = digest.hexdigest()
    expected_base64 = base64.b64encode(digest.digest()).decode("utf-8")
    return hmac.compare_digest(expected_hex, received) or hmac.compare_digest(expected_base64, received)

def _ensure_tables(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS paddle_events (
            event_id TEXT PRIMARY KEY, event_type TEXT, email TEXT, plan TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)

def _is_processed(event_id: str) -> bool:
    with connect() as db:
        _ensure_tables(db)
        return db.execute("SELECT 1 FROM paddle_events WHERE event_id = ?", (event_id,)).fetchone() is not None

def _mark_processed(event_id: str, event_type: str, email: str = None, plan: str = None):
    with connect() as db:
        _ensure_tables(db)
        db.execute("INSERT OR IGNORE INTO paddle_events (event_id, event_type, email, plan) VALUES (?, ?, ?, ?)",
                   (event_id, event_type, email, plan))

def _collect_email(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key.lower() in {"email", "customer_email", "billing_email"}:
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

def _collect_price_ids(obj, out):
    if isinstance(obj, dict):
        if "price_id" in obj and isinstance(obj["price_id"], str):
            out.append(obj["price_id"])
        if "price" in obj and isinstance(obj["price"], dict) and "id" in obj["price"]:
            out.append(obj["price"]["id"])
        for value in obj.values():
            _collect_price_ids(value, out)
    elif isinstance(obj, list):
        for value in obj:
            _collect_price_ids(value, out)

def extract_email(data):
    return _collect_email(data)

def extract_plan(data):
    price_ids = []
    _collect_price_ids(data, price_ids)
    for pid in price_ids:
        if pid == PADDLE_ANNUAL_PRICE_ID:
            return "annual"
        if pid == PADDLE_MONTHLY_PRICE_ID:
            return "monthly"
    custom_data = data.get("custom_data") or {}
    if isinstance(custom_data, dict) and custom_data.get("plan") in {"monthly", "annual"}:
        return custom_data["plan"]
    return None

def handle_webhook(payload):
    event_type = str(payload.get("event_type", ""))
    data = payload.get("data") or {}
    event_id = str(payload.get("event_id") or payload.get("id") or "")
    if not event_id:
        event_id = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()

    if _is_processed(event_id):
        return {"status": "duplicate"}

    if event_type != "transaction.completed":
        _mark_processed(event_id, event_type)
        return {"status": "ignored_event", "event_type": event_type}

    status = str(data.get("status", "completed")).lower()
    if status not in {"completed", "paid", "success"}:
        _mark_processed(event_id, event_type)
        return {"status": "ignored_transaction_status", "status": status}

    email = extract_email(data)
    plan = extract_plan(data)
    if not email or not plan:
        _mark_processed(event_id, event_type)
        return {"status": "missing_email_or_plan"}

    days = 31 if plan == "monthly" else 366
    key = create_license(email, plan, days, provider="paddle", provider_ref=event_id)

    print(f"[PADDLE] Licence créée pour {email} ({plan})")
    if DEBUG:
        print(f"[PADDLE][DEBUG] Clé de licence : {key}")

    _mark_processed(event_id, event_type, email=email, plan=plan)
    return {"status": "license_created", "email": email, "plan": plan}
''', encoding="utf-8")
    print("   ✅ paddle.py créé\n")

print("✅ Terminé !")
print("\n👉 IMPORTANT : Ouvrez un NOUVEAU terminal PowerShell et tapez :")
print("   python server.py")
print("\nPuis testez sur http://localhost:8000/paddle-debug.html avec Ctrl+F5")
print("Les logs doivent afficher : seller : 99817")