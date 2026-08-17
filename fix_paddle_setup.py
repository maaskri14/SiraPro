# fix_paddle_setup.py
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
STATIC.mkdir(exist_ok=True)

# Le nouveau code Paddle.Setup correct (sans le seller)
NEW_SETUP = "Paddle.Setup({ token: config.client_token, environment: config.environment });"

# Regex pour trouver l'ancien Paddle.Setup qui contient "seller" et "token"
PATTERN = re.compile(
    r'Paddle\.Setup\(\s*\{[^}]*seller[^}]*token[^}]*environment[^}]*\}\s*\);', 
    re.IGNORECASE | re.DOTALL
)

files_to_check = [
    STATIC / "paddle-debug.html",
    STATIC / "index.html"
]

for file_path in files_to_check:
    if file_path.exists():
        content = file_path.read_text(encoding="utf-8")
        new_content, count = PATTERN.subn(NEW_SETUP, content)
        
        if count > 0:
            file_path.write_text(new_content, encoding="utf-8")
            print(f"✅ {file_path.name} corrigé ({count} remplacement(s))")
        else:
            print(f"ℹ️ {file_path.name} n'avait pas besoin de correction.")
    else:
        print(f"⚠️ {file_path.name} introuvable.")

print("\n👉 Rafraîchissez la page avec Ctrl + F5 et retestez !")