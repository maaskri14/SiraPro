# add_import_button2.py
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

def find_storage_keys(text):
    found = []
    # 1) Clé littérale : localStorage.setItem("ma-cle", ...)
    found += re.findall(
        r'(?:localStorage|sessionStorage)\.(?:setItem|getItem)\(\s*["\']([^"\']+)["\']', text)
    # 2) Clé par variable : localStorage.setItem(CLE, ...) avec const CLE = "..."
    for m in re.finditer(
        r'(?:localStorage|sessionStorage)\.(?:setItem|getItem)\(\s*([A-Za-z_$][\w$]*)', text):
        var = m.group(1)
        dm = re.search(r'(?:const|let|var)\s+' + re.escape(var) + r'\s*=\s*["\']([^"\']+)["\']', text)
        if not dm:
            dm = re.search(re.escape(var) + r'\s*=\s*["\']([^"\']+)["\']', text)
        if dm:
            found.append(dm.group(1))
    # 3) Accès crochets : localStorage["ma-cle"]
    found += re.findall(r'(?:localStorage|sessionStorage)\[\s*["\']([^"\']+)["\']\s*\]', text)
    return found

keys = find_storage_keys(content)

if not keys:
    print("❌ Clé toujours introuvable.")
    print("   Copiez-collez moi ces lignes (ou envoyez static/index.html) :")
    for line in content.splitlines():
        if "Storage" in line or "storage" in line:
            print("   |", line.strip())
    raise SystemExit(1)

key = max(set(keys), key=keys.count)
print(f"✅ Clé de sauvegarde détectée : {key}")

BUTTON_HTML = (
    '<button id="import-json-btn" type="button" '
    'style="margin:4px;padding:10px 14px;border:1px solid #1e745a;border-radius:8px;'
    'background:#ffffff;color:#1e745a;font-weight:700;cursor:pointer;">'
    '📥 Importer JSON</button>'
    '<input type="file" id="import-json-input" accept=".json,application/json" style="display:none">'
)

# Placement du bouton : barre d'export > bouton Exemple ATS > fin de page
m = re.search(r'<[^>]+(?:id|class)="[^"]*export[^"]*"[^>]*>', content, re.I)
if m:
    content = content[:m.end()] + BUTTON_HTML + content[m.end():]
    print("✅ Bouton inséré dans la barre d'export")
else:
    m = re.search(r'<button[^>]*>[^<]*Exemple ATS', content, re.I)
    if m:
        content = content[:m.start()] + BUTTON_HTML + content[m.start():]
        print("✅ Bouton inséré près du bouton Exemple ATS")
    else:
        idx = content.find("</body>")
        content = content[:idx] + BUTTON_HTML + content[idx:]
        print("✅ Bouton inséré en fin de page")

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
print("👉 Faites Ctrl + F5 dans le navigateur.")