# fix_pdf_export.py
import re
from pathlib import Path

p = Path(__file__).resolve().parent / "exporters.py"
t = p.read_text(encoding="utf-8")
changes = 0

# --- 1) Ne reshaper QUE les lignes qui contiennent vraiment de l'arabe
def repl1(m):
    global changes
    changes += 1
    ind = m.group(1)
    return (f'if is_arabic and re.search(r"[\\u0600-\\u06FF]", raw):\n'
            f'{ind}raw = get_display(arabic_reshaper.reshape(raw), base_dir="R")')

t = re.sub(
    r'if is_arabic:\s*\n([ \t]+)raw = get_display\(arabic_reshaper\.reshape\(raw\), base_dir="R"\)',
    repl1, t, count=1)

# --- 2) Séparer la ligne contact : arabe (visuel) / latin (lisible machines)
contact_new = '''contact_rtl = " | ".join(filter(None, [data.get("headline"), data.get("location")]))
__I__contact_ltr = " | ".join(filter(None, [data.get("email"), data.get("phone"), data.get("linkedin")]))
__I__if contact_rtl:
__I__    story.append(Paragraph(pdf_text(contact_rtl), body))
__I__if contact_ltr:
__I__    story.append(Paragraph(html.escape(contact_ltr).replace("\\n", " "), body))
__I__if contact_rtl or contact_ltr:
__I__    story.append(Spacer(1, 5))'''

def repl2(m):
    global changes
    changes += 1
    return contact_new.replace("__I__", m.group(1))

t = re.sub(
    r'^([ \t]*)contact = " \| "\.join\(filter\(None, \[.*?\]\)\)\s*\n'
    r'[ \t]*if contact:\s*\n'
    r'[ \t]*story\.extend\(\[Paragraph\(pdf_text\(contact\), body\), Spacer\(1, 5\)\]\)',
    repl2, t, count=1, flags=re.S | re.M)

if changes == 0:
    print("❌ Aucun motif reconnu dans exporters.py")
else:
    p.write_text(t, encoding="utf-8")
    print(f"✅ {changes} modification(s) appliquée(s) à exporters.py")