from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_HOST = os.getenv("CV_SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("CV_SMTP_PORT", "587"))
SMTP_USER = os.getenv("CV_SMTP_USER", "")
SMTP_PASS = os.getenv("CV_SMTP_PASS", "")
SENDER_NAME = os.getenv("CV_SMTP_FROM_NAME", "SiraPro")


def send_license_email(to_email: str, key: str, plan: str) -> bool:
    if not SMTP_USER or not SMTP_PASS:
        print("[MAIL] SMTP non configuré (CV_SMTP_USER / CV_SMTP_PASS) — e-mail non envoyé")
        return False

    duration = "31 jours" if plan == "monthly" else "1 an (366 jours)"
    plan_label = "Mensuel" if plan == "monthly" else "Annuel"

    text = f"""Bonjour,

Merci pour votre paiement SiraPro !

Votre clé d'activation : {key}

Plan : {plan_label} ({duration})

Activation :
1. Ouvrez l'application SiraPro.
2. Saisissez votre e-mail et cette clé dans l'écran d'activation.
3. Profitez des exports illimités !

Merci,
L'équipe SiraPro
"""

    html_body = f"""<html><body style="font-family:Arial,sans-serif;padding:24px;color:#0f172a">
<h2 style="color:#1e745a">Merci pour votre achat SiraPro !</h2>
<p>Votre clé d'activation :</p>
<p style="font-size:20px;font-weight:bold;background:#f0fdf4;border:2px dashed #1e745a;padding:12px 16px;border-radius:10px;display:inline-block">{key}</p>
<p>Plan : <b>{plan_label}</b> — durée : <b>{duration}</b></p>
<ol>
<li>Ouvrez l'application SiraPro.</li>
<li>Saisissez votre e-mail et cette clé dans l'écran d'activation.</li>
<li>Profitez des exports illimités !</li>
</ol>
<p style="color:#64748b">L'équipe SiraPro 🇩🇿</p>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "SiraPro — Votre clé d'activation"
    msg["From"] = f"{SENDER_NAME} <{SMTP_USER}>"
    msg["To"] = to_email
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=25) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, [to_email], msg.as_string())
        print(f"[MAIL] ✅ Clé envoyée à {to_email}")
        return True
    except Exception as exc:
        print(f"[MAIL] ❌ Erreur d'envoi : {exc}")
        return False