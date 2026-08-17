# apply_pricing_page.py
from __future__ import annotations
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
STATIC.mkdir(exist_ok=True)
SERVER_PY = ROOT / "server.py"
ENV_EXAMPLE = ROOT / ".env.example"

PRICING_HTML = r'''<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SiraPro — Tarifs</title>
<script src="https://cdn.paddle.com/paddle/v2/paddle.js"></script>
<style>
  body{margin:0;font-family:system-ui,Arial,sans-serif;background:#f5f7fb;color:#0f172a}
  header{padding:16px 24px;background:#fff;border-bottom:1px solid #e2e8f0}
  header a{color:#2563eb;text-decoration:none;font-weight:600}
  main{max-width:1080px;margin:0 auto;padding:40px 20px;text-align:center}
  h1{font-size:32px;margin:0 0 8px}
  .sub{color:#64748b;margin:0 0 24px}
  .banner{margin:0 auto 20px;max-width:720px;padding:12px 16px;border-radius:10px;text-align:left;font-size:14px}
  .banner.warn{background:#fff3cd;border:1px solid #ffc107;color:#856404}
  .banner.error{background:#f8d7da;border:1px solid #f5c2c7;color:#842029}
  .toggle{display:inline-flex;background:#e2e8f0;border-radius:999px;padding:4px;margin-bottom:32px}
  .toggle button{border:0;background:transparent;padding:10px 22px;border-radius:999px;font-weight:700;cursor:pointer;color:#475569}
  .toggle button.on{background:#fff;color:#0f172a;box-shadow:0 1px 4px rgba(0,0,0,.15)}
  .tiers{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:20px;text-align:left}
  .tier{background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:24px;display:flex;flex-direction:column}
  .tier.featured{border:2px solid #2563eb}
  .tier h2{margin:0 0 4px;font-size:20px}
  .desc{color:#64748b;font-size:14px;margin:0 0 16px;min-height:40px}
  .price{font-size:32px;font-weight:800}
  .per{color:#64748b;font-size:13px;margin-bottom:16px}
  ul{list-style:none;padding:0;margin:0 0 24px;flex:1}
  li{padding:6px 0;font-size:14px;border-bottom:1px dashed #e2e8f0}
  li:before{content:"✓ ";color:#16a34a;font-weight:700}
  .subscribe{border:0;border-radius:10px;padding:12px;font-weight:700;cursor:pointer;background:#2563eb;color:#fff}
  .subscribe:disabled{background:#94a3b8;cursor:not-allowed}
</style>
</head>
<body>
<header><a href="/">← Retour à l'application</a></header>
<main>
  <h1>Choisissez votre formule</h1>
  <p class="sub">Prix localisés selon votre pays, fournis par Paddle.</p>
  <div id="config-banner" class="banner warn" hidden></div>
  <div class="toggle" role="group" aria-label="Périodicité">
    <button id="bill-month" class="on">Mensuel</button>
    <button id="bill-year">Annuel</button>
  </div>
  <div id="tiers" class="tiers"></div>
</main>
<script src="pricing-config.js"></script>
<script src="pricing.js"></script>
</body>
</html>
'''

PRICING_CONFIG_JS = r'''// ============================================================
// CONFIGURATION DES TIERS — modifiez librement
// priceId.month / priceId.year : IDs Paddle (pri_...)
// ============================================================
window.SIRAPRO_TIERS = [
  {
    name: "Starter",
    description: "Pour créer un premier CV professionnel.",
    features: [
      "Aperçu illimité",
      "Score ATS",
      "Export PDF",
      "1 modèle"
    ],
    priceId: { month: "pri_REMPLACEZ_STARTER_MONTH", year: "pri_REMPLACEZ_STARTER_YEAR" }
  },
  {
    name: "Pro",
    description: "Le plus populaire : tous les exports.",
    features: [
      "Tout Starter",
      "Exports PDF, Word, HTML, TXT, JSON",
      "3 langues (AR/EN/FR)",
      "2 appareils"
    ],
    priceId: { month: "pri_01kzknvgbrggy0fyh52x60x516", year: "pri_01kzknx5nrsjte790mp4fefkjm" }
  },
  {
    name: "Advanced",
    description: "Pour les chercheurs d'emploi intensifs.",
    features: [
      "Tout Pro",
      "Lettre de motivation IA",
      "Suivi de candidatures",
      "Support prioritaire"
    ],
    priceId: { month: "pri_REMPLACEZ_ADVANCED_MONTH", year: "pri_REMPLACEZ_ADVANCED_YEAR" }
  }
];
'''

PRICING_JS = r'''/* global Paddle, SIRAPRO_TIERS */
(function () {
  "use strict";

  var state = { billing: "month", totals: {}, country: null, email: null };

  function el(id) { return document.getElementById(id); }
  function isPlaceholder(id) { return !id || id.indexOf("REPLACEZ") !== -1; }

  function showBanner(msg, kind) {
    var b = el("config-banner");
    b.hidden = false;
    b.textContent = msg;
    b.className = "banner " + (kind || "warn");
  }

  function renderTiers() {
    var wrap = el("tiers");
    wrap.innerHTML = "";
    SIRAPRO_TIERS.forEach(function (tier) {
      var pid = tier.priceId[state.billing];
      var tot = state.totals[pid];
      var card = document.createElement("article");
      card.className = "tier" + (tier.name === "Pro" ? " featured" : "");

      var priceHtml;
      if (isPlaceholder(pid)) {
        priceHtml = '<div class="price">—</div><div class="per">price ID Paddle à configurer</div>';
      } else if (tot && tot.total) {
        // Affichage EXCLUSIF du formattedTotals renvoyé par Paddle.
        priceHtml = '<div class="price">' + tot.total + '</div><div class="per">' +
          (state.billing === "month" ? "/mois" : "/an") + '</div>';
      } else {
        priceHtml = '<div class="price">…</div><div class="per">chargement</div>';
      }

      card.innerHTML =
        "<h2>" + tier.name + "</h2>" +
        '<p class="desc">' + tier.description + "</p>" +
        priceHtml +
        "<ul>" + tier.features.map(function (f) { return "<li>" + f + "</li>"; }).join("") + "</ul>" +
        '<button class="subscribe" data-tier="' + tier.name + '"' +
        (isPlaceholder(pid) ? " disabled" : "") + ">S'abonner</button>";

      wrap.appendChild(card);
    });

    Array.prototype.forEach.call(wrap.querySelectorAll(".subscribe"), function (btn) {
      btn.addEventListener("click", function () { subscribe(btn.getAttribute("data-tier")); });
    });
  }

  function subscribe(name) {
    var tier = null;
    SIRAPRO_TIERS.forEach(function (t) { if (t.name === name) tier = t; });
    if (!tier) return;
    var pid = tier.priceId[state.billing];
    if (isPlaceholder(pid)) return;

    var args = {
      items: [{ priceId: pid, quantity: 1 }],
      settings: { displayMode: "overlay", variant: "one-page", theme: "light", locale: "fr" },
      onCheckoutCompleted: function () { window.location.href = "/welcome"; }
    };
    if (state.email) args.customer = { email: state.email };

    Paddle.Checkout.open(args);
  }

  function loadPrices() {
    var items = [];
    SIRAPRO_TIERS.forEach(function (t) {
      ["month", "year"].forEach(function (k) {
        if (!isPlaceholder(t.priceId[k])) items.push({ priceId: t.priceId[k], quantity: 1 });
      });
    });
    if (!items.length) { renderTiers(); return; }

    var args = { items: items };
    // Ne passer UN JAMAIS un sentinel interne à Paddle : seulement un vrai code ISO.
    if (state.country) args.address = { countryCode: state.country };

    Paddle.PricePreview(args).then(function (res) {
      var lines = (res && res.data && res.data.details && res.data.details.lineItems) || [];
      lines.forEach(function (li) {
        var pid = (li.item && li.item.priceId) || (li.price && li.price.id);
        if (pid && li.formattedTotals) state.totals[pid] = li.formattedTotals;
      });
      renderTiers();
    }).catch(function (err) {
      showBanner("Erreur PricePreview : " + (err && err.message ? err.message : err), "error");
      renderTiers();
    });
  }

  function setBilling(b) {
    state.billing = b;
    el("bill-month").className = b === "month" ? "on" : "";
    el("bill-year").className = b === "year" ? "on" : "";
    renderTiers();
  }

  function init() {
    try { state.email = localStorage.getItem("sirapro_email"); } catch (e) { state.email = null; }

    var hasPlaceholder = SIRAPRO_TIERS.some(function (t) {
      return isPlaceholder(t.priceId.month) || isPlaceholder(t.priceId.year);
    });
    if (hasPlaceholder) {
      showBanner("Complétez static/pricing-config.js avec vos price IDs Paddle (Starter et Advanced).");
    }

    if (typeof Paddle === "undefined") {
      showBanner("Paddle JS n'a pas pu être chargé (CDN bloqué ?).", "error");
      renderTiers();
      return;
    }

    fetch("/api/paddle/config").then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok) throw new Error(j.error || ("HTTP " + r.status));
        return j;
      });
    }).then(function (cfg) {
      Paddle.Setup({ token: cfg.client_token });
      return fetch("/api/country").then(function (r) { return r.json(); }).catch(function () { return { country: null }; });
    }).then(function (geo) {
      state.country = (geo && geo.country) || null;
      loadPrices();
    }).catch(function (err) {
      showBanner("Configuration Paddle impossible : " + err.message, "error");
      renderTiers();
    });

    el("bill-month").addEventListener("click", function () { setBilling("month"); });
    el("bill-year").addEventListener("click", function () { setBilling("year"); });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
'''

WELCOME_HTML = r'''<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bienvenue — SiraPro</title>
<style>
  body{margin:0;font-family:system-ui,Arial,sans-serif;background:#f5f7fb;display:flex;min-height:100vh;align-items:center;justify-content:center}
  .card{background:#fff;border-radius:16px;padding:40px;max-width:520px;text-align:center;box-shadow:0 12px 32px rgba(0,0,0,.12)}
  a{color:#2563eb;font-weight:700}
</style>
</head>
<body>
<div class="card">
  <h1>🎉 Merci pour votre abonnement !</h1>
  <p>Votre paiement Paddle a été confirmé.</p>
  <p>Votre licence SiraPro est en cours d'activation (webhook). Vous pouvez aussi saisir votre clé de licence depuis l'application.</p>
  <p><a href="/">Retour à l'application →</a></p>
</div>
</body>
</html>
'''

ENV_EXAMPLE_CONTENT = r'''# ============================================================
# Paddle — OBLIGATOIRE, jamais de valeur par défaut côté serveur
# ============================================================
# 'sandbox' ou 'production'. Si absent ou incohérent, /api/paddle/config renvoie 500.
CV_PADDLE_ENVIRONMENT=sandbox
# Token client-side (public par design) : test_... en sandbox, live_... en production.
CV_PADDLE_CLIENT_TOKEN=test_45ddaa8cdb6d1f48b59a91cda9e
# Seller ID (référence)
CV_PADDLE_SELLER_ID=99648
# Secret webhook (serveur UNIQUEMENT, jamais côté client)
CV_PADDLE_WEBHOOK_SECRET=

# ============================================================
# Licences
# ============================================================
CV_LICENSE_SECRET=change-this-secret-before-production
#CV_LICENSE_DB=
#CV_MAX_DEVICES=2

# ============================================================
# Chargily (marché algérien, optionnel)
# ============================================================
CV_CHARGILY_MONTHLY_URL=
CV_CHARGILY_ANNUAL_URL=
'''

ROUTES_TEMPLATE = '''# PRICING-PAGE:routes
if self.path == "/pricing":
    self._send_static_file("pricing.html")
    return

if self.path == "/welcome":
    self._send_static_file("welcome.html")
    return

if self.path == "/api/country":
    self._send_json({"country": self._detect_country()})
    return

if self.path == "/api/paddle/config":
    try:
        self._send_json(self._paddle_public_config())
    except ValueError as exc:
        self._send_json({"error": str(exc)}, 500)
    return
'''

METHODS_TEMPLATE = '''# PRICING-PAGE:methods
def _detect_country(self):
    for header in ("x-vercel-ip-country", "cf-ipcountry", "x-country-code", "x-client-geo-country"):
        value = (self.headers.get(header) or "").strip().upper()
        if re.fullmatch(r"[A-Z]{2}", value):
            return value
    return None

def _paddle_public_config(self) -> dict:
    environment = os.getenv("CV_PADDLE_ENVIRONMENT", "").strip()
    token = os.getenv("CV_PADDLE_CLIENT_TOKEN", "").strip()

    if not environment:
        raise ValueError("CV_PADDLE_ENVIRONMENT n'est pas défini (sandbox ou production).")
    if environment not in {"sandbox", "production"}:
        raise ValueError("CV_PADDLE_ENVIRONMENT doit valoir 'sandbox' ou 'production'.")
    if not token:
        raise ValueError("CV_PADDLE_CLIENT_TOKEN n'est pas défini.")
    if environment == "sandbox" and not token.startswith("test_"):
        raise ValueError("CV_PADDLE_ENVIRONMENT=sandbox mais le token ne commence pas par test_.")
    if environment == "production" and not token.startswith("live_"):
        raise ValueError("CV_PADDLE_ENVIRONMENT=production mais le token ne commence pas par live_.")

    return {"environment": environment, "client_token": token}

def _send_static_file(self, name: str) -> None:
    path = STATIC / name
    if not path.exists():
        self.send_error(404)
        return
    payload = path.read_bytes()
    self.send_response(200)
    self.send_header("Content-Type", "text/html; charset=utf-8")
    self.send_header("Content-Length", str(len(payload)))
    self.end_headers()
    self.wfile.write(payload)
'''


def indent_block(block: str, indent: str) -> str:
    return "\n".join((indent + line) if line.strip() else "" for line in block.splitlines())


def write(path: Path, content: str) -> None:
    path.write_text(content.lstrip("\n"), encoding="utf-8")
    print(f"✅ {path.name}")


def patch_server() -> None:
    content = SERVER_PY.read_text(encoding="utf-8")
    original = content

    if "PRICING-PAGE:routes" not in content:
        m = re.search(r"^([ \t]*)super\(\)\.do_GET\(\)", content, re.M)
        if not m:
            raise SystemExit("❌ super().do_GET() introuvable dans server.py")
        content = content[:m.start()] + indent_block(ROUTES_TEMPLATE, m.group(1)) + "\n\n" + content[m.start():]

    if "PRICING-PAGE:methods" not in content:
        m = re.search(r"^([ \t]*)def _read_json", content, re.M)
        if not m:
            raise SystemExit("❌ def _read_json introuvable dans server.py")
        content = content[:m.start()] + indent_block(METHODS_TEMPLATE, m.group(1)) + "\n\n" + content[m.start():]

    if content != original:
        shutil.copy2(SERVER_PY, SERVER_PY.with_suffix(".py.bak-pricing"))
        SERVER_PY.write_text(content, encoding="utf-8")
        print("✅ server.py patché (backup : server.py.bak-pricing)")
    else:
        print("ℹ️ server.py déjà patché")


def main() -> None:
    write(STATIC / "pricing.html", PRICING_HTML)
    write(STATIC / "pricing-config.js", PRICING_CONFIG_JS)
    write(STATIC / "pricing.js", PRICING_JS)
    write(STATIC / "welcome.html", WELCOME_HTML)
    write(ENV_EXAMPLE, ENV_EXAMPLE_CONTENT)
    patch_server()
    print("\n👉 Redémarrez : python server.py, puis ouvrez http://localhost:8000/pricing")


if __name__ == "__main__":
    main()