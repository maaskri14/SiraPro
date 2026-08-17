# debug_pdf_text.py
import re
from pathlib import Path
from pypdf import PdfReader

pdf_path = Path(r"C:\Users\LENOVO\Downloads\نادية بن علي-CV (5).pdf")
if not pdf_path.exists():
    cands = sorted(Path.home().joinpath("Downloads").glob("*CV*.pdf"))
    if cands:
        pdf_path = cands[-1]

print("Fichier analysé :", pdf_path)
reader = PdfReader(str(pdf_path))
text = "\n".join((p.extract_text() or "") for p in reader.pages)

print("Longueur du texte :", len(text))
print("Nombre de mots :", len(text.split()))
print("Caractères arabes :", len(re.findall(r"[؀-]", text)))
print("Email trouvé :", bool(re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)))
print("\n--- 800 PREMIERS CARACTÈRES EXTRAITS ---")
print(text[:800])