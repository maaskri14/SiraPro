# add_import_button.py
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HTML = ROOT / "static" / "index.html"

if not HTML.exists():
    print("❌ static/index.html introuvable.")
    raise SystemExit(1)

content = HTML.read_text(encoding="utf-8")

if "import-json-btn" in content:
    print("ℹ️ Le bouton d'import existe déjà.")
    raise SystemExit(0)

# 1) Détecter la clé localStorage de la sauvegarde automatique
keys = re.findall(r'localStorage\.(?:setItem|getItem)\(\s*["\']([^"\']+)["\']', content)
if not keys:
    print("❌ Clé localStorage introuvable. Envoyez-moi static/index.html.")
    raise SystemExit(1)

key = max(set(keys), key=keys.count)
print(f"✅ Clé localStorage détectée : {key}")

# 2) Le bouton + le champ fichier caché
BUTTON_HTML = (
    '<button id="import-json-btn" type="button" '
    'style="margin:4px;padding:10px 14px;border:1px solid #1e745a;border-radius:8px;'
    'background:#ffffff;color:#1e745a;font-weight:700;cursor:pointer;">'
    '📥 Importer JSON</button>'
    '<input type="file" id="import-json-input" accept=".json,application/json" style="display:none">'
)

# 3) Placer le bouton (barre d'export > bouton Exemple ATS > fin de page)
anchor = None
m = re.search(r'<[^>]+(?:id|class)="[^"]*export[^"]*"[^>]*>', content, re.I)
if m:
    content = content[:m.end()] + BUTTON_HTML + content[m.end():]
    anchor = "barre d'export"
else:
    m = re.search(r'<button[^>]*>[^<]*Exemple ATS', content, re.I)
    if m:
        content = content[:m.start()] + BUTTON_HTML + content[m.start():]
        anchor = "près du bouton Exemple ATS"
    else:
        idx = content.find("</body>")
        content = content[:idx] + BUTTON_HTML + content[idx:]
        anchor = "fin de page"
print(f"✅ Bouton inséré : {anchor}")

# 4) Le script d'import
SCRIPT_HTML = '''
<script>
(function () {
  var KEY = __KEY__;
  var btn = document.getElementById("import-json-btn");
  var input = document.getElementById("import-json-input");
  if (!btn || !input) return;

  btn.addEventListener("click", function () { input.click(); });

  input.addEventListener("change", function () {
    var file = input.files && input.files[0];
    if (!file) return;

    var reader = new FileReader();
    reader.onload = function () {
      try {
        // Retire le BOM UTF-8 ajouté par l'export JSON
        var text = String(reader.result).replace(/^\\uFEFF/, "");
        var data = JSON.parse(text);

        if (typeof data !== "object" || data === null || Array.isArray(data)) throw new Error("format");
        if (!("fullName" in data) && !("experience" in data) && !("email" in data)) throw new Error("format");

        localStorage.setItem(KEY, JSON.stringify(data));
        alert("✅ CV importé avec succès. La page va se recharger.");
        location.reload();
      } catch (e) {
        alert("❌ Fichier JSON invalide. Choisissez un fichier exporté depuis SiraPro.");
      }
    };
    reader.readAsText(file, "utf-8");
    input.value = "";
  });
})();
</script>
'''
SCRIPT_HTML = SCRIPT_HTML.replace("__KEY__", json.dumps(key))

idx = content.rfind("</body>")
content = content[:idx] + SCRIPT_HTML + content[idx:]

HTML.write_text(content, encoding="utf-8")
print("✅ static/index.html mis à jour.")
print("👉 Faites Ctrl + F5 dans le navigateur pour voir le bouton.")