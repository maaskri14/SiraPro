# fix_scanner_arabic.py
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCANNER_PY = ROOT / "scanner.py"

SCANNER_CODE = r'''
from __future__ import annotations

import io
import re
from pathlib import Path

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d .()-]{7,}\d")

SECTIONS = {
    "experience": ["experience", "expérience", "experiences", "expériences", "work history", "employment",
                   "الخبرات", "خبرة", "الخبرة المهنية", "سجل العمل", "التجارب"],
    "education": ["education", "éducation", "formation", "formations", "études",
                  "تعليم", "التعليم", "التكوين", "الدراسة", "الشهادات"],
    "skills": ["skills", "compétences", "competences", "technologies",
               "مهارات", "المهارات", "الكفاءات"],
    "languages": ["languages", "langues", "لغات", "اللغات"],
}

SKILLS = [
    # Latin
    "python","java","javascript","typescript","html","css","react","angular","vue","node","php",
    "laravel","django","flask","spring","sql","mysql","postgresql","mongodb","excel","word",
    "powerpoint","power bi","docker","git","linux","kubernetes","aws","azure","flutter","dart",
    "kotlin","swift","c++","marketing","comptabilite","communication","gestion de projet",
    "machine learning","intelligence artificielle","photoshop","illustrator","figma","autocad",
    "arduino","reseau","cybersecurite","seo","tensorflow","pytorch","pandas","numpy","unity","firebase",
    # Arabe
    "بايثون","جافا","جافاسكريبت","رياكت","أنغولار","لارافيل","دجانغو","فلاسك","سبرينغ",
    "إكسل","وورد","باوربوينت","باور بي آي","دوكر","غيت","لينكس","كوبيرنيتيس","فلاتر",
    "كوتلن","سويفت","تسويق","محاسبة","تواصل","إدارة المشاريع","تعلم الآلة","ذكاء اصطناعي",
    "فوتوشوب","إليستريتور","فيغما","أوتوكاد","أردوينو","شبكات","أمن سيبراني",
    "تحسين محركات البحث","قواعد البيانات","برمجة","تطوير الويب","تطبيقات","يونيتي","فايربيز",
]

STOPWORDS = set((
    "the and for with are was were have has had pas pour les des une le la et de du en un que qui "
    "dans sur avec sans par vous votre vos nous notre nos je tu il elle est sont"
).split()) | {
    "في", "من", "على", "مع", "إلى", "عن", "أن", "أو", "و", "التي", "الذي", "نحن", "أنت",
    "هل", "ما", "لا", "مطلوب", "وظيفة", "عمل", "شركة", "فريق", "خبرة", "سنوات", "يوم", "دوام",
}


def extract_text(data: bytes, kind: str) -> str:
    if kind == "pdf":
        try:
            from pypdf import PdfReader
        except Exception as exc:
            raise RuntimeError(f"Lecture PDF impossible : {exc}")
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in reader.pages)

    try:
        import pytesseract
        from PIL import Image
    except Exception as exc:
        raise RuntimeError(f"OCR non installé : {exc}")

    for c in (r"C:\Program Files\Tesseract-OCR\tesseract.exe",
              r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"):
        if Path(c).exists():
            pytesseract.pytesseract.tesseract_cmd = c
            break

    img = Image.open(io.BytesIO(data))
    try:
        return pytesseract.image_to_string(img, lang="eng+fra+ara")
    except Exception:
        return pytesseract.image_to_string(img, lang="eng")


def _tokens(text: str):
    # Lettres latines + chiffres + lettres arabes (ٔrange \u0600-\u06FF)
    return [t for t in re.findall(r"[a-zàâçéèêëîïôöùûü0-9_؀-ۿ-]{3,}", text.lower())]


def analyze(text: str, job_text: str = "") -> dict:
    checks = []

    def add(label, points, ok):
        checks.append({"label": label, "points": points, "ok": bool(ok)})

    words = text.split()
    n = len(words)
    low = text.lower()

    add("Longueur adaptée (250 à 900 mots)", 15, 250 <= n <= 900)
    add("Adresse e-mail détectée", 15, EMAIL_RE.search(text))
    add("Numéro de téléphone détecté", 10, PHONE_RE.search(text))

    found_sections = [k for k, kws in SECTIONS.items() if any(w in low for w in kws)]
    add("Section Expérience présente", 15, "experience" in found_sections)
    add("Section Formation présente", 10, "education" in found_sections)
    add("Section Compétences présente", 10, "skills" in found_sections)
    add("Section Langues présente", 5, "languages" in found_sections)

    toks = set(_tokens(text))
    matched = [s for s in SKILLS if s in toks or s.replace(" ", "") in low.replace(" ", "")]
    add("Mots-clés métiers détectés (5 ou plus)", 10, len(matched) >= 5)
    # Chiffres latins OU arabes (٠١٢٣٤٥٧٨٩)
    add("Résultats chiffrés (%, nombres)", 5, len(re.findall(r"[\d٠-٩]+", text)) >= 3)

    total = min(100, sum(c["points"] for c in checks if c["ok"]))

    compatibility = None
    job_matched = []
    if job_text and job_text.strip():
        jt = [t for t in set(_tokens(job_text)) if t not in STOPWORDS]
        found = [t for t in jt if t in toks]
        compatibility = round(100 * len(found) / len(jt)) if jt else 0
        job_matched = found[:20]

    return {
        "ats_score": total,
        "compatibility": compatibility,
        "word_count": n,
        "checks": checks,
        "matched_skills": matched[:15],
        "sections": found_sections,
        "job_keywords_matched": job_matched,
    }
'''

SCANNER_PY.write_text(SCANNER_CODE.lstrip("\n"), encoding="utf-8")
print("✅ scanner.py réécrit avec support arabe complet")
print("👉 Redémarrez le serveur (Ctrl+C puis python server.py) et faites Ctrl+F5")