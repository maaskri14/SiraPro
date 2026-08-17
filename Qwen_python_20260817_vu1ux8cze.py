# test_scanner_direct.py
import re
from pathlib import Path
from pypdf import PdfReader
import scanner

pdf = Path(r"C:\Users\LENOVO\Downloads\نادية بن علي-CV (5).pdf")
reader = PdfReader(str(pdf))
raw = "\n".join((p.extract_text() or "") for p in reader.pages)

norm = scanner._norm(raw)
print("Caractères arabes après normalisation :", len(re.findall(r"[؀-ۿ]", norm)))
print("\n--- 300 premiers caractères normalisés ---")
print(norm[:300])

result = scanner.analyze(norm)
print("\nSCORE :", result["ats_score"], "/ 100")
for c in result["checks"]:
    print(("✅" if c["ok"] else "❌"), c["label"], f"(+{c['points']})")