# show_licenses.py
import sqlite3
from pathlib import Path
import os
from datetime import datetime

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"

# 1) Lire le chemin de la base de données depuis .env
db_path = ROOT / "licenses.db"
if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("CV_LICENSE_DB="):
            val = line.split("=", 1)[1].strip().strip('"').strip("'")
            if val:
                db_path = Path(val)
                break

if not db_path.exists():
    print(f"❌ Base de données introuvable : {db_path}")
    print("   Lancez d'abord le serveur ou créez une licence pour initialiser la base.")
    raise SystemExit(1)

# 2) Connexion et requête
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Vérifier si la table existe
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='licenses'")
if not cursor.fetchone():
    print("⚠️ La table 'licenses' n'existe pas encore dans la base.")
    raise SystemExit(0)

rows = cursor.execute("SELECT * FROM licenses ORDER BY id DESC").fetchall()
devices = cursor.execute("SELECT license_id, COUNT(*) as nb FROM devices GROUP BY license_id").fetchall()
dev_map = {r["license_id"]: r["nb"] for r in devices}

if not rows:
    print("📭 La base de données est vide (aucune licence créée).")
else:
    print(f"=== {len(rows)} LICENCE(S) ENREGISTRÉE(S) ===\n")
    for row in rows:
        plan = row["plan"].upper() if row["plan"] else "?"
        status = row["status"]
        expires = row["expires_at"]
        email = row["email"]
        provider = row["provider"] if "provider" in row.keys() else "manual"
        lic_id = row["id"]
        nb_dev = dev_map.get(lic_id, 0)
        
        # Formatage de la date
        try:
            exp_dt = datetime.fromisoformat(expires)
            exp_str = exp_dt.strftime("%d/%m/%Y à %H:%M")
            is_expired = exp_dt < datetime.now()
            exp_display = f"{exp_str} {'❌ EXPIRÉE' if is_expired else '⏳ Active'}"
        except Exception:
            exp_display = expires

        print(f"👤 Email     : {email}")
        print(f"📅 Expire    : {exp_display}")
        print(f"🎟️  Plan      : {plan}")
        print(f"🛡️  Statut    : {status}")
        print(f"💻 Appareils : {nb_dev} / 2")
        print(f"💳 Origine   : {provider}")
        print("-" * 40)

conn.close()