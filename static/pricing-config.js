// ============================================================
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
