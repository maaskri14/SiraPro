# fix_paddle_environment.py
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"

files_to_fix = [
    STATIC / "paddle-debug.html",
    STATIC / "index.html"
]

for file_path in files_to_fix:
    if file_path.exists():
        content = file_path.read_text(encoding="utf-8")
        
        # 1. Supprimer le paramètre environment
        new_content = re.sub(
            r',?\s*environment:\s*config\.environment',
            '',
            content
        )
        
        # 2. Nettoyer la syntaxe pour avoir un Paddle.Setup({ token: ... }); propre
        new_content = re.sub(
            r'Paddle\.Setup\(\s*\{\s*token:\s*config\.client_token\s*,?\s*\}\s*\);',
            'Paddle.Setup({ token: config.client_token });',
            new_content
        )
        
        if new_content != content:
            file_path.write_text(new_content, encoding="utf-8")
            print(f"✅ {file_path.name} corrigé : 'environment' retiré de Paddle.Setup()")
        else:
            print(f"ℹ️ {file_path.name} n'avait pas besoin de correction.")
    else:
        print(f"⚠️ {file_path.name} introuvable.")

print("\n👉 Rafraîchissez la page avec Ctrl + F5 et retestez !")