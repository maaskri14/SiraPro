from __future__ import annotations

import io
import re
import unicodedata
from pathlib import Path

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d .()-]{7,}\d")


def _norm(s: str) -> str:
    # 1) Convertit les formes visuelles (ﻧﺎﺩﻳﺔ) en arabe standard (نادية)
    s = unicodedata.normalize("NFKD", s)
    # 2) Retire diacritiques + tatweel
    s = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", s)
    # 3) Unifie : أ إ آ → ا ; ى → ي ; ة → ه
    s = re.sub(r"[أإآ]", "ا", s)
    s = s.replace("ى", "ي").replace("ة", "ه")
    # 4) Chiffres arabes → latins
    s = s.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    return s


SECTIONS = {
    "experience": ["experience", "expérience", "work history", "الخبره المهنيه", "الخبرات", "خبره"],
    "education": ["education", "éducation", "formation", "التعليم", "التكوين", "الدراسه", "الشهادات"],
    "skills": ["skills", "compétences", "competences", "المهارات", "مهارات", "الكفاءات"],
    "languages": ["languages", "langues", "اللغات", "لغات"],
}

SKILLS = [
    "python","java","javascript","typescript","html","css","react","angular","vue","node","php",
    "laravel","django","flask","spring","sql","mysql","postgresql","mongodb","excel","word",
    "powerpoint","power bi","docker","git","linux","kubernetes","aws","azure","flutter","dart",
    "kotlin","swift","c++","marketing","comptabilite","communication","gestion de projet",
    "machine learning","intelligence artificielle","photoshop","illustrator","figma","autocad",
    "arduino","reseau","cybersecurite","seo","tensorflow","pytorch","pandas","numpy","unity","firebase",
    "بايثون","جافا","جافاسكريبت","رياكت","أنغولار","لارافيل","دجانغو","فلاسك","سبرينغ",
    "إكسل","وورد","باوربوينت","باور بي آي","دوكر","غيت","لينكس","فلاتر","كوتلن","سويفت",
    "تسويق","محاسبه","تواصل","إداره المشاريع","تعلم الآله","ذكاء اصطناعي","فوتوشوب","فيغما",
    "أوتوكاد","أردوينو","شبكات","أمن سيبراني","تحسين محركات البحث","قواعد البيانات","برمجه",
    "تطوير الويب","تطبيقات","يونيتي","فايربيز","إداره","مشاريع","تحليل",
]

SECTIONS_N = {k: [_norm(w) for w in v] for k, v in SECTIONS.items()}
SKILLS_N = [_norm(s) for s in SKILLS]

STOPWORDS = set((
    "the and for with are was were have has had pas pour les des une le la et de du en un que qui "
    "dans sur avec sans par vous votre vos nous notre nos je tu il elle est sont"
).split()) | {
    "في", "من", "علي", "مع", "الي", "عن", "ان", "او", "و", "التي", "الذي", "نحن", "انت",
    "هل", "ما", "لا", "مطلوب", "وظيفه", "عمل", "شركه", "فريق", "خبره", "سنوات", "يوم", "دوام",
}


def extract_text(data: bytes, kind: str) -> str:
    if kind == "pdf":
        try:
            from pypdf import PdfReader
        except Exception as exc:
            raise RuntimeError(f"Lecture PDF impossible : {exc}")
        reader = PdfReader(io.BytesIO(data))
        raw = "\n".join((p.extract_text() or "") for p in reader.pages)
    else:
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
            raw = pytesseract.image_to_string(img, lang="eng+fra+ara")
        except Exception:
            raw = pytesseract.image_to_string(img, lang="eng")

    return _norm(raw)


def _tokens(text: str):
    return [t for t in re.findall(r"[a-zàâçéèêëîïôöùûü0-9_؀-ۿ-]{3,}", text.lower())]


def analyze(text: str, job_text: str = "") -> dict:
    checks = []

    def add(label, points, ok):
        checks.append({"label": label, "points": points, "ok": bool(ok)})

    words = text.split()
    n = len(words)
    low = text.lower()

    add("Longueur adaptée (200 à 900 mots)", 20, 200 <= n <= 900)
    add("Adresse e-mail détectée", 15, EMAIL_RE.search(text))
    add("Numéro de téléphone détecté", 10, PHONE_RE.search(text))

    found_sections = [k for k, kws in SECTIONS_N.items() if any(w in low for w in kws)]
    add("Section Expérience présente", 15, "experience" in found_sections)
    add("Section Formation présente", 10, "education" in found_sections)
    add("Section Compétences présente", 10, "skills" in found_sections)
    add("Section Langues présente", 5, "languages" in found_sections)

    toks = set(_tokens(text))
    matched = [orig for orig, norm in zip(SKILLS, SKILLS_N)
               if norm in toks or norm.replace(" ", "") in low.replace(" ", "")]
    add("Mots-clés métiers détectés (5 ou plus)", 10, len(matched) >= 5)
    add("Résultats chiffrés (%, nombres)", 5, len(re.findall(r"\d+", text)) >= 3)

    total = min(100, sum(c["points"] for c in checks if c["ok"]))

    compatibility = None
    job_matched = []
    if job_text and job_text.strip():
        jn = _norm(job_text)
        jt = [t for t in set(_tokens(jn)) if t not in STOPWORDS]
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