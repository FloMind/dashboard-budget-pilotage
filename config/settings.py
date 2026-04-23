"""
config/settings.py
══════════════════════════════════════════════════════════════════════════════
FloMind Budget Dashboard — Constantes métier centralisées

Principe : toutes les "magic values" dispersées dans le code sont ici.
Modifier un seuil, un label ou un paramètre → un seul endroit à changer.

Sections :
  PATHS       → chemins fichiers
  DASHBOARD   → paramètres d'affichage
  ALERTES     → seuils de matérialité
  ATTERRISSAGE→ paramètres de projection
  FORECAST    → paramètres rolling forecast
  SIG         → labels et ordre des soldes intermédiaires
  SITES       → métadonnées réseau
══════════════════════════════════════════════════════════════════════════════
"""

from pathlib import Path

# ── CHEMINS ───────────────────────────────────────────────────────────────────

# Racine du projet (deux niveaux au-dessus de config/)
ROOT = Path(__file__).parent.parent

# Fichier de données principal
DATA_FILE = ROOT / "data" / "sample_budget_v2.xlsx"

# Noms des onglets Excel
SHEET_DATA    = "data"
SHEET_SITES   = "ref_sites"
SHEET_COMPTES = "ref_comptes"

# Dossier de sortie pour les exports PDF
EXPORT_DIR = ROOT / "exports"


# ── DASHBOARD ─────────────────────────────────────────────────────────────────

# Titre de la page Streamlit
PAGE_TITLE = "FloMind — Budget Dashboard"
PAGE_ICON  = "📊"

# Nombre de mois affichés par défaut dans la heatmap (YTD seulement)
HEATMAP_MOIS_MAX = 12

# Top N écarts affichés par défaut sur l'écran 3
TOP_ECARTS_DEFAULT = 10

# Hauteurs des graphiques (px) — ajustable selon la résolution client
CHART_HEIGHT_KPI    = 340    # Courbes mensuelles
CHART_HEIGHT_WF     = 380    # Waterfall
CHART_HEIGHT_HM     = 260    # Heatmap
CHART_HEIGHT_FC     = 400    # Forecast
CHART_HEIGHT_BARS   = 360    # Barres horizontales écarts


# ── ALERTES — SEUILS DE MATÉRIALITÉ ──────────────────────────────────────────
#
# Une alerte est déclenchée si ET SEULEMENT SI les deux conditions sont remplies :
#   1. |écart_%| ≥ ALERTE_SEUIL_PCT
#   2. |écart_€| ≥ ALERTE_SEUIL_ABS
#
# Ce double critère filtre les micro-écarts insignifiants
# (ex. 20% sur un compte à 100€ de budget — non matériel)

ALERTE_SEUIL_PCT  : float = 5.0     # % — seuil d'écart relatif par défaut
ALERTE_SEUIL_ABS  : float = 2_000.0 # € — seuil d'écart absolu par défaut

# Classes analytiques exclues des alertes automatiques
# (hors contrôle opérationnel immédiat — figées comptablement)
ALERTE_CLASSES_EXCLUES = [
    "Dotations",           # Amortissements calculés sur plan d'amortissement
    "IS et participation", # IS calculé en fin d'exercice sur résultat fiscal
]

# Seuil de priorité (multiple du seuil absolu)
ALERTE_PRIORITE_1 = 4.0   # Critique  : impact > 4 × seuil_abs (>  8 000€)
ALERTE_PRIORITE_2 = 2.0   # Important : impact > 2 × seuil_abs (>  4 000€)
# Priorité 3 : surveillance (juste au-dessus du seuil)


# ── ATTERRISSAGE — PARAMÈTRES DE PROJECTION ───────────────────────────────────
#
# Méthode hybride : réel YTD + budget restant × facteur
# facteur = (1 - POIDS_TENDANCE) × 1.0 + POIDS_TENDANCE × ratio_YTD
#
# ratio_YTD = réel_YTD / budget_YTD
# Si ratio = 1.05 → on projette +5% sur les mois restants
# Si ratio = 0.90 → on projette -10% sur les mois restants

POIDS_ATTERRISSAGE_TENDANCE: float = 0.70
# 0.70 = 70% tendance + 30% budget pur
# Réduire vers 0.5 pour un réseau plus volatile (atténue l'extrapolation)
# Augmenter vers 0.9 pour un réseau très régulier (amplifie la tendance)


# ── FORECAST — PARAMÈTRES ROLLING ────────────────────────────────────────────

# Méthode par défaut à l'ouverture de l'écran 4
FORECAST_METHODE_DEFAUT = "hybride"

# Nombre de simulations bootstrap pour les bandes P10/P90
# 1 000 = bon équilibre précision / vitesse de calcul
# 5 000 = meilleure précision (export PDF haute qualité)
# 200   = prévisualisation rapide
FORECAST_N_SIMULATIONS = 1_000
FORECAST_SEED          = 42   # Graine fixée pour reproductibilité

# Facteur de décroissance des poids WLS
# 0.75 = mois récent poids 1.0, mois -1 poids 0.75, mois -2 poids 0.56…
# Plus bas → sur-pondère le dernier mois (instable)
# Plus haut → poids quasi-uniformes (moins réactif aux inflexions)
FORECAST_WLS_DECAY: float = 0.75

# Pondérations méthode hybride selon la cadence
# Format : {mois_reel_max: (w_tendance, w_wls)}
FORECAST_HYBRIDE_POIDS = {
    3 : (0.75, 0.25),  # Début d'exercice : peu de données → tendance majoritaire
    6 : (0.55, 0.45),  # Milieu d'exercice : équilibre
    12: (0.45, 0.55),  # Fin d'exercice : WLS plus fiable → dominant
}

# KPIs disponibles dans le sélecteur de l'écran 4
FORECAST_KPI_OPTIONS = {
    "CA_net": "CA net (chiffre d'affaires)",
    "MC"    : "Marge commerciale",
    "VA"    : "Valeur ajoutée",
    "EBE"   : "EBE (excédent brut d'exploitation)",
    "REX"   : "REX (résultat d'exploitation)",
    "RCAI"  : "RCAI (résultat courant avant IS)",
}


# ── SIG — SOLDES INTERMÉDIAIRES DE GESTION ────────────────────────────────────

# Ordre d'affichage des classes dans le P&L vertical (de haut en bas)
CLASSE_ORDER = [
    "Produits",
    "Achats",
    "Services ext. 61",
    "Services ext. 62",
    "Autres produits",
    "Impôts et taxes",
    "Charges personnel",
    "Autres charges",
    "Dotations",
    "Reprises",
    "Produits financiers",
    "Charges financières",
    "Produits exceptionnels",
    "Charges exceptionnelles",
    "IS et participation",
]

# Labels courts pour les graphiques (axes, légendes)
SIG_LABELS = {
    "CA_net": "CA net",
    "MC"    : "Marge comm.",
    "VA"    : "Valeur ajoutée",
    "EBE"   : "EBE",
    "REX"   : "REX",
    "RCAI"  : "RCAI",
    "RN"    : "Résultat net",
}

# Labels longs pour les tooltips et tableaux
SIG_LABELS_LONG = {
    "CA_net": "Chiffre d'affaires net",
    "MC"    : "Marge commerciale",
    "VA"    : "Valeur ajoutée",
    "EBE"   : "Excédent Brut d'Exploitation",
    "REX"   : "Résultat d'Exploitation",
    "RCAI"  : "Résultat Courant Avant Impôts",
    "RN"    : "Résultat Net",
}

# Mois — labels courts
MOIS_LABELS = {
    1:"Jan", 2:"Fév", 3:"Mar", 4:"Avr", 5:"Mai", 6:"Jun",
    7:"Jul", 8:"Aoû", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Déc",
}


# ── RÉSEAU — MÉTADONNÉES ──────────────────────────────────────────────────────

# Nom du réseau (affiché dans le titre et les exports)
RESEAU_NOM = "FloMind Réseau"

# Exercice fiscal courant
ANNEE_COURANTE = 2025

# Devise (symbole utilisé dans les formatters)
DEVISE = "€"

# Unité d'affichage par défaut
UNITE_AFFICHAGE = "K€"    # "€" | "K€" | "M€"
