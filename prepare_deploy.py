# prepare_deploy.py
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SERVER_PY = ROOT / "server.py"

(ROOT / ".gitignore").write_text("""__pycache__/
*.pyc
.env
*.db
*.db-journal
*.bak*
*.broken
*.casse
cloudflared.exe
""", encoding="utf-8")
print("✅ .gitignore créé")

(ROOT / "requirements.txt").write_text("""reportlab
python-docx
arabic-reshaper
python-bidi
pypdf
pytesseract
Pillow
""", encoding="utf-8")
print("✅ requirements.txt créé")

(ROOT / "Procfile").write_text("web: python server.py\n", encoding="utf-8")
print("✅ Procfile créé")

(ROOT / "nixpacks.toml").write_text("""[phases.setup]
nixPkgs = ["python311", "tesseract", "tessdata"]
""", encoding="utf-8")
print("✅ nixpacks.toml créé (Tesseract pour le scan OCR)")

content = SERVER_PY.read_text(encoding="utf-8")
if "DEPLOY:port" not in content:
    content2, n = re.subn(
        r'ThreadingHTTPServer\(\("0\.0\.0\.0",\s*8000\)',
        'ThreadingHTTPServer(("0.0.0.0", int(os.getenv("PORT", "8000")))  # DEPLOY:port',
        content, count=1)
    if n:
        SERVER_PY.write_text(content2, encoding="utf-8")
        print("✅ server.py : port dynamique OK")
    else:
        print("⚠️ motif port introuvable dans server.py")
else:
    print("ℹ️ port déjà dynamique")

print("\n👉 Passez à l'étape GitHub ci-dessous.")