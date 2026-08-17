# remove_test_window.py
import re
from pathlib import Path

html_file = Path(__file__).resolve().parent / "static" / "index.html"

if not html_file.exists():
    print("❌ static/index.html introuvable.")
    raise SystemExit(1)

content = html_file.read_text(encoding="utf-8")
original = content

# 1) Supprimer le bloc délimité par les marqueurs d'injection
pattern_block = re.compile(
    r"<!-- =+ -->\s*<!-- INT[ÉE]GRATION PADDLE \(Ajout[ée] automatiquement\)-->\s*<!-- =+ -->.*?<!-- =+ -->",
    re.S | re.I
)
content = pattern_block.sub("", content)

# 2) Sécurité : supprimer la zone de test flottante
content = re.sub(r'<div id="paddle-test-zone".*?</div>', "", content, flags=re.S)

# 3) Sécurité : supprimer la fonction de test Paddle
content = re.sub(r"<script>\s*async function ouvrirPaiementPaddle.*?</script>", "", content, flags=re.S)

# 4) Sécurité : supprimer le script Paddle ajouté par l'injection
if "ouvrirPaiementPaddle" not in content:
    content = content.replace('<script src="https://cdn.paddle.com/paddle/v2/paddle.js"></script>', "")

# Nettoyer les lignes vides en trop
content = re.sub(r"\n{3,}", "\n\n", content)

if content != original:
    html_file.write_text(content, encoding="utf-8")
    print("✅ Fenêtre de test Paddle supprimée de static/index.html")
else:
    print("ℹ️ Aucune fenêtre de test trouvée dans static/index.html")

print("👉 Rechargez la page avec Ctrl + F5")