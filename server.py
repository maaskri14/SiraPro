from __future__ import annotations
import base64
import hashlib
import hmac
import html as html_lib
import io
import json
import mimetypes
import os
import re
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, urlencode
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
        path = urlparse(self.path).path

        # VIRAL-SHARE: dynamic Facebook/social share page
        share_match = re.fullmatch(r"/s/([^/]+)", path)
        if share_match:
            self._handle_share_page(share_match.group(1))
            return

        # VIRAL-SHARE: dynamic 1200x630 social image
        card_match = re.fullmatch(r"/share-card/([^/]+)\.png", path)
        if card_match:
            self._handle_share_card(card_match.group(1))
            return
        if self.path.split("?")[0] == "/webhooks/chargily":
            self._send_json({"status": "ok"}, 200)
            return
        if self.path.split("?")[0] == "/webhooks/chargily":
            self._send_json({"status": "ok"}, 200)
            return
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
        if self.path == "/api/admin/license":  # ADMIN:route
            self._handle_admin_license()
            return
        if self.path == "/api/register_intent":  # PAYCAP:route
            self._handle_register_intent()
            return
        if self.path == "/api/claim_license":  # CLAIM:route
            self._handle_claim_license()
            return
        path = urlparse(self.path).path

        # VIRAL-SHARE: create a signed social URL for a real ATS score
        if path == "/api/share-link":
            self._handle_share_link()
            return

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

    def _handle_claim_license(self) -> None:  # CLAIM:method
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except Exception:
            self._send_json({"error": "invalid_json"}, 400)
            return
        email = str(payload.get("email", "")).strip().lower()
        checkout_id = str(payload.get("checkout_id", "")).strip()
        if "@" not in email or not checkout_id:
            self._send_json({"error": "email_and_checkout_id_required"}, 400)
            return
        import licensing
        with licensing.connect() as db:
            row = db.execute("SELECT plan FROM pending_payments WHERE checkout_id = ? AND consumed = 0", (checkout_id,)).fetchone()
            if not row:
                self._send_json({"error": "payment_not_found"}, 404)
                return
            plan = row[0]
            db.execute("UPDATE pending_payments SET consumed = 1 WHERE checkout_id = ?", (checkout_id,))
        days = 31 if plan == "monthly" else 366
        key = licensing.create_license(email, plan, days, provider="chargily", provider_ref=checkout_id)
        print(f"[CHARGILY] Licence réclamée pour {email} ({plan})", flush=True)
        try:
            import mailer
            mailer.send_license_email(email, key, plan)
        except Exception as exc:
            print(f"[MAIL] Erreur : {exc}", flush=True)
        self._send_json({"status": "license_created", "email": email, "plan": plan})


    def _handle_register_intent(self) -> None:  # PAYCAP:method
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except Exception:
            self._send_json({"error": "invalid_json"}, 400)
            return
        email = str(payload.get("email", "")).strip().lower()
        plan = payload.get("plan") if payload.get("plan") in ("monthly", "annual") else "monthly"
        if "@" not in email:
            self._send_json({"error": "invalid_email"}, 400)
            return
        import licensing
        with licensing.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS payment_intents ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, plan TEXT,"
                "consumed INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
            )
            db.execute("INSERT INTO payment_intents (email, plan) VALUES (?, ?)", (email, plan))
        print(f"[INTENT] E-mail enregistré avant paiement : {email} ({plan})", flush=True)
        self._send_json({"status": "ok"})


    def _handle_admin_license(self) -> None:  # ADMIN:method
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except Exception:
            self._send_json({"error": "invalid_json"}, 400)
            return
        import hmac as _hmac
        expected = os.getenv("CV_ADMIN_SECRET") or os.getenv("CV_LICENSE_SECRET") or ""
        secret = str(payload.get("secret", ""))
        if not expected or not _hmac.compare_digest(expected, secret):
            self._send_json({"error": "forbidden"}, 403)
            return
        email = str(payload.get("email", "")).strip().lower()
        plan = payload.get("plan") if payload.get("plan") in ("monthly", "annual") else "monthly"
        if "@" not in email:
            self._send_json({"error": "invalid_email"}, 400)
            return
        import licensing
        days = 31 if plan == "monthly" else 366
        key = licensing.create_license(email, plan, days, provider="admin", provider_ref="manual")
        sent = False
        if payload.get("send_email", True):
            try:
                import mailer
                sent = bool(mailer.send_license_email(email, key, plan))
            except Exception as exc:
                print(f"[MAIL] Erreur : {exc}", flush=True)
        print(f"[ADMIN] Licence manuelle pour {email} ({plan})", flush=True)
        self._send_json({"status": "license_created", "key": key, "email": email, "plan": plan, "email_sent": sent})

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

    # ============================================================
    # VIRAL-SHARE : liens Facebook dynamiques avec score ATS signé
    # ============================================================

    def _share_secret(self) -> bytes:
        secret = (
            os.getenv("CV_SHARE_SECRET")
            or os.getenv("CV_LICENSE_SECRET")
            or os.getenv("CV_ADMIN_SECRET")
            or ""
        )
        if not secret:
            raise RuntimeError(
                "Secret de partage absent. Définissez CV_SHARE_SECRET "
                "ou conservez CV_LICENSE_SECRET dans les variables Render."
            )
        return secret.encode("utf-8")

    def _public_origin(self) -> str:
        configured = os.getenv("CV_PUBLIC_BASE_URL", "").strip().rstrip("/")
        if configured:
            return configured

        forwarded_proto = self.headers.get("X-Forwarded-Proto", "").split(",")[0].strip()
        proto = forwarded_proto or "https"
        host = (
            self.headers.get("X-Forwarded-Host", "").split(",")[0].strip()
            or self.headers.get("Host", "sirapro.onrender.com")
        )
        return f"{proto}://{host}"

    @staticmethod
    def _b64url_encode(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    @staticmethod
    def _b64url_decode(value: str) -> bytes:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode((value + padding).encode("ascii"))

    def _make_share_token(self, score: int, ref: str, channel: str) -> str:
        payload = {
            "v": 1,
            "score": int(score),
            "ref": ref,
            "channel": channel,
            "created": int(time.time()),
        }
        raw = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":")
        ).encode("utf-8")

        signature = hmac.new(
            self._share_secret(),
            raw,
            hashlib.sha256
        ).digest()

        return f"{self._b64url_encode(raw)}.{self._b64url_encode(signature)}"

    def _decode_share_token(self, token: str):
        try:
            body_b64, sig_b64 = token.split(".", 1)
            raw = self._b64url_decode(body_b64)
            supplied = self._b64url_decode(sig_b64)

            expected = hmac.new(
                self._share_secret(),
                raw,
                hashlib.sha256
            ).digest()

            if not hmac.compare_digest(expected, supplied):
                return None

            payload = json.loads(raw.decode("utf-8"))
            score = int(payload.get("score", -1))
            if score < 0 or score > 100:
                return None

            return payload
        except Exception:
            return None

    def _handle_share_link(self) -> None:
        try:
            data = self._read_json()

            score = int(round(float(data.get("score", -1))))
            if score < 0 or score > 100:
                raise ValueError("Score ATS invalide")

            ref = re.sub(
                r"[^A-Za-z0-9_-]",
                "",
                str(data.get("ref", "")).strip()
            )[:24]

            if not ref:
                ref = "SIRAPRO"

            channel = re.sub(
                r"[^A-Za-z0-9_-]",
                "",
                str(data.get("channel", "facebook")).strip().lower()
            )[:24] or "facebook"

            token = self._make_share_token(score, ref, channel)
            share_url = f"{self._public_origin()}/s/{token}"

            self._send_json({
                "status": "ok",
                "share_url": share_url
            })
        except ValueError as exc:
            self._send_json({"error": str(exc)}, 400)
        except RuntimeError as exc:
            self._send_json({"error": str(exc)}, 503)
        except Exception as exc:
            print(f"[SHARE] Erreur création lien : {exc}", flush=True)
            self._send_json({"error": "Impossible de créer le lien de partage"}, 500)

    def _share_copy(self, score: int):
        if score >= 85:
            level = "Excellent score"
            icon = "🏆"
            title = f"{score}/100 ATS — Peux-tu battre mon score ?"
            description = (
                f"J'ai obtenu {score}/100 au test ATS SiraPro. "
                "Peux-tu battre mon score ? Teste gratuitement ton CV."
            )
        elif score >= 70:
            level = "Bon score"
            icon = "🟢"
            title = f"{score}/100 au test ATS SiraPro"
            description = (
                f"Mon CV obtient {score}/100 au test ATS SiraPro. "
                "Et le tien ? Teste gratuitement ton CV."
            )
        elif score >= 50:
            level = "Score moyen"
            icon = "🟠"
            title = f"Test ATS SiraPro : score {score}/100"
            description = (
                "Je viens de tester mon CV avec SiraPro. "
                "Découvre gratuitement ton propre score ATS."
            )
        else:
            level = "À améliorer"
            icon = "🔍"
            title = "J'ai testé mon CV avec SiraPro"
            description = (
                "Le test ATS SiraPro m'a montré les points à améliorer. "
                "Teste gratuitement ton propre CV."
            )

        return icon, level, title, description

    def _handle_share_page(self, token: str) -> None:
        payload = self._decode_share_token(token)
        if not payload:
            self.send_error(404, "Lien de partage invalide")
            return

        score = int(payload["score"])
        ref = re.sub(r"[^A-Za-z0-9_-]", "", str(payload.get("ref", "SIRAPRO")))[:24]
        channel = re.sub(
            r"[^A-Za-z0-9_-]",
            "",
            str(payload.get("channel", "facebook")).lower()
        )[:24] or "facebook"

        icon, level, title, description = self._share_copy(score)
        origin = self._public_origin()
        share_url = f"{origin}/s/{token}"
        image_url = f"{origin}/share-card/{token}.png"

        destination_query = urlencode({
            "utm_source": channel,
            "utm_medium": "organic_share",
            "utm_campaign": "ats_score",
            "ref": ref,
        })
        destination = f"/?{destination_query}"

        safe_title = html_lib.escape(title, quote=True)
        safe_description = html_lib.escape(description, quote=True)
        safe_share_url = html_lib.escape(share_url, quote=True)
        safe_image_url = html_lib.escape(image_url, quote=True)
        safe_destination = json.dumps(destination)

        page = f"""<!doctype html>
<html lang="fr-DZ" dir="ltr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">

  <title>{safe_title} | SiraPro</title>
  <meta name="description" content="{safe_description}">
  <meta name="robots" content="noindex,follow">

  <meta property="og:type" content="website">
  <meta property="og:site_name" content="SiraPro">
  <meta property="og:url" content="{safe_share_url}">
  <meta property="og:title" content="{safe_title}">
  <meta property="og:description" content="{safe_description}">
  <meta property="og:image" content="{safe_image_url}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:type" content="image/png">
  <meta property="og:locale" content="fr_DZ">

  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{safe_title}">
  <meta name="twitter:description" content="{safe_description}">
  <meta name="twitter:image" content="{safe_image_url}">

  <style>
    *{{box-sizing:border-box}}
    body{{margin:0;font-family:Arial,Helvetica,sans-serif;background:linear-gradient(135deg,#effaf6,#f5f0ff);color:#0f172a;min-height:100vh;display:grid;place-items:center;padding:24px}}
    .card{{width:min(680px,100%);background:#fff;border:1px solid #e2e8f0;border-radius:24px;padding:34px;text-align:center;box-shadow:0 20px 60px rgba(15,23,42,.12)}}
    .brand{{font-size:28px;font-weight:900;color:#1e745a}}
    .badge{{display:inline-block;margin:18px 0 8px;padding:7px 12px;border-radius:999px;background:#ede9fe;color:#6d28d9;font-weight:800}}
    .score{{font-size:clamp(58px,12vw,92px);font-weight:900;color:#7c3aed;line-height:1;margin:12px 0}}
    h1{{font-size:28px;margin:12px 0}}
    p{{color:#475569;line-height:1.65}}
    a{{display:inline-block;margin-top:15px;padding:14px 22px;border-radius:12px;background:linear-gradient(90deg,#1e745a,#7c3aed);color:#fff;text-decoration:none;font-weight:900}}
    small{{display:block;margin-top:18px;color:#94a3b8}}
  </style>
</head>
<body>
  <main class="card">
    <div class="brand">SiraPro 🇩🇿</div>
    <div class="badge">{html_lib.escape(icon)} {html_lib.escape(level)}</div>
    <div class="score">{score}/100</div>
    <h1>{html_lib.escape(title)}</h1>
    <p>{html_lib.escape(description)}</p>
    <a href="{html_lib.escape(destination, quote=True)}">🔍 Tester gratuitement mon CV</a>
    <small>Redirection vers SiraPro…</small>
  </main>

  <script>
    setTimeout(function () {{
      window.location.replace({safe_destination});
    }}, 1400);
  </script>
</body>
</html>"""

        raw = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "public, max-age=3600")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _handle_share_card(self, token: str) -> None:
        payload = self._decode_share_token(token)
        if not payload:
            self.send_error(404, "Carte invalide")
            return

        score = int(payload["score"])
        icon, level, title, description = self._share_copy(score)

        try:
            from PIL import Image, ImageDraw, ImageFont

            width, height = 1200, 630
            image = Image.new("RGB", (width, height), "#F7FBFA")
            draw = ImageDraw.Draw(image)

            # Subtle brand panels
            draw.rounded_rectangle((55, 50, 1145, 580), radius=34, fill="#FFFFFF", outline="#DDE8E4", width=3)
            draw.rounded_rectangle((75, 70, 420, 150), radius=22, fill="#E8F6F1")
            draw.rounded_rectangle((780, 70, 1125, 150), radius=22, fill="#F0EAFE")

            def load_font(size, bold=False):
                candidates = [
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
                ]
                for candidate in candidates:
                    try:
                        return ImageFont.truetype(candidate, size=size)
                    except Exception:
                        pass
                return ImageFont.load_default()

            font_brand = load_font(42, True)
            font_small = load_font(29, True)
            font_score = load_font(112, True)
            font_title = load_font(44, True)
            font_cta = load_font(30, True)

            draw.text((100, 91), "SiraPro", font=font_brand, fill="#1E745A")
            draw.text((815, 95), "CV ATS Algérie", font=font_small, fill="#7C3AED")

            # score centered
            score_text = f"{score}/100"
            bbox = draw.textbbox((0, 0), score_text, font=font_score)
            x = (width - (bbox[2] - bbox[0])) / 2
            draw.text((x, 190), score_text, font=font_score, fill="#7C3AED")

            title_text = title
            if len(title_text) > 42:
                title_text = title_text[:39] + "…"
            bbox = draw.textbbox((0, 0), title_text, font=font_title)
            x = max(90, (width - (bbox[2] - bbox[0])) / 2)
            draw.text((x, 350), title_text, font=font_title, fill="#0F172A")

            cta = "Teste gratuitement ton CV sur SiraPro"
            bbox = draw.textbbox((0, 0), cta, font=font_cta)
            x = (width - (bbox[2] - bbox[0])) / 2
            draw.text((x, 455), cta, font=font_cta, fill="#1E745A")

            draw.text((423, 520), "sirapro.onrender.com", font=font_small, fill="#475569")

            buffer = io.BytesIO()
            image.save(buffer, format="PNG", optimize=True)
            raw = buffer.getvalue()

        except Exception as exc:
            print(f"[SHARE] Carte dynamique indisponible : {exc}", flush=True)
            fallback = STATIC / "sirapro-share.png"
            if not fallback.exists():
                self.send_error(500, "Image de partage indisponible")
                return
            raw = fallback.read_bytes()

        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Cache-Control", "public, max-age=86400")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

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
    server = ThreadingHTTPServer(("0.0.0.0", int(os.getenv("PORT", "8000"))), AppHandler)  # DEPLOY:port
    print("=== SERVEUR SIRA PRO DÉMARRÉ ===")
    print(f"Seller ID : {os.getenv('CV_PADDLE_SELLER_ID', 'NON DÉFINI')}")
    print(f"Client token : {os.getenv('CV_PADDLE_CLIENT_TOKEN', 'NON DÉFINI')[:15]}...")
    print(f"URL : http://localhost:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
