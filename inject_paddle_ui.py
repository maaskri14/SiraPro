# inject_paddle_ui.py
import shutil
from pathlib import Path

html_file = Path("static/index.html")

if not html_file.exists():
    print("❌ Le fichier static/index.html est introuvable.")
    print("   Assurez-vous d'exécuter ce script depuis le dossier racine du projet.")
    exit(1)

# 1. Création d'une sauvegarde de sécurité
backup_file = html_file.with_name("index.html.bak")
if not backup_file.exists():
    shutil.copy(html_file, backup_file)
    print(f"✅ Sauvegarde créée : {backup_file.name}")

content = html_file.read_text(encoding="utf-8")

# 2. Le code Paddle à injecter
paddle_code = """
<!-- ========================================== -->
<!-- INTÉGRATION PADDLE (Ajouté automatiquement)-->
<!-- ========================================== -->
<script src="https://cdn.paddle.com/paddle/v2/paddle.js"></script>
<script>
async function ouvrirPaiementPaddle(plan) {
    try {
        // Demande la configuration à votre serveur Python
        const response = await fetch("/api/checkout", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ provider: "paddle", plan: plan })
        });
        
        const config = await response.json();
        
        if (config.error) {
            alert("Erreur serveur : " + config.error);
            return;
        }

        if (!window.Paddle) {
            alert("Le script Paddle n'a pas pu être chargé.");
            return;
        }

        // Initialisation de Paddle avec vos identifiants Sandbox
        Paddle.Setup({
            seller: config.seller,
            token: config.client_token,
            environment: config.environment
        });

        // Ouverture de la fenêtre de paiement (Checkout)
        Paddle.Checkout.open({
            items: [{ priceId: config.price_id, quantity: 1 }],
            settings: { displayMode: "overlay", theme: "light", locale: "fr" }
        });
    } catch (e) {
        console.error(e);
        alert("Impossible d'ouvrir le paiement.");
    }
}
</script>

<!-- Zone de test flottante (à supprimer plus tard quand vous l'intégrerez à vos vrais boutons) -->
<div id="paddle-test-zone" style="position: fixed; bottom: 20px; right: 20px; background: #fff3cd; border: 2px solid #ffc107; padding: 15px; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); z-index: 99999; font-family: system-ui, sans-serif; text-align: center; min-width: 200px;">
    <strong style="color:#856404;">🚀 Test Paddle Sandbox</strong><br><br>
    <button onclick="ouvrirPaiementPaddle('monthly')" style="background: #28a745; color: white; border: none; padding: 10px 15px; border-radius: 5px; cursor: pointer; font-weight: bold; width: 100%; margin-bottom: 8px; font-size: 14px;">
        Tester Mensuel (5$)
    </button>
    <button onclick="ouvrirPaiementPaddle('annual')" style="background: #007bff; color: white; border: none; padding: 10px 15px; border-radius: 5px; cursor: pointer; font-weight: bold; width: 100%; font-size: 14px;">
        Tester Annuel (50$)
    </button>
</div>
<!-- ========================================== -->
"""

# 3. Injection dans le fichier HTML
if "ouvrirPaiementPaddle" in content:
    print("ℹ️ Le code Paddle est déjà présent dans index.html.")
else:
    if "</body>" in content:
        new_content = content.replace("</body>", paddle_code + "\n</body>")
    elif "</html>" in content:
        new_content = content.replace("</html>", paddle_code + "\n</html>")
    else:
        new_content = content + "\n" + paddle_code
        
    html_file.write_text(new_content, encoding="utf-8")
    print("✅ Code Paddle injecté avec succès dans static/index.html !")

print("\n👉 Prochaine étape :")
print("1. Allez sur http://localhost:8000 dans votre navigateur.")
print("2. Regardez en bas à droite de l'écran, vous verrez un encadré jaune de test.")
print("3. Cliquez sur les boutons pour ouvrir la fenêtre de paiement Paddle !")