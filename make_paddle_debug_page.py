# make_paddle_debug_page.py
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
STATIC.mkdir(exist_ok=True)

DEBUG_PAGE = STATIC / "paddle-debug.html"

HTML = """<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Diagnostic Paddle - SiraPro</title>
  <script src="https://cdn.paddle.com/paddle/v2/paddle.js"></script>
  <style>
    body {
      font-family: system-ui, Arial, sans-serif;
      background: #f5f7fb;
      margin: 0;
      padding: 30px 20px;
      display: flex;
      justify-content: center;
    }
    .card {
      background: white;
      width: 100%;
      max-width: 900px;
      border-radius: 16px;
      padding: 24px;
      box-shadow: 0 12px 32px rgba(0,0,0,0.12);
    }
    h1 {
      margin-top: 0;
      font-size: 24px;
    }
    button {
      border: 0;
      border-radius: 10px;
      padding: 11px 16px;
      font-weight: 700;
      cursor: pointer;
      color: white;
      background: #2563eb;
      margin-right: 10px;
    }
    button.green {
      background: #16a34a;
    }
    pre {
      background: #0f172a;
      color: #e2e8f0;
      padding: 16px;
      border-radius: 12px;
      min-height: 280px;
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 13px;
      line-height: 1.45;
    }
    .hint {
      color: #64748b;
      font-size: 14px;
      margin-top: 16px;
    }
  </style>
</head>
<body>
  <div class="card">
    <h1>🔍 Diagnostic Paddle</h1>

    <p>
      Cette page sert à afficher l'erreur exacte quand le paiement Paddle ne s'ouvre pas.
    </p>

    <button class="green" onclick="runTest('monthly')">Tester Mensuel 5 USD</button>
    <button onclick="runTest('annual')">Tester Annuel 50 USD</button>

    <p class="hint">
      Cliquez sur un bouton, puis regardez les logs ci-dessous.
      La ligne importante commence par <strong>❌ ERREUR EXACTE</strong>.
    </p>

    <pre id="log">Logs...</pre>
  </div>

  <script>
    function log(message) {
      const el = document.getElementById("log");
      const time = new Date().toLocaleTimeString();
      el.textContent += time + " | " + message + "\\n";
      console.log(message);
    }

    window.addEventListener("error", function(event) {
      log("ERREUR GLOBAL : " + event.message);
    });

    window.addEventListener("unhandledrejection", function(event) {
      const reason = event.reason;
      const message = reason && reason.message ? reason.message : String(reason);
      log("ERREUR PROMISE : " + message);
    });

    async function runTest(plan) {
      document.getElementById("log").textContent = "";

      try {
        log("Début du test : " + plan);
        log("Page : " + location.href);
        log("window.Paddle type : " + typeof window.Paddle);

        if (!window.Paddle) {
          throw new Error("Paddle JS non chargé. CDN bloqué, proxy, antivirus ou bloqueur de pub.");
        }

        if (typeof window.Paddle.Setup !== "function") {
          throw new Error("Paddle.Setup absent. La bibliothèque Paddle JS n'est pas la bonne version.");
        }

        log("Appel de /api/checkout...");

        const response = await fetch("/api/checkout", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            provider: "paddle",
            plan: plan
          })
        });

        log("Réponse HTTP : " + response.status);

        const text = await response.text();
        log("Corps de réponse : " + text.slice(0, 1200));

        let config;

        try {
          config = JSON.parse(text);
        } catch (parseError) {
          throw new Error("Le serveur n'a pas renvoyé du JSON.");
        }

        if (!response.ok || config.error) {
          throw new Error(config.error || "Erreur HTTP " + response.status);
        }

        log("provider : " + config.provider);
        log("environment : " + config.environment);
        log("seller : " + config.seller + " (type: " + typeof config.seller + ")");
        log("client_token : " + String(config.client_token).slice(0, 12) + "...");
        log("price_id : " + config.price_id);

        log("Exécution de Paddle.Setup...");

        Paddle.Setup({
          seller: Number(config.seller),
          token: config.client_token,
          environment: config.environment
        });

        log("Paddle.Setup OK");
        log("Ouverture de Paddle.Checkout...");

        Paddle.Checkout.open({
          items: [
            {
              priceId: config.price_id,
              quantity: 1
            }
          ],
          settings: {
            displayMode: "overlay",
            theme: "light",
            locale: "fr"
          }
        });

        log("Paddle.Checkout.open appelé.");
        log("Si aucune fenêtre ne s'ouvre, regardez les erreurs réseau ou les bloqueurs de popups.");
      } catch (error) {
        const message = error && error.message ? error.message : String(error);
        log("❌ ERREUR EXACTE : " + message);
        console.error(error);
      }
    }
  </script>
</body>
</html>
"""

DEBUG_PAGE.write_text(HTML, encoding="utf-8")

print("✅ Page de diagnostic créée :")
print(DEBUG_PAGE)
print()
print("Ouvrez maintenant dans le navigateur :")
print("http://localhost:8000/paddle-debug.html")