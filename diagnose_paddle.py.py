# diagnose_paddle.py
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SERVER_PY = ROOT / "server.py"
PADDLE_PY = ROOT / "paddle.py"
ENV_FILE = ROOT / ".env"

def ok(value: bool) -> str:
    return "✅" if value else "❌"

print("=== Diagnostic Paddle SiraPro ===")
print()

# --------------------------------------------------
# 1. Vérification des fichiers
# --------------------------------------------------

if SERVER_PY.exists():
    server_text = SERVER_PY.read_text(encoding="utf-8", errors="ignore")

    checks = [
        ("server.py contient /paddle-test", "/paddle-test" in server_text),
        ("server.py contient provider == \"paddle\"", 'provider == "paddle"' in server_text),
        ("server.py contient /webhooks/paddle", "/webhooks/paddle" in server_text),
        ("server.py contient CV_PADDLE_PRICE_", "CV_PADDLE_PRICE_" in server_text),
    ]

    for label, passed in checks:
        print(f"{ok(passed)} {label}")

    if not all(passed for _, passed in checks):
        print()
        print("👉 server.py ne semble pas être la version Paddle.")
        print("   Exécutez : python repair_paddle.py")
        print("   Puis arrêtez et relancez : python server.py")
else:
    print("❌ server.py introuvable")

print()

if PADDLE_PY.exists():
    print("✅ paddle.py existe")
else:
    print("❌ paddle.py absent")
    print("   Exécutez : python repair_paddle.py")

print()

# --------------------------------------------------
# 2. Vérification du fichier .env
# --------------------------------------------------

required_env = [
    "CV_PADDLE_ENVIRONMENT",
    "CV_PADDLE_SELLER_ID",
    "CV_PADDLE_CLIENT_TOKEN",
    "CV_PADDLE_PRICE_MONTHLY",
    "CV_PADDLE_PRICE_ANNUAL",
    "CV_PADDLE_WEBHOOK_SECRET",
]

env_values = {}

if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        if line.startswith("export "):
            line = line[7:]

        key, value = line.split("=", 1)
        env_values[key.strip()] = value.strip().strip('"').strip("'")

    for key in required_env:
        value = env_values.get(key, "")

        if not value:
            print(f"❌ Variable manquante dans .env : {key}")
        elif key == "CV_PADDLE_WEBHOOK_SECRET" and value.startswith("REMPLACEZ"):
            print(f"⚠️ {key} contient encore la valeur placeholder")
        elif key == "CV_PADDLE_CLIENT_TOKEN" and not value.startswith("test_"):
            print(f"⚠️ {key} ne commence pas par test_")
        elif key == "CV_PADDLE_PRICE_MONTHLY" and not value.startswith("pri_"):
            print(f"⚠️ {key} ne commence pas par pri_")
        elif key == "CV_PADDLE_PRICE_ANNUAL" and not value.startswith("pri_"):
            print(f"⚠️ {key} ne commence pas par pri_")
        else:
            print(f"✅ {key} défini")
else:
    print("❌ Fichier .env introuvable")
    print("   Exécutez : python repair_paddle.py")

print()

# --------------------------------------------------
# 3. Vérification du serveur local
# --------------------------------------------------

try:
    with urllib.request.urlopen("http://localhost:8000/health", timeout=3) as response:
        body = response.read().decode("utf-8")
        print(f"✅ Serveur local accessible : {body}")
except Exception as exc:
    print("❌ Serveur local inaccessible sur http://localhost:8000")
    print(f"   Erreur : {exc}")
    print("   Lancez : python server.py")

print()

# --------------------------------------------------
# 4. Test de /api/checkout avec provider=paddle
# --------------------------------------------------

payload = json.dumps(
    {
        "provider": "paddle",
        "plan": "monthly"
    }
).encode("utf-8")

request = urllib.request.Request(
    "http://localhost:8000/api/checkout",
    data=payload,
    headers={
        "Content-Type": "application/json"
    },
    method="POST"
)

try:
    with urllib.request.urlopen(request, timeout=5) as response:
        body = response.read().decode("utf-8")

        print(f"✅ /api/checkout répond HTTP {response.status}")

        try:
            data = json.loads(body)

            if data.get("provider") == "paddle":
                print("✅ Le serveur répond avec provider=paddle")

                if str(data.get("client_token", "")).startswith("test_"):
                    print("✅ client_token semble valide")
                else:
                    print("❌ client_token ne commence pas par test_")

                if str(data.get("price_id", "")).startswith("pri_"):
                    print("✅ price_id semble valide")
                else:
                    print("❌ price_id ne commence pas par pri_")

                if data.get("seller"):
                    print("✅ seller présent")
                else:
                    print("❌ seller absent")

            else:
                print("❌ Le serveur ne répond pas avec provider=paddle")

        except json.JSONDecodeError:
            print("❌ Réponse de /api/checkout n'est pas du JSON")
            print(body[:500])

except urllib.error.HTTPError as exc:
    body = exc.read().decode("utf-8", errors="ignore")

    print(f"❌ /api/checkout répond HTTP {exc.code}")
    print(body[:500])

    if "Paiement en mode test" in body:
        print()
        print("👉 Le serveur utilise encore l'ancien mode Chargily/URL.")
        print("   1. Fermez toutes les fenêtres PowerShell où server.py tourne.")
        print("   2. Exécutez : python repair_paddle.py")
        print("   3. Relancez : python server.py")

except Exception as exc:
    print("❌ Impossible d'appeler /api/checkout")
    print(f"   Erreur : {exc}")

print()
print("=== Fin du diagnostic ===")
print()
print("Si tout est vert mais que le navigateur affiche toujours :")
print("    Impossible d'ouvrir le paiement Paddle.")
print()
print("Alors ouvrez la console du navigateur avec F12, cliquez sur Payer,")
print("et copiez le message d'erreur rouge affiché dans Console.")