# Mise en production commerciale

## Inclus dans cette version

- mode évaluation avec aperçu, score ATS et filigrane ;
- impression et cinq formats d'export verrouillés ;
- contrôle de licence côté serveur ;
- abonnements mensuel et annuel ;
- clés d'activation signées et limitation à deux appareils ;
- jetons valables sept jours pour la version Windows ;
- liens de paiement Chargily configurables.

## À configurer avant de vendre

1. Déployer le serveur Python derrière HTTPS.
2. Définir `CV_LICENSE_SECRET` avec au moins 32 caractères aléatoires.
3. Remplacer SQLite par PostgreSQL lorsque plusieurs serveurs sont utilisés.
4. Créer les produits mensuel et annuel dans Chargily et Paddle.
5. Définir les URL de paiement avec les variables indiquées dans le README.
6. Relier les webhooks signés à la création, au renouvellement et à
   l'expiration des licences.
7. Ajouter une authentification par e-mail avant une ouverture publique.
8. Publier les conditions d'utilisation, la confidentialité, les remboursements
   et les coordonnées de l'entreprise.

## États recommandés

- `active` : export autorisé ;
- `past_due` : délai de grâce court ;
- `canceled` : accès jusqu'à la fin de la période payée ;
- `expired` : aperçu uniquement.

Ne placez jamais une clé secrète Chargily, Paddle ou de licence dans les fichiers
JavaScript ou dans l'application Windows.
