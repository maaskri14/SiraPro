from __future__ import annotations
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

        # CHARGILY-WEBHOOK:route
        if path == "/webhooks/chargily":
            self._handle_chargily_webhook()
            return

        # SCAN:route
        if path == "/api/scan-score":
            self._handle_scan_score()
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

    # CHARGILY-WEBHOOK:method
    def _handle_chargily_webhook(self) -> None:
        try:
            import chargily
        except ImportError:
            self._send_json({"error": "Module chargily manquant"}, 500)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length)
            if not chargily.verify_chargily_signature(raw_body, self.headers):
                self._send_json({"error": "invalid_signature"}, 400)
                return
            payload = json.loads(raw_body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Payload invalide")
            self._send_json(chargily.handle_webhook(payload))
        except Exception as exc:
            print(f"[CHARGILY] Erreur webhook : {exc}")
            self._send_json({"error": "invalid_webhook"}, 400)

    # SCAN:methods
    def _parse_multipart(self, raw: bytes, boundary: str):
        fields = {}
        file_bytes = None
        filename = ""
        for part in raw.split(b"--" + boundary.encode()):
            if b"\r\n\r\n" not in part:
                continue
            head, body = part.split(b"\r\n\r\n", 1)
            head_text = head.decode("utf-8", errors="ignore")
            m = re.search(r'name="([^"]+)"', head_text)
            if not m:
                continue
            if 'filename="' in head_text:
                mf = re.search(r'filename="([^"]*)"', head_text)
                filename = mf.group(1) if mf else ""
                file_bytes = body.rstrip(b"\r\n")
            else:
                fields[m.group(1)] = body.rstrip(b"\r\n").decode("utf-8", errors="ignore")
        return fields, file_bytes, filename

    def _handle_scan_score(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 12_000_000:
            self._send_json({"error": "Fichier trop volumineux (max 10 Mo)"}, 400)
            return
        ctype = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in ctype:
            self._send_json({"error": "Envoi multipart requis"}, 400)
            return
        boundary = ctype.split("boundary=")[-1].strip().strip('"')
        raw = self.rfile.read(length)
        fields, file_bytes, filename = self._parse_multipart(raw, boundary)
        if not file_bytes:
            self._send_json({"error": "Aucun fichier reçu"}, 400)
            return
        kind = fields.get("kind", "") or (filename.rsplit(".", 1)[-1].lower() if filename and "." in filename else "")
        try:
            import scanner
            text = scanner.extract_text(file_bytes, kind)
            if len(text.strip()) < 40:
                self._send_json({"error": "Texte insuffisant. Photo floue ou PDF scanné sans OCR : essayez une image plus nette."}, 400)
                return
            self._send_json(scanner.analyze(text, fields.get("job", "")))
        except RuntimeError as exc:
            self._send_json({"error": str(exc)}, 500)
        except Exception as exc:
            self._send_json({"error": f"Analyse impossible : {exc}"}, 500)

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
    server = ThreadingHTTPServer(("0.0.0.0", int(os.getenv("PORT", "8000")))  # DEPLOY:port, AppHandler)
    print("=== SERVEUR SIRA PRO DÉMARRÉ ===")
    print(f"Seller ID : {os.getenv('CV_PADDLE_SELLER_ID', 'NON DÉFINI')}")
    print(f"Client token : {os.getenv('CV_PADDLE_CLIENT_TOKEN', 'NON DÉFINI')[:15]}...")
    print(f"URL : http://localhost:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
