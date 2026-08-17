# set_chargily.py
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"

CHARGILY_MONTHLY = "http://pay.chargily.com/payment-links/01m06dtq2agwsggna21bmfcvbc"
CHARGILY_ANNUAL  = "http://pay.chargily.com/payment-links/01m06dsac6mshf2y9fbyfhfy1f"

if not ENV_FILE.exists():
    ENV_FILE.write_text("", encoding="utf-8")

lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
out = []
monthly_set = annual_set = False

for line in lines:
    stripped = line.strip()
    if stripped.startswith("CV_CHARGILY_MONTHLY_URL="):
        out.append(f"CV_CHARGILY_MONTHLY_URL={CHARGILY_MONTHLY}")
        monthly_set = True
    elif stripped.startswith("CV_CHARGILY_ANNUAL_URL="):
        out.append(f"CV_CHARGILY_ANNUAL_URL={CHARGILY_ANNUAL}")
        annual_set = True
    else:
        out.append(line)

if not monthly_set:
    out.append(f"CV_CHARGILY_MONTHLY_URL={CHARGILY_MONTHLY}")
if not annual_set:
    out.append(f"CV_CHARGILY_ANNUAL_URL={CHARGILY_ANNUAL}")

ENV_FILE.write_text("\n".join(out) + "\n", encoding="utf-8")
print("✅ .env mis à jour avec les liens Chargily")
print(f"   Mensuel : {CHARGILY_MONTHLY}")
print(f"   Annuel  : {CHARGILY_ANNUAL}")