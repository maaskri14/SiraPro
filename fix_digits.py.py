# fix_digits.py
import re
from pathlib import Path

p = Path(__file__).resolve().parent / "scanner.py"
t = p.read_text(encoding="utf-8")

new_line = 's = re.sub(r"[\\u064B-\\u065F\\u0670\\u0640]", "", s)'

t2, n = re.subn(
    r'^([ \t]*)s = re\.sub\(r"\[[^\]]*\]", "", s\)$',
    lambda m: m.group(1) + new_line,
    t,
    flags=re.M,
)

if n == 0:
    print("❌ Ligne des diacritiques introuvable dans scanner.py")
else:
    p.write_text(t2, encoding="utf-8")
    print(f"✅ {n} ligne corrigée dans scanner.py")