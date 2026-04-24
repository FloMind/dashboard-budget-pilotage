"""
hypotheses_store.py
══════════════════════════════════════════════════════════════════════════════
FloMind Budget Dashboard — Bibliothèque d'hypothèses Reforecast CDG

RÔLE
─────
Ce module fournit :
  1. HYPOTHESES_LIBRARY  : catalogue de 47 hypothèses typées par catégorie
  2. Persistance JSON    : lecture / écriture de data/hypotheses.json
  3. Calcul d'impact     : traduit chaque hypothèse en deltas mensuels SIG
                           avec cascade CA → MC → VA → EBE correcte

CASCADE SIG
────────────
  Hypothèse type CA     : ΔCA × taux_marge     → ΔMC → ΔVA → ΔEBE
  Hypothèse type Marge  : ΔCA × Δtaux_marge    → ΔMC → ΔVA → ΔEBE
  Hypothèse type Serv.  : Δcharges_services    → ΔVA → ΔEBE (pas CA, pas MC)
  Hypothèse type Pers.  : Δcharges_personnel   → ΔEBE seulement
  Hypothèse type Direct : impact direct EBE ou REX (provisions, taxes…)

TYPES D'IMPACT
───────────────
  "ca_pct"       → % variation CA sur mois sélectionnés
  "ca_abs"       → montant CA absolu perdu/gagné par mois (K€)
  "marge_pts"    → variation taux marge brute en points
  "serv_abs"     → variation charges services (VA→EBE) en K€/mois
  "serv_pct"     → variation charges services en % du budget
  "pers_abs"     → variation charges personnel (EBE) en K€/mois
  "pers_pct"     → variation charges personnel en %
  "ebe_abs"      → impact direct EBE en K€ (exceptionnel, provision…)

PERSISTANCE
────────────
  data/hypotheses.json (gitignored)
  Structure :
  {
    "meta": {"annee": 2025, "last_updated": "..."},
    "hypotheses": [
      {
        "uuid": "abc123",
        "type_id": "C01",
        "site_code": "LYO_E",
        "label": "Perte client Dupont",
        "params": {"montant_ke": 8.0, "mois_debut": 4, "mois_fin": 12},
        "note": "Client parti chez concurrent",
        "created_at": "2025-04-23T14:30:00"
      }
    ]
  }

AUTEUR : FloMind Consulting — 2025
══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_PATH = Path("data/hypotheses.json")

# Taux de marge brute par défaut pour le négoce B2B (utilisé si data indisponible)
TAUX_MARGE_DEFAULT = 0.38

# KPIs disponibles pour le reforecast
KPIS_RFC = ["CA_net", "MC", "VA", "EBE"]
KPI_LABELS = {
    "CA_net": "CA net (K€)",
    "MC"    : "Marge commerciale (K€)",
    "VA"    : "Valeur ajoutée (K€)",
    "EBE"   : "EBE ≈ EBITDA (K€)",
}

# Labels courts des mois
MOIS_LABELS = [
    "Jan","Fév","Mar","Avr","Mai","Jun",
    "Jul","Aoû","Sep","Oct","Nov","Déc"
]


# ══════════════════════════════════════════════════════════════════════════════
# BIBLIOTHÈQUE DES HYPOTHÈSES
# ══════════════════════════════════════════════════════════════════════════════

# Structure de chaque hypothèse :
#   categorie     : groupe d'affichage
#   label         : nom court affiché dans le sélecteur
#   description   : explication pour le CDG
#   impact_type   : méthode de calcul (voir module docstring)
#   kpis_impactes : KPIs recalculés en cascade (dans l'ordre)
#   params        : liste de paramètres à saisir dans l'interface
#     Chaque param : {key, label, type (float/int/pct/mois), default, min, max, unit, help}

HYPOTHESES_LIBRARY: Dict[str, dict] = {

    # ── CA & COMMERCIAL ──────────────────────────────────────────────────────
    "C01": {
        "categorie"    : "🔵 CA & Commercial",
        "label"        : "Perte client majeur",
        "description"  : "Un client récurrent disparaît à partir d'un mois donné. "
                         "Le CA mensuel perdu est appliqué en déduction sur tous les mois sélectionnés.",
        "impact_type"  : "ca_abs",
        "kpis_impactes": ["CA_net", "MC", "VA", "EBE"],
        "sens"         : -1,
        "params": [
            {"key": "montant_ke",  "label": "CA mensuel perdu",      "type": "float", "min": 0,  "max": 500, "unit": "K€",  "default": 10.0},
            {"key": "mois_debut",  "label": "Mois de départ",        "type": "mois",  "min": 1,  "max": 12,  "unit": "",    "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",           "type": "mois",  "min": 1,  "max": 12,  "unit": "",    "default": 12},
        ],
    },
    "C02": {
        "categorie"    : "🔵 CA & Commercial",
        "label"        : "Nouveau contrat signé",
        "description"  : "Signature d'un nouveau client ou contrat. CA mensuel additionnel à partir du mois de début.",
        "impact_type"  : "ca_abs",
        "kpis_impactes": ["CA_net", "MC", "VA", "EBE"],
        "sens"         : +1,
        "params": [
            {"key": "montant_ke",  "label": "CA mensuel additionnel", "type": "float", "min": 0,  "max": 500, "unit": "K€", "default": 8.0},
            {"key": "mois_debut",  "label": "Mois de démarrage",      "type": "mois",  "min": 1,  "max": 12,  "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",            "type": "mois",  "min": 1,  "max": 12,  "unit": "",   "default": 12},
        ],
    },
    "C03": {
        "categorie"    : "🔵 CA & Commercial",
        "label"        : "Appel d'offres remporté",
        "description"  : "Contrat exceptionnel remporté. Montant total réparti uniformément sur la période.",
        "impact_type"  : "ca_abs",
        "kpis_impactes": ["CA_net", "MC", "VA", "EBE"],
        "sens"         : +1,
        "params": [
            {"key": "montant_ke",  "label": "CA mensuel attendu",    "type": "float", "min": 0, "max": 1000, "unit": "K€", "default": 15.0},
            {"key": "mois_debut",  "label": "Mois de début livraison","type": "mois", "min": 1, "max": 12,   "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",           "type": "mois",  "min": 1, "max": 12,   "unit": "",   "default": 12},
        ],
    },
    "C04": {
        "categorie"    : "🔵 CA & Commercial",
        "label"        : "Appel d'offres perdu",
        "description"  : "Perte d'un appel d'offres budgeté. CA mensuel perdu sur la période prévue.",
        "impact_type"  : "ca_abs",
        "kpis_impactes": ["CA_net", "MC", "VA", "EBE"],
        "sens"         : -1,
        "params": [
            {"key": "montant_ke",  "label": "CA mensuel perdu",  "type": "float", "min": 0, "max": 500, "unit": "K€", "default": 10.0},
            {"key": "mois_debut",  "label": "Mois de départ",    "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",       "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": 12},
        ],
    },
    "C05": {
        "categorie"    : "🔵 CA & Commercial",
        "label"        : "Hausse tarifaire appliquée",
        "description"  : "Révision tarifaire à la hausse. Impacte le CA et le taux de marge simultanément "
                         "si les achats ne bougent pas.",
        "impact_type"  : "ca_pct",
        "kpis_impactes": ["CA_net", "MC", "VA", "EBE"],
        "sens"         : +1,
        "params": [
            {"key": "pct_hausse",  "label": "Hausse tarifaire",  "type": "pct",  "min": 0, "max": 30,  "unit": "%",  "default": 3.0},
            {"key": "mois_debut",  "label": "Mois d'application","type": "mois", "min": 1, "max": 12,  "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",       "type": "mois", "min": 1, "max": 12,  "unit": "",   "default": 12},
        ],
    },
    "C06": {
        "categorie"    : "🔵 CA & Commercial",
        "label"        : "Baisse tarifaire accordée",
        "description"  : "Concession commerciale ou rabais accordé. Réduit le CA sans changer les achats → marge dégradée.",
        "impact_type"  : "ca_pct",
        "kpis_impactes": ["CA_net", "MC", "VA", "EBE"],
        "sens"         : -1,
        "params": [
            {"key": "pct_baisse",  "label": "Baisse tarifaire",  "type": "pct",  "min": 0, "max": 30, "unit": "%", "default": 3.0},
            {"key": "mois_debut",  "label": "Mois d'application","type": "mois", "min": 1, "max": 12, "unit": "",  "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",       "type": "mois", "min": 1, "max": 12, "unit": "",  "default": 12},
        ],
    },
    "C07": {
        "categorie"    : "🔵 CA & Commercial",
        "label"        : "Action promotionnelle",
        "description"  : "Remises exceptionnelles accordées lors d'une opération commerciale. "
                         "Impacte le CA net (via 709x).",
        "impact_type"  : "ca_abs",
        "kpis_impactes": ["CA_net", "MC", "VA", "EBE"],
        "sens"         : -1,
        "params": [
            {"key": "montant_ke",  "label": "Remises mensuelles", "type": "float", "min": 0, "max": 100, "unit": "K€", "default": 3.0},
            {"key": "mois_debut",  "label": "Mois de début",      "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",        "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
        ],
    },
    "C08": {
        "categorie"    : "🔵 CA & Commercial",
        "label"        : "Ouverture nouveau segment produit",
        "description"  : "Lancement d'une nouvelle gamme ou d'un nouveau marché. CA additionnel à partir du lancement.",
        "impact_type"  : "ca_abs",
        "kpis_impactes": ["CA_net", "MC", "VA", "EBE"],
        "sens"         : +1,
        "params": [
            {"key": "montant_ke",  "label": "CA mensuel estimé", "type": "float", "min": 0, "max": 300, "unit": "K€", "default": 5.0},
            {"key": "mois_debut",  "label": "Mois de lancement", "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",       "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": 12},
        ],
    },
    "C09": {
        "categorie"    : "🔵 CA & Commercial",
        "label"        : "Abandon gamme / référence",
        "description"  : "Retrait d'une gamme ou référence produit. CA et marge perdus à partir du mois de retrait.",
        "impact_type"  : "ca_abs",
        "kpis_impactes": ["CA_net", "MC", "VA", "EBE"],
        "sens"         : -1,
        "params": [
            {"key": "montant_ke",  "label": "CA mensuel perdu",  "type": "float", "min": 0, "max": 200, "unit": "K€", "default": 4.0},
            {"key": "mois_debut",  "label": "Mois de retrait",   "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",       "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": 12},
        ],
    },
    "C10": {
        "categorie"    : "🔵 CA & Commercial",
        "label"        : "Fermeture temporaire site",
        "description"  : "Fermeture partielle ou totale du site (travaux, sinistre, vacances imposées). "
                         "CA perdu = jours fermés × CA journalier moyen.",
        "impact_type"  : "ca_abs",
        "kpis_impactes": ["CA_net", "MC", "VA", "EBE"],
        "sens"         : -1,
        "params": [
            {"key": "montant_ke",  "label": "CA mensuel perdu",  "type": "float", "min": 0, "max": 500, "unit": "K€", "default": 15.0,
             "help": "Estimer : CA mensuel site × (nb jours fermés / nb jours ouvrés mois)"},
            {"key": "mois_debut",  "label": "Mois concerné",     "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",       "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
        ],
    },
    "C11": {
        "categorie"    : "🔵 CA & Commercial",
        "label"        : "Saisonnalité anormale",
        "description"  : "Mois atypique (météo, grève, événement local). Appliquer un % d'écart vs budget saisonnier.",
        "impact_type"  : "ca_pct",
        "kpis_impactes": ["CA_net", "MC", "VA", "EBE"],
        "sens"         : None,  # positif ou négatif selon saisie
        "params": [
            {"key": "pct_ecart",   "label": "Écart vs budget",   "type": "pct_signe", "min": -50, "max": 50, "unit": "%",
             "help": "Négatif = moins bon que budget, positif = mieux", "default": -10.0},
            {"key": "mois_debut",  "label": "Mois concerné",     "type": "mois", "min": 1, "max": 12, "unit": "", "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",       "type": "mois", "min": 1, "max": 12, "unit": "", "default": None},
        ],
    },
    "C12": {
        "categorie"    : "🔵 CA & Commercial",
        "label"        : "Nouveau concurrent sur zone",
        "description"  : "Arrivée d'un concurrent qui capte une partie du CA. Estimer le % de CA capté.",
        "impact_type"  : "ca_pct",
        "kpis_impactes": ["CA_net", "MC", "VA", "EBE"],
        "sens"         : -1,
        "params": [
            {"key": "pct_baisse",  "label": "% CA capté par concurrent", "type": "pct", "min": 0, "max": 40, "unit": "%", "default": 5.0},
            {"key": "mois_debut",  "label": "Mois d'impact",             "type": "mois", "min": 1, "max": 12, "unit": "", "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",               "type": "mois", "min": 1, "max": 12, "unit": "", "default": 12},
        ],
    },
    "C13": {
        "categorie"    : "🔵 CA & Commercial",
        "label"        : "Départ responsable commercial",
        "description"  : "Perte du responsable commercial. Impact sur CA via portefeuille client pendant la transition.",
        "impact_type"  : "ca_pct",
        "kpis_impactes": ["CA_net", "MC", "VA", "EBE"],
        "sens"         : -1,
        "params": [
            {"key": "pct_baisse",  "label": "% CA estimé perdu", "type": "pct",  "min": 0, "max": 30, "unit": "%", "default": 8.0},
            {"key": "mois_debut",  "label": "Mois de départ",    "type": "mois", "min": 1, "max": 12, "unit": "",  "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",       "type": "mois", "min": 1, "max": 12, "unit": "",  "default": 12},
        ],
    },
    "C14": {
        "categorie"    : "🔵 CA & Commercial",
        "label"        : "Renégociation contrat client annuel",
        "description"  : "Révision d'un contrat annuel à mi-exercice. Impacte le CA sur les mois restants.",
        "impact_type"  : "ca_pct",
        "kpis_impactes": ["CA_net", "MC", "VA", "EBE"],
        "sens"         : None,
        "params": [
            {"key": "pct_ecart",   "label": "Variation contrat", "type": "pct_signe", "min": -30, "max": 30, "unit": "%",
             "help": "Négatif = baisse, positif = hausse", "default": -5.0},
            {"key": "mois_debut",  "label": "Mois d'application", "type": "mois", "min": 1, "max": 12, "unit": "", "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",        "type": "mois", "min": 1, "max": 12, "unit": "", "default": 12},
        ],
    },

    # ── ACHATS & MARGE BRUTE ─────────────────────────────────────────────────
    "A01": {
        "categorie"    : "🟢 Achats & Marge brute",
        "label"        : "Hausse prix fournisseur principal",
        "description"  : "Hausse du prix d'achat non répercutée sur le tarif client → taux de marge brute dégradé.",
        "impact_type"  : "marge_pts",
        "kpis_impactes": ["MC", "VA", "EBE"],
        "sens"         : -1,
        "params": [
            {"key": "pts_marge",   "label": "Dégradation taux marge", "type": "float", "min": 0, "max": 15, "unit": "pts",
             "help": "Ex: hausse achats +5% sur 40% de taux marge → -2 pts environ", "default": 2.0},
            {"key": "mois_debut",  "label": "Mois d'application",      "type": "mois", "min": 1, "max": 12, "unit": "", "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",             "type": "mois", "min": 1, "max": 12, "unit": "", "default": 12},
        ],
    },
    "A02": {
        "categorie"    : "🟢 Achats & Marge brute",
        "label"        : "Baisse prix fournisseur (renégociation)",
        "description"  : "Renégociation réussie → amélioration du taux de marge brute à partir du mois de prise d'effet.",
        "impact_type"  : "marge_pts",
        "kpis_impactes": ["MC", "VA", "EBE"],
        "sens"         : +1,
        "params": [
            {"key": "pts_marge",   "label": "Gain taux marge",      "type": "float", "min": 0, "max": 10, "unit": "pts", "default": 1.5},
            {"key": "mois_debut",  "label": "Mois de prise d'effet","type": "mois",  "min": 1, "max": 12, "unit": "",    "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",          "type": "mois",  "min": 1, "max": 12, "unit": "",    "default": 12},
        ],
    },
    "A03": {
        "categorie"    : "🟢 Achats & Marge brute",
        "label"        : "Rupture fournisseur → approvisionnement spot",
        "description"  : "Rupture du fournisseur habituel → achat en urgence sur le marché spot à prix majoré.",
        "impact_type"  : "marge_pts",
        "kpis_impactes": ["MC", "VA", "EBE"],
        "sens"         : -1,
        "params": [
            {"key": "pts_marge",   "label": "Surcoût en pts de marge","type": "float", "min": 0, "max": 15, "unit": "pts", "default": 3.0},
            {"key": "mois_debut",  "label": "Mois de rupture",        "type": "mois",  "min": 1, "max": 12, "unit": "",    "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",            "type": "mois",  "min": 1, "max": 12, "unit": "",    "default": None},
        ],
    },
    "A04": {
        "categorie"    : "🟢 Achats & Marge brute",
        "label"        : "Nouveau fournisseur (meilleures conditions)",
        "description"  : "Référencement d'un nouveau fournisseur avec de meilleures conditions que le titulaire.",
        "impact_type"  : "marge_pts",
        "kpis_impactes": ["MC", "VA", "EBE"],
        "sens"         : +1,
        "params": [
            {"key": "pts_marge",   "label": "Gain en pts de marge","type": "float", "min": 0, "max": 10, "unit": "pts", "default": 1.0},
            {"key": "mois_debut",  "label": "Mois de référencement","type": "mois", "min": 1, "max": 12, "unit": "",    "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",          "type": "mois", "min": 1, "max": 12, "unit": "",    "default": 12},
        ],
    },
    "A05": {
        "categorie"    : "🟢 Achats & Marge brute",
        "label"        : "Hausse coûts transport entrant (fret)",
        "description"  : "Hausse du fret entrant (608100) non répercutée sur les clients.",
        "impact_type"  : "marge_pts",
        "kpis_impactes": ["MC", "VA", "EBE"],
        "sens"         : -1,
        "params": [
            {"key": "montant_ke",  "label": "Surcoût mensuel fret", "type": "float", "min": 0, "max": 50, "unit": "K€", "default": 1.5,
             "help": "Sera converti en pts de marge via CA du site"},
            {"key": "mois_debut",  "label": "Mois de départ",       "type": "mois",  "min": 1, "max": 12, "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",          "type": "mois",  "min": 1, "max": 12, "unit": "",   "default": 12},
        ],
        "impact_type"  : "serv_abs",   # fret = achats → impact MC direct
    },
    "A06": {
        "categorie"    : "🟢 Achats & Marge brute",
        "label"        : "Hausse droits de douane / import",
        "description"  : "Augmentation des droits de douane (608200) sur les achats hors UE.",
        "impact_type"  : "marge_pts",
        "kpis_impactes": ["MC", "VA", "EBE"],
        "sens"         : -1,
        "params": [
            {"key": "pts_marge",   "label": "Impact en pts de marge","type": "float", "min": 0, "max": 10, "unit": "pts", "default": 0.5},
            {"key": "mois_debut",  "label": "Mois d'application",    "type": "mois",  "min": 1, "max": 12, "unit": "",    "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",           "type": "mois",  "min": 1, "max": 12, "unit": "",    "default": 12},
        ],
    },
    "A07": {
        "categorie"    : "🟢 Achats & Marge brute",
        "label"        : "RFA fournisseur obtenu / annulé",
        "description"  : "Ristourne de fin d'année fournisseur (609300) confirmée, révisée ou annulée.",
        "impact_type"  : "ebe_abs",
        "kpis_impactes": ["MC", "VA", "EBE"],
        "sens"         : None,
        "params": [
            {"key": "montant_ke",  "label": "Montant RFA (+ = gain)", "type": "float_signe", "min": -50, "max": 50, "unit": "K€",
             "help": "Positif si RFA reçue, négatif si RFA annulée", "default": 5.0},
            {"key": "mois_debut",  "label": "Mois de comptabilisation","type": "mois", "min": 1, "max": 12, "unit": "", "default": 12},
            {"key": "mois_fin",    "label": "Mois de fin",             "type": "mois", "min": 1, "max": 12, "unit": "", "default": 12},
        ],
    },
    "A08": {
        "categorie"    : "🟢 Achats & Marge brute",
        "label"        : "Déstockage (liquidation à prix réduit)",
        "description"  : "Vente de stock dormant avec remise importante. CA augmente mais marge brute baisse.",
        "impact_type"  : "marge_pts",
        "kpis_impactes": ["MC", "VA", "EBE"],
        "sens"         : -1,
        "params": [
            {"key": "pts_marge",   "label": "Dégradation taux marge","type": "float", "min": 0, "max": 20, "unit": "pts",
             "help": "Estimer la perte de marge sur le stock liquidé", "default": 5.0},
            {"key": "mois_debut",  "label": "Mois de déstockage",    "type": "mois",  "min": 1, "max": 12, "unit": "",    "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",           "type": "mois",  "min": 1, "max": 12, "unit": "",    "default": None},
        ],
    },
    "A09": {
        "categorie"    : "🟢 Achats & Marge brute",
        "label"        : "Mix produit défavorable",
        "description"  : "Glissement du mix vers des gammes moins rentables sans baisse du CA total.",
        "impact_type"  : "marge_pts",
        "kpis_impactes": ["MC", "VA", "EBE"],
        "sens"         : -1,
        "params": [
            {"key": "pts_marge",   "label": "Perte en pts de marge","type": "float", "min": 0, "max": 10, "unit": "pts", "default": 1.5},
            {"key": "mois_debut",  "label": "Mois d'impact",        "type": "mois",  "min": 1, "max": 12, "unit": "",    "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",          "type": "mois",  "min": 1, "max": 12, "unit": "",    "default": 12},
        ],
    },
    "A10": {
        "categorie"    : "🟢 Achats & Marge brute",
        "label"        : "Escomptes fournisseurs renforcés",
        "description"  : "Paiement anticipé fournisseurs en échange d'escomptes supplémentaires (765000).",
        "impact_type"  : "ebe_abs",
        "kpis_impactes": ["MC", "VA", "EBE"],
        "sens"         : +1,
        "params": [
            {"key": "montant_ke",  "label": "Escomptes mensuels supplémentaires","type": "float", "min": 0, "max": 20, "unit": "K€", "default": 1.0},
            {"key": "mois_debut",  "label": "Mois de début",                    "type": "mois",  "min": 1, "max": 12, "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",                      "type": "mois",  "min": 1, "max": 12, "unit": "",   "default": 12},
        ],
    },

    # ── CHARGES DE PERSONNEL ─────────────────────────────────────────────────
    "P01": {
        "categorie"    : "🟠 Charges de personnel",
        "label"        : "Recrutement CDI",
        "description"  : "Embauche d'un nouveau salarié en CDI. Coût mensuel = salaire brut × (1 + taux charges patronales).",
        "impact_type"  : "pers_abs",
        "kpis_impactes": ["EBE"],
        "sens"         : -1,
        "params": [
            {"key": "salaire_brut_ke","label": "Salaire brut mensuel",  "type": "float", "min": 0, "max": 20,  "unit": "K€", "default": 3.0},
            {"key": "taux_charges",   "label": "Taux charges patronales","type": "pct",   "min": 30,"max": 60,  "unit": "%",  "default": 45.0},
            {"key": "mois_debut",     "label": "Mois d'embauche",        "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
            {"key": "mois_fin",       "label": "Mois de fin",            "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": 12},
        ],
    },
    "P02": {
        "categorie"    : "🟠 Charges de personnel",
        "label"        : "Départ non remplacé",
        "description"  : "Économie de masse salariale suite à un départ sans remplacement prévu.",
        "impact_type"  : "pers_abs",
        "kpis_impactes": ["EBE"],
        "sens"         : +1,
        "params": [
            {"key": "salaire_brut_ke","label": "Salaire brut mensuel",  "type": "float", "min": 0, "max": 20,  "unit": "K€", "default": 2.5},
            {"key": "taux_charges",   "label": "Taux charges patronales","type": "pct",   "min": 30,"max": 60,  "unit": "%",  "default": 45.0},
            {"key": "mois_debut",     "label": "Mois de départ",         "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
            {"key": "mois_fin",       "label": "Mois de fin",            "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": 12},
        ],
    },
    "P03": {
        "categorie"    : "🟠 Charges de personnel",
        "label"        : "Arrêt maladie longue durée",
        "description"  : "Salarié en arrêt prolongé. Coût net = salaire maintenu - remboursement prévoyance.",
        "impact_type"  : "pers_abs",
        "kpis_impactes": ["EBE"],
        "sens"         : None,
        "params": [
            {"key": "cout_net_ke", "label": "Coût net mensuel",         "type": "float", "min": 0, "max": 10,  "unit": "K€",
             "help": "Salaire maintenu - IJSS - prévoyance. Souvent proche de 0 selon accord d'entreprise", "default": 0.5},
            {"key": "mois_debut",  "label": "Mois de début arrêt",      "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin estimé",       "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": 12},
        ],
    },
    "P04": {
        "categorie"    : "🟠 Charges de personnel",
        "label"        : "NAO — hausse masse salariale",
        "description"  : "Négociation annuelle obligatoire (NAO). Hausse en % appliquée à la masse salariale totale.",
        "impact_type"  : "pers_pct",
        "kpis_impactes": ["EBE"],
        "sens"         : -1,
        "params": [
            {"key": "pct_hausse",  "label": "Hausse masse salariale",  "type": "pct",   "min": 0, "max": 10,  "unit": "%",  "default": 2.5},
            {"key": "mois_debut",  "label": "Mois d'application",      "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",             "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": 12},
        ],
    },
    "P05": {
        "categorie"    : "🟠 Charges de personnel",
        "label"        : "Recours intérim structurel",
        "description"  : "Recours à l'intérim pour palier un sous-effectif ou une suractivité.",
        "impact_type"  : "serv_abs",
        "kpis_impactes": ["VA", "EBE"],
        "sens"         : -1,
        "params": [
            {"key": "montant_ke",  "label": "Coût intérim mensuel",  "type": "float", "min": 0, "max": 30,  "unit": "K€", "default": 3.0},
            {"key": "mois_debut",  "label": "Mois de début",         "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",           "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": 12},
        ],
    },
    "P06": {
        "categorie"    : "🟠 Charges de personnel",
        "label"        : "Fin recours intérim",
        "description"  : "Arrêt du recours à l'intérim. Économie directe sur les charges de services extérieurs.",
        "impact_type"  : "serv_abs",
        "kpis_impactes": ["VA", "EBE"],
        "sens"         : +1,
        "params": [
            {"key": "montant_ke",  "label": "Économie mensuelle intérim","type": "float", "min": 0, "max": 30, "unit": "K€", "default": 3.0},
            {"key": "mois_debut",  "label": "Mois d'arrêt",              "type": "mois",  "min": 1, "max": 12, "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",               "type": "mois",  "min": 1, "max": 12, "unit": "",   "default": 12},
        ],
    },
    "P07": {
        "categorie"    : "🟠 Charges de personnel",
        "label"        : "Prime exceptionnelle",
        "description"  : "Prime hors budget versée (performance, fidélisation, prime de départ…).",
        "impact_type"  : "pers_abs",
        "kpis_impactes": ["EBE"],
        "sens"         : -1,
        "params": [
            {"key": "montant_ke",  "label": "Montant brut prime",  "type": "float", "min": 0, "max": 100, "unit": "K€", "default": 5.0},
            {"key": "mois_debut",  "label": "Mois de versement",   "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",         "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
        ],
    },
    "P08": {
        "categorie"    : "🟠 Charges de personnel",
        "label"        : "Chômage partiel",
        "description"  : "Activité partielle : le salarié est payé partiellement, l'État rembourse une partie. "
                         "Impact net = coût employeur - remboursement ASP.",
        "impact_type"  : "pers_abs",
        "kpis_impactes": ["EBE"],
        "sens"         : +1,
        "params": [
            {"key": "montant_ke",  "label": "Économie nette mensuelle","type": "float", "min": 0, "max": 50, "unit": "K€",
             "help": "Économie = charges non payées - remboursement ASP attendu", "default": 5.0},
            {"key": "mois_debut",  "label": "Mois de début",           "type": "mois",  "min": 1, "max": 12, "unit": "", "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",             "type": "mois",  "min": 1, "max": 12, "unit": "", "default": 12},
        ],
    },
    "P09": {
        "categorie"    : "🟠 Charges de personnel",
        "label"        : "Rupture conventionnelle",
        "description"  : "Indemnités de rupture conventionnelle hors budget.",
        "impact_type"  : "pers_abs",
        "kpis_impactes": ["EBE"],
        "sens"         : -1,
        "params": [
            {"key": "montant_ke",  "label": "Montant total indemnités","type": "float", "min": 0, "max": 100, "unit": "K€", "default": 8.0},
            {"key": "mois_debut",  "label": "Mois de signature",       "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",             "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
        ],
    },
    "P10": {
        "categorie"    : "🟠 Charges de personnel",
        "label"        : "Formation longue (salarié indisponible)",
        "description"  : "Salarié en formation longue durée : coût pédagogique additionnel et perte de productivité.",
        "impact_type"  : "pers_abs",
        "kpis_impactes": ["EBE"],
        "sens"         : -1,
        "params": [
            {"key": "montant_ke",  "label": "Coût formation mensuel","type": "float", "min": 0, "max": 10, "unit": "K€", "default": 1.0},
            {"key": "mois_debut",  "label": "Mois de début",         "type": "mois",  "min": 1, "max": 12, "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",           "type": "mois",  "min": 1, "max": 12, "unit": "",   "default": 12},
        ],
    },
    "P11": {
        "categorie"    : "🟠 Charges de personnel",
        "label"        : "Hausse cotisations sociales",
        "description"  : "Changement de taux URSSAF, retraite ou prévoyance décidé hors budget.",
        "impact_type"  : "pers_pct",
        "kpis_impactes": ["EBE"],
        "sens"         : -1,
        "params": [
            {"key": "pct_hausse",  "label": "Hausse cotisations",  "type": "pct",  "min": 0, "max": 5,  "unit": "%",  "default": 0.5},
            {"key": "mois_debut",  "label": "Mois d'application",  "type": "mois", "min": 1, "max": 12, "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",         "type": "mois", "min": 1, "max": 12, "unit": "",   "default": 12},
        ],
    },
    "P12": {
        "categorie"    : "🟠 Charges de personnel",
        "label"        : "Variation rémunération gérant",
        "description"  : "Révision de la rémunération du gérant (642000) en cours d'exercice.",
        "impact_type"  : "pers_abs",
        "kpis_impactes": ["EBE"],
        "sens"         : None,
        "params": [
            {"key": "delta_ke",    "label": "Variation mensuelle (+ = hausse)","type": "float_signe","min": -10, "max": 10, "unit": "K€",
             "help": "Positif = hausse (charge +), négatif = baisse (charge -)", "default": 1.0},
            {"key": "mois_debut",  "label": "Mois d'application",              "type": "mois", "min": 1, "max": 12, "unit": "", "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",                     "type": "mois", "min": 1, "max": 12, "unit": "", "default": 12},
        ],
    },

    # ── SERVICES EXTÉRIEURS & FRAIS GÉNÉRAUX ─────────────────────────────────
    "S01": {
        "categorie"    : "🔴 Services ext. & Frais généraux",
        "label"        : "Travaux / rénovation imprévus",
        "description"  : "Travaux non budgétés (615000). Impact VA → EBE en cascade.",
        "impact_type"  : "serv_abs",
        "kpis_impactes": ["VA", "EBE"],
        "sens"         : -1,
        "params": [
            {"key": "montant_ke",  "label": "Coût mensuel travaux", "type": "float", "min": 0, "max": 100, "unit": "K€", "default": 5.0},
            {"key": "mois_debut",  "label": "Mois de début",        "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",          "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
        ],
    },
    "S02": {
        "categorie"    : "🔴 Services ext. & Frais généraux",
        "label"        : "Renégociation loyer à la baisse",
        "description"  : "Renégociation du bail commercial (613200). Économie mensuelle à partir du mois de prise d'effet.",
        "impact_type"  : "serv_abs",
        "kpis_impactes": ["VA", "EBE"],
        "sens"         : +1,
        "params": [
            {"key": "montant_ke",  "label": "Économie mensuelle loyer","type": "float", "min": 0, "max": 20, "unit": "K€", "default": 1.5},
            {"key": "mois_debut",  "label": "Mois de prise d'effet",   "type": "mois",  "min": 1, "max": 12, "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",             "type": "mois",  "min": 1, "max": 12, "unit": "",   "default": 12},
        ],
    },
    "S03": {
        "categorie"    : "🔴 Services ext. & Frais généraux",
        "label"        : "Hausse loyer (indexation / renouvellement bail)",
        "description"  : "Révision à la hausse du loyer commercial. Surcoût mensuel permanent.",
        "impact_type"  : "serv_abs",
        "kpis_impactes": ["VA", "EBE"],
        "sens"         : -1,
        "params": [
            {"key": "montant_ke",  "label": "Surcoût mensuel loyer","type": "float", "min": 0, "max": 20, "unit": "K€", "default": 1.0},
            {"key": "mois_debut",  "label": "Mois de prise d'effet","type": "mois",  "min": 1, "max": 12, "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",          "type": "mois",  "min": 1, "max": 12, "unit": "",   "default": 12},
        ],
    },
    "S04": {
        "categorie"    : "🔴 Services ext. & Frais généraux",
        "label"        : "Nouveau contrat de maintenance",
        "description"  : "Contrat de maintenance non budgété (615200). Charge mensuelle récurrente.",
        "impact_type"  : "serv_abs",
        "kpis_impactes": ["VA", "EBE"],
        "sens"         : -1,
        "params": [
            {"key": "montant_ke",  "label": "Coût mensuel contrat","type": "float", "min": 0, "max": 20, "unit": "K€", "default": 0.8},
            {"key": "mois_debut",  "label": "Mois de début",       "type": "mois",  "min": 1, "max": 12, "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",         "type": "mois",  "min": 1, "max": 12, "unit": "",   "default": 12},
        ],
    },
    "S05": {
        "categorie"    : "🔴 Services ext. & Frais généraux",
        "label"        : "Hausse coûts énergie",
        "description"  : "Révision à la hausse du contrat d'énergie (635810 ou charges diverses).",
        "impact_type"  : "serv_abs",
        "kpis_impactes": ["VA", "EBE"],
        "sens"         : -1,
        "params": [
            {"key": "montant_ke",  "label": "Surcoût mensuel énergie","type": "float", "min": 0, "max": 10, "unit": "K€", "default": 0.5},
            {"key": "mois_debut",  "label": "Mois d'impact",          "type": "mois",  "min": 1, "max": 12, "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",            "type": "mois",  "min": 1, "max": 12, "unit": "",   "default": 12},
        ],
    },
    "S06": {
        "categorie"    : "🔴 Services ext. & Frais généraux",
        "label"        : "Hausse cotisations assurances",
        "description"  : "Révision à la hausse des primes d'assurance (616x) lors du renouvellement.",
        "impact_type"  : "serv_abs",
        "kpis_impactes": ["VA", "EBE"],
        "sens"         : -1,
        "params": [
            {"key": "montant_ke",  "label": "Surcoût mensuel assurance","type": "float", "min": 0, "max": 5, "unit": "K€", "default": 0.3},
            {"key": "mois_debut",  "label": "Mois de renouvellement",   "type": "mois",  "min": 1, "max": 12,"unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",              "type": "mois",  "min": 1, "max": 12,"unit": "",   "default": 12},
        ],
    },
    "S07": {
        "categorie"    : "🔴 Services ext. & Frais généraux",
        "label"        : "Honoraires exceptionnels (avocat, conseil, audit)",
        "description"  : "Recours à des prestations externes non prévues au budget (622xxx).",
        "impact_type"  : "serv_abs",
        "kpis_impactes": ["VA", "EBE"],
        "sens"         : -1,
        "params": [
            {"key": "montant_ke",  "label": "Montant mensuel honoraires","type": "float", "min": 0, "max": 50, "unit": "K€", "default": 3.0},
            {"key": "mois_debut",  "label": "Mois de début",             "type": "mois",  "min": 1, "max": 12, "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",               "type": "mois",  "min": 1, "max": 12, "unit": "",   "default": None},
        ],
    },
    "S08": {
        "categorie"    : "🔴 Services ext. & Frais généraux",
        "label"        : "Investissement IT non budgété (en charge)",
        "description"  : "Licence, abonnement ou prestation IT passée en charge (626300, 622700).",
        "impact_type"  : "serv_abs",
        "kpis_impactes": ["VA", "EBE"],
        "sens"         : -1,
        "params": [
            {"key": "montant_ke",  "label": "Coût mensuel IT","type": "float", "min": 0, "max": 20, "unit": "K€", "default": 1.0},
            {"key": "mois_debut",  "label": "Mois de début",  "type": "mois",  "min": 1, "max": 12, "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",    "type": "mois",  "min": 1, "max": 12, "unit": "",   "default": 12},
        ],
    },
    "S09": {
        "categorie"    : "🔴 Services ext. & Frais généraux",
        "label"        : "Économie frais de déplacements",
        "description"  : "Réduction des déplacements (625100/625200) suite à télétravail ou politique de sobriété.",
        "impact_type"  : "serv_abs",
        "kpis_impactes": ["VA", "EBE"],
        "sens"         : +1,
        "params": [
            {"key": "montant_ke",  "label": "Économie mensuelle déplacements","type": "float", "min": 0, "max": 10, "unit": "K€", "default": 0.8},
            {"key": "mois_debut",  "label": "Mois de début",                 "type": "mois",  "min": 1, "max": 12, "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",                   "type": "mois",  "min": 1, "max": 12, "unit": "",   "default": 12},
        ],
    },
    "S10": {
        "categorie"    : "🔴 Services ext. & Frais généraux",
        "label"        : "Changement prestataire logistique",
        "description"  : "Nouveau prestataire de transport/logistique (624100). Delta mensuel vs ancien contrat.",
        "impact_type"  : "serv_abs",
        "kpis_impactes": ["VA", "EBE"],
        "sens"         : None,
        "params": [
            {"key": "delta_ke",    "label": "Delta mensuel (+ = économie)","type": "float_signe","min": -20, "max": 20, "unit": "K€",
             "help": "Positif = moins cher, négatif = plus cher", "default": -0.5},
            {"key": "mois_debut",  "label": "Mois de changement",          "type": "mois", "min": 1, "max": 12, "unit": "", "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",                 "type": "mois", "min": 1, "max": 12, "unit": "", "default": 12},
        ],
    },
    "S11": {
        "categorie"    : "🔴 Services ext. & Frais généraux",
        "label"        : "Résiliation contrat sous-traitance",
        "description"  : "Fin d'un contrat de sous-traitance logistique (611000). Économie ou pénalité de résiliation.",
        "impact_type"  : "serv_abs",
        "kpis_impactes": ["VA", "EBE"],
        "sens"         : None,
        "params": [
            {"key": "delta_ke",    "label": "Impact mensuel net (+ = économie)","type": "float_signe","min": -20, "max": 20, "unit": "K€",
             "help": "Positif = économie nette, négatif = pénalité de résiliation", "default": 2.0},
            {"key": "mois_debut",  "label": "Mois d'effet",                     "type": "mois", "min": 1, "max": 12, "unit": "", "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",                      "type": "mois", "min": 1, "max": 12, "unit": "", "default": 12},
        ],
    },
    "S12": {
        "categorie"    : "🔴 Services ext. & Frais généraux",
        "label"        : "Hausse abonnements SaaS / logiciels",
        "description"  : "Révision tarifaire des abonnements logiciels (ERP, CRM, BI…) — 626300.",
        "impact_type"  : "serv_abs",
        "kpis_impactes": ["VA", "EBE"],
        "sens"         : -1,
        "params": [
            {"key": "montant_ke",  "label": "Surcoût mensuel abonnements","type": "float", "min": 0, "max": 5, "unit": "K€", "default": 0.3},
            {"key": "mois_debut",  "label": "Mois de début",              "type": "mois",  "min": 1, "max": 12,"unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",               "type": "mois",  "min": 1, "max": 12,"unit": "",   "default": 12},
        ],
    },

    # ── ÉVÉNEMENTS EXCEPTIONNELS ─────────────────────────────────────────────
    "E01": {
        "categorie"    : "⚪ Événements exceptionnels",
        "label"        : "Sinistre (incendie, dégât des eaux…)",
        "description"  : "Impact net = pertes non assurées. Si assurance couvre, saisir le solde non remboursé.",
        "impact_type"  : "ebe_abs",
        "kpis_impactes": ["EBE"],
        "sens"         : -1,
        "params": [
            {"key": "montant_ke",  "label": "Perte nette mensuelle",  "type": "float", "min": 0, "max": 200, "unit": "K€",
             "help": "Pertes totales moins remboursement assurance attendu", "default": 10.0},
            {"key": "mois_debut",  "label": "Mois du sinistre",       "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin impact",     "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
        ],
    },
    "E02": {
        "categorie"    : "⚪ Événements exceptionnels",
        "label"        : "Litige commercial — provision",
        "description"  : "Constitution d'une provision pour risque (681500) suite à un litige client ou fournisseur.",
        "impact_type"  : "ebe_abs",
        "kpis_impactes": ["EBE"],
        "sens"         : -1,
        "params": [
            {"key": "montant_ke",  "label": "Montant provisionné",  "type": "float", "min": 0, "max": 200, "unit": "K€", "default": 15.0},
            {"key": "mois_debut",  "label": "Mois de provisionnement","type": "mois", "min": 1, "max": 12,  "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",           "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
        ],
    },
    "E03": {
        "categorie"    : "⚪ Événements exceptionnels",
        "label"        : "Subvention obtenue",
        "description"  : "Subvention d'exploitation reçue hors budget (741000 / aides AURA, OPCO…).",
        "impact_type"  : "ebe_abs",
        "kpis_impactes": ["EBE"],
        "sens"         : +1,
        "params": [
            {"key": "montant_ke",  "label": "Montant subvention",  "type": "float", "min": 0, "max": 100, "unit": "K€", "default": 5.0},
            {"key": "mois_debut",  "label": "Mois d'encaissement", "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",         "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
        ],
    },
    "E04": {
        "categorie"    : "⚪ Événements exceptionnels",
        "label"        : "Subvention annulée / remboursée",
        "description"  : "Subvention budgétée mais non obtenue, ou remboursement suite à contrôle.",
        "impact_type"  : "ebe_abs",
        "kpis_impactes": ["EBE"],
        "sens"         : -1,
        "params": [
            {"key": "montant_ke",  "label": "Montant annulé",      "type": "float", "min": 0, "max": 100, "unit": "K€", "default": 3.0},
            {"key": "mois_debut",  "label": "Mois d'impact",       "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",         "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
        ],
    },
    "E05": {
        "categorie"    : "⚪ Événements exceptionnels",
        "label"        : "Redressement fiscal / URSSAF",
        "description"  : "Régularisation suite à contrôle fiscal ou URSSAF. Impact exceptionnel sur le résultat.",
        "impact_type"  : "ebe_abs",
        "kpis_impactes": ["EBE"],
        "sens"         : -1,
        "params": [
            {"key": "montant_ke",  "label": "Montant redressement","type": "float", "min": 0, "max": 500, "unit": "K€", "default": 20.0},
            {"key": "mois_debut",  "label": "Mois de notification","type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",         "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
        ],
    },
    "E06": {
        "categorie"    : "⚪ Événements exceptionnels",
        "label"        : "Remboursement assurance",
        "description"  : "Indemnisation reçue d'un assureur (sinistre précédent, RC pro…).",
        "impact_type"  : "ebe_abs",
        "kpis_impactes": ["EBE"],
        "sens"         : +1,
        "params": [
            {"key": "montant_ke",  "label": "Montant remboursé",   "type": "float", "min": 0, "max": 200, "unit": "K€", "default": 8.0},
            {"key": "mois_debut",  "label": "Mois d'encaissement", "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",         "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
        ],
    },
    "E07": {
        "categorie"    : "⚪ Événements exceptionnels",
        "label"        : "Cession d'actif (véhicule, matériel)",
        "description"  : "Vente d'un actif immobilisé. Plus ou moins-value comptable = prix cession - VCN.",
        "impact_type"  : "ebe_abs",
        "kpis_impactes": ["EBE"],
        "sens"         : None,
        "params": [
            {"key": "delta_ke",    "label": "Plus-value nette (+ = gain)","type": "float_signe","min": -50, "max": 50, "unit": "K€",
             "help": "Positif = plus-value, négatif = moins-value (VCN > prix cession)", "default": 2.0},
            {"key": "mois_debut",  "label": "Mois de cession",            "type": "mois", "min": 1, "max": 12, "unit": "", "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",                "type": "mois", "min": 1, "max": 12, "unit": "", "default": None},
        ],
    },
    "E08": {
        "categorie"    : "⚪ Événements exceptionnels",
        "label"        : "Perte sur créances irrécouvrables",
        "description"  : "Client en procédure collective. Perte définitive comptabilisée en 654000.",
        "impact_type"  : "ebe_abs",
        "kpis_impactes": ["EBE"],
        "sens"         : -1,
        "params": [
            {"key": "montant_ke",  "label": "Montant créance perdue","type": "float", "min": 0, "max": 200, "unit": "K€", "default": 10.0},
            {"key": "mois_debut",  "label": "Mois de constatation",  "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",           "type": "mois",  "min": 1, "max": 12,  "unit": "",   "default": None},
        ],
    },
    "E09": {
        "categorie"    : "⚪ Événements exceptionnels",
        "label"        : "CFE / taxe foncière — régularisation",
        "description"  : "Ajustement suite à avis de CFE ou taxe foncière révisé.",
        "impact_type"  : "ebe_abs",
        "kpis_impactes": ["EBE"],
        "sens"         : None,
        "params": [
            {"key": "delta_ke",    "label": "Régularisation (- = surcoût)","type": "float_signe","min": -20, "max": 20, "unit": "K€",
             "help": "Négatif = supplément à payer, positif = dégrèvement", "default": -1.5},
            {"key": "mois_debut",  "label": "Mois d'avis",                 "type": "mois", "min": 1, "max": 12, "unit": "", "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",                 "type": "mois", "min": 1, "max": 12, "unit": "", "default": None},
        ],
    },
    "E10": {
        "categorie"    : "⚪ Événements exceptionnels",
        "label"        : "Participation / intéressement révisé",
        "description"  : "Révision de la provision pour participation ou intéressement en cours d'exercice.",
        "impact_type"  : "ebe_abs",
        "kpis_impactes": ["EBE"],
        "sens"         : None,
        "params": [
            {"key": "delta_ke",    "label": "Variation provision (- = hausse)","type": "float_signe","min": -50, "max": 50, "unit": "K€",
             "help": "Négatif = provision plus élevée (résultat meilleur), positif = reprise", "default": -5.0},
            {"key": "mois_debut",  "label": "Mois d'ajustement",              "type": "mois", "min": 1, "max": 12, "unit": "", "default": None},
            {"key": "mois_fin",    "label": "Mois de fin",                    "type": "mois", "min": 1, "max": 12, "unit": "", "default": None},
        ],
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# PERSISTANCE
# ══════════════════════════════════════════════════════════════════════════════

def load_hypotheses(path: Path = DEFAULT_PATH) -> dict:
    """Charge le JSON des hypothèses. Retourne structure vide si absent."""
    if not Path(path).exists():
        return {"meta": {}, "hypotheses": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"meta": {}, "hypotheses": []}


def save_hypotheses(hyp_data: dict, path: Path = DEFAULT_PATH) -> None:
    """Sauvegarde le JSON des hypothèses avec timestamp."""
    hyp_data.setdefault("meta", {})
    hyp_data["meta"]["last_updated"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(hyp_data, f, indent=2, ensure_ascii=False)


def add_hypothesis(
    hyp_data  : dict,
    type_id   : str,
    site_code : str,
    params    : dict,
    label     : str = "",
    note      : str = "",
) -> dict:
    """Ajoute une hypothèse. Retourne le dict mis à jour (sans sauvegarder)."""
    hyp_data.setdefault("hypotheses", [])
    hyp_data["hypotheses"].append({
        "uuid"      : str(uuid.uuid4())[:8],
        "type_id"   : type_id,
        "site_code" : site_code,
        "label"     : label or HYPOTHESES_LIBRARY[type_id]["label"],
        "params"    : params,
        "note"      : note,
        "created_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    })
    return hyp_data


def delete_hypothesis(hyp_data: dict, hyp_uuid: str) -> dict:
    """Supprime une hypothèse par UUID."""
    hyp_data["hypotheses"] = [
        h for h in hyp_data.get("hypotheses", [])
        if h["uuid"] != hyp_uuid
    ]
    return hyp_data


def get_hypotheses_for_site(hyp_data: dict, site_code: str) -> List[dict]:
    """Retourne toutes les hypothèses actives pour un site donné."""
    return [
        h for h in hyp_data.get("hypotheses", [])
        if h["site_code"] == site_code
    ]


# ══════════════════════════════════════════════════════════════════════════════
# CALCUL D'IMPACT — CASCADE SIG CORRECTE
# ══════════════════════════════════════════════════════════════════════════════

def compute_hypothesis_monthly_impact(
    hyp       : dict,
    budget_ca_m: List[float],      # 12 valeurs CA budget mensuel
    taux_marge : float,             # taux de marge brute moyen du site (0.0 – 1.0)
    budget_pers_m: List[float],    # 12 valeurs charges personnel budget mensuel (valeur abs)
    budget_serv_m: List[float],    # 12 valeurs services ext budget mensuel (valeur abs)
    mois_reel  : int,               # seuls les mois futurs sont modifiés
) -> Dict[str, List[float]]:
    """
    Calcule l'impact mensuel d'une hypothèse sur chaque KPI.

    Retourne un dict {kpi: [delta_m1, …, delta_m12]}
    Valeurs en euros (positif = amélioration du KPI).
    Seuls les mois futurs (> mois_reel) sont impactés.

    CASCADE SIG :
      CA_net  : impact direct CA
      MC      : ΔCA × taux_marge + impact direct marge
      VA      : ΔMC + impact direct services (VA→EBE)
      EBE     : ΔVA + impact direct EBE (personnel, exceptionnel)
    """
    lib = HYPOTHESES_LIBRARY.get(hyp["type_id"], {})
    p   = hyp["params"]
    impact_type = lib.get("impact_type", "ebe_abs")

    # Plage de mois impactés (futurs uniquement)
    m_debut = int(p.get("mois_debut", 1) or 1)
    m_fin   = int(p.get("mois_fin",  12) or 12)
    mois_actifs = [
        m for m in range(m_debut, m_fin + 1)
        if m > mois_reel  # on ne révise que les mois futurs
    ]

    # Initialiser les deltas à zéro
    deltas = {kpi: [0.0] * 12 for kpi in KPIS_RFC}

    if not mois_actifs:
        return deltas

    for m in mois_actifs:
        i = m - 1  # index 0-based
        ca_m   = budget_ca_m[i]   if i < len(budget_ca_m)   else 0.0
        pers_m = budget_pers_m[i] if i < len(budget_pers_m) else 0.0
        serv_m = budget_serv_m[i] if i < len(budget_serv_m) else 0.0

        # ── Impact CA direct ──────────────────────────────────────────────
        if impact_type == "ca_abs":
            delta_ca = float(p.get("montant_ke", 0)) * 1000 * lib.get("sens", -1)
            if lib.get("sens") is None:
                # Hypothèse à sens variable → utiliser pct_ecart
                pct = float(p.get("pct_ecart", p.get("delta_ke", 0))) / 100
                delta_ca = ca_m * pct

        elif impact_type == "ca_pct":
            pct = float(p.get("pct_hausse", p.get("pct_baisse", p.get("pct_ecart", 0)))) / 100
            delta_ca = ca_m * pct * lib.get("sens", -1) if lib.get("sens") is not None else ca_m * float(p.get("pct_ecart", 0)) / 100
        else:
            delta_ca = 0.0

        # ── Impact Marge direct (variations de taux) ──────────────────────
        if impact_type == "marge_pts":
            pts = float(p.get("pts_marge", p.get("montant_ke", 0)))
            delta_mc_direct = ca_m * (pts / 100) * lib.get("sens", -1)
        else:
            delta_mc_direct = 0.0

        # ── Impact Services ext. (VA → EBE) ──────────────────────────────
        if impact_type == "serv_abs":
            if lib.get("sens") is None:
                delta_serv = float(p.get("delta_ke", 0)) * 1000
            else:
                delta_serv = float(p.get("montant_ke", 0)) * 1000 * lib.get("sens", -1)
        else:
            delta_serv = 0.0

        # ── Impact Personnel (EBE uniquement) ────────────────────────────
        if impact_type == "pers_abs":
            if lib.get("sens") is None:
                delta_pers = float(p.get("cout_net_ke", p.get("delta_ke", 0))) * 1000
            else:
                sal = float(p.get("salaire_brut_ke", p.get("montant_ke", 0))) * 1000
                tc  = float(p.get("taux_charges", 45)) / 100
                delta_pers = sal * (1 + tc) * lib.get("sens", -1)
        elif impact_type == "pers_pct":
            pct  = float(p.get("pct_hausse", 0)) / 100
            delta_pers = pers_m * pct * lib.get("sens", -1)
        else:
            delta_pers = 0.0

        # ── Impact EBE direct (exceptionnel, provisions, taxes) ───────────
        if impact_type == "ebe_abs":
            if lib.get("sens") is None:
                delta_ebe_direct = float(p.get("montant_ke", p.get("delta_ke", 0))) * 1000
            else:
                delta_ebe_direct = float(p.get("montant_ke", p.get("delta_ke", 0))) * 1000 * lib.get("sens", -1)
        else:
            delta_ebe_direct = 0.0

        # ── CASCADE SIG ───────────────────────────────────────────────────
        # CA_net
        deltas["CA_net"][i] += delta_ca

        # MC = CA_net × taux_marge + impact marge direct
        delta_mc = delta_ca * taux_marge + delta_mc_direct
        deltas["MC"][i] += delta_mc

        # VA = MC + impact services (charges ext = déductions de VA)
        delta_va = delta_mc + delta_serv
        deltas["VA"][i] += delta_va

        # EBE = VA + impact personnel + impact EBE direct
        delta_ebe = delta_va + delta_pers + delta_ebe_direct
        deltas["EBE"][i] += delta_ebe

    return deltas


def compute_all_hypotheses_impact(
    hyp_data      : dict,
    site_code     : str,
    budget_ca_m   : List[float],
    taux_marge    : float,
    budget_pers_m : List[float],
    budget_serv_m : List[float],
    mois_reel     : int,
) -> Dict[str, List[float]]:
    """
    Cumule l'impact de toutes les hypothèses actives pour un site.

    Retourne {kpi: [delta_total_m1, …, delta_total_m12]}
    """
    cumul = {kpi: [0.0] * 12 for kpi in KPIS_RFC}

    for hyp in get_hypotheses_for_site(hyp_data, site_code):
        impact = compute_hypothesis_monthly_impact(
            hyp, budget_ca_m, taux_marge,
            budget_pers_m, budget_serv_m, mois_reel,
        )
        for kpi in KPIS_RFC:
            for i in range(12):
                cumul[kpi][i] += impact[kpi][i]

    return cumul


def get_categorie_list() -> List[str]:
    """Retourne la liste ordonnée des catégories."""
    seen, cats = set(), []
    for h in HYPOTHESES_LIBRARY.values():
        c = h["categorie"]
        if c not in seen:
            cats.append(c)
            seen.add(c)
    return cats


def get_hypotheses_by_categorie(categorie: str) -> Dict[str, dict]:
    """Retourne les hypothèses d'une catégorie donnée."""
    return {k: v for k, v in HYPOTHESES_LIBRARY.items() if v["categorie"] == categorie}
