# fix_all.py
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
SERVER_PY = ROOT / "server.py"
PADDLE_PY = ROOT / "paddle.py"
ENV_FILE = ROOT / ".env"

# 1. Sauvegarde
if SERVER_PY.exists():
    shutil.copy(SERVER_PY, SERVER_PY.with_suffix(".py.old"))
    print("✅ server.py sauvegardé")

# 2. Écriture du nouveau server.py
SERVER_PY.write_text(r'''from __future__ import annotations
import json, mimetypes, os, re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from exporters import export_docx, export_html, export_json, export_pdf, export_txt
from licensing import activate, authorization_token, verify_token
import paddle

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"

# Chargement du .env
ENV_FILE = ROOT / ".env"
if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

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
            self._send_json({"status": "ok"}); return
        if self.path == "/api/license/status":
            license_info = verify_token(authorization_token(self.headers))
            self._send_json(license_info or {"active": False, "mode": "trial"}); return
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        
        if path == "/api/license/activate":
            try:
                data = self._read_json()
                result = activate(str(data.get("email", "")), str(data.get("license_key", "")), str(data.get("device_id", "")), str(data.get("device_name", "")))
                self._send_json({"active": True, **result})
            except ValueError as exc:
                self._send_json({"error": str(exc)}, 400)
            return

        if path == "/api/checkout":
            try:
                data = self._read_json()
                provider = str(data.get("provider", "chargily")).lower()
                plan = str(data.get("plan", "annual")).lower()

                # --- LOGIQUE PADDLE ---
                if provider == "paddle":
                    seller = int(os.getenv("CV_PADDLE_SELLER_ID", "99648"))
                    self._send_json({
                        "provider": "paddle",
                        "environment": os.getenv("CV_PADDLE_ENVIRONMENT", "sandbox"),
                        "seller": seller,
                        "client_token": os.getenv("CV_PADDLE_CLIENT_TOKEN", ""),
                        "price_id": os.getenv(f"CV_PADDLE_PRICE_{plan.upper()}", ""),
                        "plan": plan
                    })
                    return
                # ----------------------

                # Fallback Chargily (ancien système)
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
            self.send_error(404); return

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
        except Exception as exc:
            self._send_json({"error": str(exc)}, 400)

    def _handle_paddle_webhook(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length)
            signature = self.headers.get("Paddle-Signature", "")
            if not paddle.verify_paddle_signature(raw_body, signature):
                self._send_json({"error": "invalid_signature"}, 400); return
            payload = json.loads(raw_body.decode("utf-8"))
            result = paddle.handle_webhook(payload)
            self._send_json(result)
        except Exception as exc:
            print(f"[PADDLE] Erreur: {exc}")
            self._send_json({"error": "invalid_webhook"}, 400)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 2_000_000: raise ValueError("Données invalides")
        data = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(data, dict): raise ValueError("Données invalides")
        return data

    def _send_json(self, body: dict, status: int = 200) -> None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", 8000), AppHandler)
    print("Serveur SiraPro démarré sur http://localhost:8000")
    server.serve_forever()
''', encoding="utf-8")
print("✅ server.py réécrit avec support Paddle")

# 3. Écriture de paddle.py (si absent ou pour forcer)
if not PADDLE_PY.exists():
    print("⚠️ paddle.py manquant. Veuillez utiliser le script précédent pour le créer.")