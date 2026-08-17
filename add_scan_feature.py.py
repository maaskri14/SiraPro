# add_scan_feature.py
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SERVER_PY = ROOT / "server.py"
SCANNER_PY = ROOT / "scanner.py"
HTML = ROOT / "static" / "index.html"
REQ = ROOT / "requirements.txt"

# ------------------------------------------------------------
# 1) Module scanner.py (OCR + analyse)
# ------------------------------------------------------------
SCANNER_CODE = r'''
from __future__ import annotations

import io
import re
from pathlib import Path

try:
    import pytesseract
    from PIL import Image
    HAS_OCR = True
    for _c in (r"C:\Program Files\Tesseract-OCR\tesseract.exe",
               r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"):
        if Path(_c).exists():
            pytesseract.pytesseract.tesseract_cmd = _c
            break
except Exception:
    HAS_OCR = False

try:
    from pypdf import PdfReader
    HAS_PDF = True
except Exception:
    HAS_PDF = False

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d .()-]{7,}\d")

SECTIONS = {
    "experience": ["experience", "expérience", "experiences", "expériences", "work history", "employment", "الخبرات", "خبرة"],
    "education": ["education", "éducation", "formation", "formations", "études", "تعليم"],
    "skills": ["skills", "compétences", "competences", "technologies", "مهارات"],
    "languages": ["languages", "langues", "لغات"],
}

SKILLS = ["python","java","javascript","typescript","html","css","react","angular","vue","node","php","laravel","django","flask","spring","sql","mysql","postgresql","mongodb","excel","word","powerpoint","power bi","docker","git","linux","kubernetes","aws","azure","flutter","dart","kotlin","swift","c++","marketing","comptabilite","communication","gestion de projet","machine learning","intelligence artificielle","photoshop","illustrator","figma","autocad","arduino","reseau","cybersecurite","seo","tensorflow","pytorch","pandas","numpy","unity","firebase","bootstrap"]

STOPWORDS = set("the and for with are was were have has had pas pour les des une le la et de du en un que qui dans sur avec sans par vous votre vos nous notre nos je tu il elle est sont".split())


def extract_text(data: bytes, kind: str) -> str:
    if kind == "pdf":
        if not HAS_PDF:
            raise RuntimeError("Lecture PDF non installée (pip install pypdf)")
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((p.extract_text() or "") for p in reader.pages)
        return text
    if not HAS_OCR:
        raise RuntimeError("OCR non installé (pip install pytesseract pillow + Tesseract)")
    img = Image.open(io.BytesIO(data))
    try:
        return pytesseract.image_to_string(img, lang="eng+fra+ara")
    except Exception:
        return pytesseract.image_to_string(img, lang="eng")


def _tokens(text: str):
    return [t for t in re.findall(r"[a-zàâçéèêëîïôöùûü0-9_-]{3,}", text.lower())]


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
    add("Résultats chiffrés (%, nombres)", 5, len(re.findall(r"\d+", text)) >= 3)

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
print("✅ scanner.py créé")

# ------------------------------------------------------------
# 2) Patch server.py
# ------------------------------------------------------------
content = SERVER_PY.read_text(encoding="utf-8")
original = content

if "SCAN:route" not in content:
    m = re.search(r'^([ \t]*)match = re\.fullmatch\(r"/api/export/', content, re.M)
    if not m:
        raise SystemExit("❌ Anchor /api/export introuvable")
    ind = m.group(1)
    route = (
        f'{ind}# SCAN:route\n'
        f'{ind}if path == "/api/scan-score":\n'
        f'{ind}    self._handle_scan_score()\n'
        f'{ind}    return\n\n'
    )
    content = content[:m.start()] + route + content[m.start():]

if "SCAN:methods" not in content:
    m = re.search(r"^([ \t]*)def _read_json", content, re.M)
    if not m:
        raise SystemExit("❌ Anchor _read_json introuvable")
    ind = m.group(1)
    methods = (
        f'{ind}# SCAN:methods\n'
        f'{ind}def _parse_multipart(self, raw: bytes, boundary: str):\n'
        f'{ind}    fields = {{}}\n'
        f'{ind}    file_bytes = None\n'
        f'{ind}    filename = ""\n'
        f'{ind}    for part in raw.split(b"--" + boundary.encode()):\n'
        f'{ind}        if b"\\r\\n\\r\\n" not in part:\n'
        f'{ind}            continue\n'
        f'{ind}        head, body = part.split(b"\\r\\n\\r\\n", 1)\n'
        f'{ind}        head_text = head.decode("utf-8", errors="ignore")\n'
        f'{ind}        m = re.search(r\'name="([^"]+)"\', head_text)\n'
        f'{ind}        if not m:\n'
        f'{ind}            continue\n'
        f'{ind}        if \'filename="\' in head_text:\n'
        f'{ind}            mf = re.search(r\'filename="([^"]*)"\', head_text)\n'
        f'{ind}            filename = mf.group(1) if mf else ""\n'
        f'{ind}            file_bytes = body.rstrip(b"\\r\\n")\n'
        f'{ind}        else:\n'
        f'{ind}            fields[m.group(1)] = body.rstrip(b"\\r\\n").decode("utf-8", errors="ignore")\n'
        f'{ind}    return fields, file_bytes, filename\n\n'
        f'{ind}def _handle_scan_score(self) -> None:\n'
        f'{ind}    length = int(self.headers.get("Content-Length", "0"))\n'
        f'{ind}    if length <= 0 or length > 12_000_000:\n'
        f'{ind}        self._send_json({{"error": "Fichier trop volumineux (max 10 Mo)"}}, 400)\n'
        f'{ind}        return\n'
        f'{ind}    ctype = self.headers.get("Content-Type", "")\n'
        f'{ind}    if "multipart/form-data" not in ctype:\n'
        f'{ind}        self._send_json({{"error": "Envoi multipart requis"}}, 400)\n'
        f'{ind}        return\n'
        f'{ind}    boundary = ctype.split("boundary=")[-1].strip().strip(\'"\')\n'
        f'{ind}    raw = self.rfile.read(length)\n'
        f'{ind}    fields, file_bytes, filename = self._parse_multipart(raw, boundary)\n'
        f'{ind}    if not file_bytes:\n'
        f'{ind}        self._send_json({{"error": "Aucun fichier reçu"}}, 400)\n'
        f'{ind}        return\n'
        f'{ind}    kind = fields.get("kind", "") or (filename.rsplit(".", 1)[-1].lower() if filename and "." in filename else "")\n'
        f'{ind}    try:\n'
        f'{ind}        import scanner\n'
        f'{ind}        text = scanner.extract_text(file_bytes, kind)\n'
        f'{ind}        if len(text.strip()) < 40:\n'
        f'{ind}            self._send_json({{"error": "Texte insuffisant. Photo floue ou PDF scanné sans OCR : essayez une image plus nette."}}, 400)\n'
        f'{ind}            return\n'
        f'{ind}        self._send_json(scanner.analyze(text, fields.get("job", "")))\n'
        f'{ind}    except RuntimeError as exc:\n'
        f'{ind}        self._send_json({{"error": str(exc)}}, 500)\n'
        f'{ind}    except Exception as exc:\n'
        f'{ind}        self._send_json({{"error": f"Analyse impossible : {{exc}}"}}, 500)\n\n'
    )
    content = content[:m.start()] + methods + content[m.start():]

if content != original:
    shutil.copy2(SERVER_PY, SERVER_PY.with_suffix(".py.bak-scan"))
    SERVER_PY.write_text(content, encoding="utf-8")
    print("✅ server.py patché (backup : server.py.bak-scan)")

# ------------------------------------------------------------
# 3) Interface : bouton + panneau de scan
# ------------------------------------------------------------
html = HTML.read_text(encoding="utf-8")
if "scan-open" not in html:
    UI = r'''
<button id="scan-open" style="position:fixed;bottom:16px;left:16px;z-index:9998;border:0;border-radius:999px;padding:12px 18px;background:#7c3aed;color:#fff;font-weight:700;cursor:pointer;box-shadow:0 8px 20px rgba(0,0,0,.25);">📷 Scanner mon CV</button>
<div id="scan-panel" style="display:none;position:fixed;inset:0;background:rgba(15,23,42,.55);z-index:9999;">
  <div style="max-width:660px;margin:4vh auto;background:#fff;border-radius:16px;padding:24px;max-height:92vh;overflow:auto;">
    <div style="display:flex;justify-content:space-between;align-items:center;">
      <h2 style="margin:0;font-size:20px;">📷 Scan &amp; Score de votre CV</h2>
      <button id="scan-close" style="border:0;background:#e2e8f0;border-radius:8px;padding:6px 10px;cursor:pointer;">✖</button>
    </div>
    <p style="color:#64748b;font-size:14px;">Uploadez une photo ou un PDF de votre CV existant. L'application lit le texte et calcule votre score ATS, plus un score de compatibilité si vous collez une offre d'emploi.</p>
    <input type="file" id="scan-file" accept="image/png,image/jpeg,image/webp,application/pdf" style="margin:8px 0;">
    <textarea id="scan-job" rows="4" placeholder="(Optionnel) Collez ici l'offre d'emploi pour calculer la compatibilité..." style="width:100%;margin:8px 0;padding:10px;border:1px solid #cbd5e1;border-radius:8px;"></textarea>
    <button id="scan-go" style="border:0;border-radius:10px;padding:12px 18px;background:#7c3aed;color:#fff;font-weight:700;cursor:pointer;">Analyser mon CV</button>
    <div id="scan-result" style="margin-top:16px;"></div>
  </div>
</div>
<script>
(function () {
  var open = document.getElementById("scan-open");
  var panel = document.getElementById("scan-panel");
  var close = document.getElementById("scan-close");
  var go = document.getElementById("scan-go");
  var fileInput = document.getElementById("scan-file");
  var jobInput = document.getElementById("scan-job");
  var result = document.getElementById("scan-result");

  open.addEventListener("click", function () { panel.style.display = "block"; });
  close.addEventListener("click", function () { panel.style.display = "none"; });

  go.addEventListener("click", function () {
    var file = fileInput.files && fileInput.files[0];
    if (!file) { alert("Choisissez d'abord une photo ou un PDF de votre CV."); return; }

    result.innerHTML = "<p>⏳ Analyse en cours…</p>";
    var fd = new FormData();
    fd.append("file", file, file.name);
    fd.append("kind", (file.name.split(".").pop() || "").toLowerCase());
    fd.append("job", jobInput.value || "");

    fetch("/api/scan-score", { method: "POST", body: fd })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (!res.ok) { result.innerHTML = "<p style='color:#b91c1c;'>❌ " + (res.j.error || "Erreur") + "</p>"; return; }
        var j = res.j;
        var htmlOut = "<h3 style='margin:0 0 8px;'>Score ATS : " + j.ats_score + " / 100</h3>";
        if (j.compatibility !== null && j.compatibility !== undefined) {
          htmlOut += "<h3 style='margin:0 0 8px;color:#7c3aed;'>Compatibilité avec l'offre : " + j.compatibility + " %</h3>";
        }
        htmlOut += "<p style='color:#64748b;'>" + j.word_count + " mots détectés</p><ul style='list-style:none;padding:0;'>";
        (j.checks || []).forEach(function (c) {
          htmlOut += "<li>" + (c.ok ? "✅" : "❌") + " " + c.label + " <b>(+" + c.points + ")</b></li>";
        });
        htmlOut += "</ul>";
        if ((j.matched_skills || []).length) {
          htmlOut += "<p><b>Compétences détectées :</b> " + j.matched_skills.join(", ") + "</p>";
        }
        if ((j.job_keywords_matched || []).length) {
          htmlOut += "<p><b>Mots-clés de l'offre trouvés :</b> " + j.job_keywords_matched.join(", ") + "</p>";
        }
        result.innerHTML = htmlOut;
      })
      .catch(function (e) { result.innerHTML = "<p style='color:#b91c1c;'>❌ " + e + "</p>"; });
  });
})();
</script>
'''
    idx = html.rfind("</body>")
    html = html[:idx] + UI + html[idx:]
    HTML.write_text(html, encoding="utf-8")
    print("✅ Interface de scan ajoutée")

# ------------------------------------------------------------
# 4) requirements.txt
# ------------------------------------------------------------
REQ.write_text("pytesseract\npillow\npypdf\n", encoding="utf-8")
print("✅ requirements.txt créé")
print("\n👉 Redémarrez : python server.py, puis Ctrl + F5")