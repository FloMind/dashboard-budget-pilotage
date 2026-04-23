"""
core/metrics.py
══════════════════════════════════════════════════════════════════════════════
FloMind Budget Dashboard — Couche de calcul des métriques de gestion

RÔLE DANS L'ARCHITECTURE
─────────────────────────
Ce module transforme les données brutes (DashboardData) en indicateurs
directement lisibles par un dirigeant. Il n'a aucune connaissance des
vues Streamlit ni de Plotly — il produit des structures de données Python
(dataclasses, DataFrames) que les vues consomment librement.

PRINCIPE DE SÉPARATION DES RESPONSABILITÉS
────────────────────────────────────────────
  loader.py   → Lit, valide, structure
  metrics.py  → Calcule les KPIs, projections et alertes   ← ICI
  forecast.py → Projette les mois futurs (rolling forecast)
  views/      → Affiche avec Streamlit + Plotly

MÉTRIQUES PRODUITES
────────────────────
  KPI Strip        : 15 indicateurs clés pour l'en-tête du dashboard
                     (CA, Marge, EBE, REX — YTD réel + budget + atterrissage)

  Atterrissage     : Projection hybride fin d'exercice par site et pour le groupe
                     Méthode : réel YTD + (budget restant × ratio tendance)

  Alertes          : Dérives matérielles détectées compte par compte
                     Double critère : |écart_%| ≥ seuil ET |écart_€| ≥ seuil
                     Priorité 1/2/3 selon intensité de la dérive

  Rankings         : Classements multi-critères (REX, EBE, CA, taux de marge)

  Contribution     : Poids de chaque site dans le total réseau (%)

  Waterfall        : Décomposition mensuelle Budget → drivers → Réel

  Évolution        : Série mensuelle budget vs réel pour un KPI

DÉPENDANCES
────────────
  numpy  >= 1.24
  pandas >= 2.0
  core.loader (DashboardData)

AUTEUR    : FloMind Consulting
CRÉÉ LE   : 2025
══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from loader import DashboardData


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES MÉTIER
# ══════════════════════════════════════════════════════════════════════════════

# Labels courts des mois pour les axes de graphiques
MOIS_LABELS: Dict[int, str] = {
    1:"Jan", 2:"Fév", 3:"Mar", 4:"Avr", 5:"Mai", 6:"Jun",
    7:"Jul", 8:"Aoû", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Déc",
}

# Seuil d'alerte en % d'écart (ex. 5% → alerte si réel > budget + 5%)
# Valeur métier typique dans les PME : entre 3% et 10% selon la maturité CDG
SEUIL_ECART_PCT_DEFAUT: float = 5.0

# Seuil d'alerte en valeur absolue (€) — filtre les micro-écarts insignifiants
# Sans ce seuil, un compte avec budget=50€ et réel=60€ générerait une alerte 20%
SEUIL_ECART_ABS_DEFAUT: float = 2_000.0

# Poids de la tendance YTD dans le calcul de l'atterrissage hybride
# 0.7 = 70% tendance + 30% budget pur
# En début d'année (peu de mois réalisés), ce poids est réduit par la méthode
POIDS_ATTERRISSAGE_TENDANCE: float = 0.70


# ══════════════════════════════════════════════════════════════════════════════
# DATACLASSES DE SORTIE
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class KPIStrip:
    """
    Ensemble des 15 indicateurs clés pour la bande d'en-tête du dashboard.

    Cette dataclass représente le "cockpit" du DG : une lecture en moins
    de 10 secondes de l'état financier du réseau à date.

    Convention d'interprétation
    ───────────────────────────
    • ca_ecart_pct > 0  → CA réel meilleur que prévu (favorable)
    • ebe_ecart_abs > 0 → EBE réel meilleur que prévu (favorable)
    • tx_ebe_reel        → marge opérationnelle réelle à date
    • ca_atterrissage    → projection CA fin d'année (hybride tendance + budget)

    Tous les montants sont en euros (€), non arrondis.
    L'arrondi (K€, M€) est délégué aux vues Streamlit.

    Attributs CA
    ------------
    ca_ytd_reel    : CA réel cumulé Jan → mois_reel
    ca_ytd_budget  : CA budget cumulé Jan → mois_reel (même périmètre)
    ca_ecart_abs   : réel - budget (€)
    ca_ecart_pct   : (réel - budget) / |budget| × 100 (%)
    ca_annuel_bgt  : CA budget total sur 12 mois (référence annuelle)
    ca_atterrissage: Projection CA fin d'exercice

    Attributs MC (Marge Commerciale)
    ---------------------------------
    mc_ytd_reel    : MC réelle cumulée YTD
    mc_ytd_budget  : MC budget cumulée YTD
    tx_mc_reel     : Taux de marge réel = MC_réel / CA_réel × 100 (%)
    tx_mc_budget   : Taux de marge budgété = MC_bgt / CA_bgt × 100 (%)

    Attributs EBE (Excédent Brut d'Exploitation)
    ---------------------------------------------
    ebe_ytd_reel     : EBE réel cumulé YTD
    ebe_ytd_budget   : EBE budget cumulé YTD
    ebe_ecart_abs    : réel - budget (€)
    tx_ebe_reel      : EBE_réel / CA_réel × 100 (%)
    tx_ebe_budget    : EBE_bgt / CA_bgt × 100 (%)
    ebe_atterrissage : Projection EBE fin d'exercice

    Attributs REX (Résultat d'Exploitation)
    ----------------------------------------
    rex_ytd_reel     : REX réel cumulé YTD
    rex_ytd_budget   : REX budget cumulé YTD
    rex_ecart_abs    : réel - budget (€)
    tx_rex_reel      : REX_réel / CA_réel × 100 (%)
    rex_atterrissage : Projection REX fin d'exercice

    Attributs méta
    --------------
    mois_reel       : Mois courant (dernier réalisé)
    n_mois_restants : 12 - mois_reel
    annee           : Exercice fiscal
    scope           : "consolidé" | code site (ex. "LYO_C")
    """
    # CA
    ca_ytd_reel    : float
    ca_ytd_budget  : float
    ca_ecart_abs   : float
    ca_ecart_pct   : float
    ca_annuel_bgt  : float
    ca_atterrissage: float
    # Marge commerciale
    mc_ytd_reel    : float
    mc_ytd_budget  : float
    tx_mc_reel     : float
    tx_mc_budget   : float
    # EBE
    ebe_ytd_reel    : float
    ebe_ytd_budget  : float
    ebe_ecart_abs   : float
    tx_ebe_reel     : float
    tx_ebe_budget   : float
    ebe_atterrissage: float
    # REX
    rex_ytd_reel    : float
    rex_ytd_budget  : float
    rex_ecart_abs   : float
    tx_rex_reel     : float
    rex_atterrissage: float
    # Méta
    mois_reel       : int
    n_mois_restants : int
    annee           : int
    scope           : str


@dataclass
class Alerte:
    """
    Représente une dérive matérielle détectée sur un compte YTD.

    Une alerte est déclenchée uniquement si DEUX conditions sont réunies :
      1. |écart_%| ≥ seuil_ecart_pct (évite les alertes sur grosse base)
      2. |écart_€| ≥ seuil_ecart_abs (évite les alertes sur micro-montants)

    Ce double critère est une bonne pratique CDG : une dérive de 20%
    sur un compte à 100€ de budget n'est pas matérielle. Une dérive
    de 3% sur la masse salariale à 200 000€ l'est fortement.

    Attributs
    ---------
    site_code      : Code site (ex. "BGR")
    site_libelle   : Nom complet du site
    compte_code    : Numéro PCG (ex. "641100")
    compte_libelle : Libellé du compte
    classe_cdg     : Classe analytique (ex. "Charges personnel")
    budget_ytd     : Montant budget cumulé YTD (signé)
    reel_ytd       : Montant réel cumulé YTD (signé)
    ecart_abs      : réel - budget (€) — positif pas forcément favorable
    ecart_pct      : (réel - budget) / |budget| × 100 (%)
    est_favorable  : True si l'écart joue en faveur du résultat
                     (logique : ecart × sens > 0)
    priorite       : 1 = critique (> 4× seuil), 2 = important (> 2×), 3 = surveillance
    """
    site_code     : str
    site_libelle  : str
    compte_code   : str
    compte_libelle: str
    classe_cdg    : str
    budget_ytd    : float
    reel_ytd      : float
    ecart_abs     : float
    ecart_pct     : float
    est_favorable : bool
    priorite      : int


@dataclass
class Atterrissage:
    """
    Projection de fin d'exercice pour un site ou le groupe consolidé.

    Méthode de calcul hybride
    ──────────────────────────
    Pour chaque KPI :
      forecast = réel_YTD + budget_reste × facteur_projection
      facteur  = (1 - poids) × 1.0 + poids × ratio_tendance
      ratio    = réel_YTD / budget_YTD

    Interprétation du ratio_tendance :
      • ratio = 1.0 → performance exactement conforme au budget
      • ratio = 1.05 → 5% de mieux que prévu → on projette +5% sur le reste
      • ratio = 0.90 → 10% de moins → on projette -10% sur le reste

    Le poids (défaut 70%) détermine l'équilibre entre :
      • 100% tendance : atterrissage très sensible à la perf YTD (volatil)
      • 0% tendance   : atterrissage = réel YTD + budget restant (optimiste)
      • 70% tendance  : compromis raisonnable pour un PME réseau

    Attributs
    ---------
    scope           : "consolidé" | code site
    annee           : Exercice (ex. 2025)
    mois_reel       : Mois courant
    ca_bgt_annuel   : Budget CA annuel (12 mois) — référence
    ca_reel_ytd     : CA réel Jan → mois_reel
    ca_forecast     : Projection CA fin d'année
    ca_reste_bgt    : CA budget des mois non réalisés (mois_reel+1 → 12)
    ca_ecart_vs_bgt : forecast - budget annuel (€) — objectif manqué/dépassé
    ebe_bgt_annuel  : Idem pour l'EBE
    ebe_reel_ytd    : …
    ebe_forecast    : …
    ebe_ecart_vs_bgt: …
    rex_bgt_annuel  : Idem pour le REX
    rex_reel_ytd    : …
    rex_forecast    : …
    rex_ecart_vs_bgt: …
    tx_ebe_forecast : ebe_forecast / ca_forecast × 100 (%)
    tx_rex_forecast : rex_forecast / ca_forecast × 100 (%)
    """
    scope           : str
    annee           : int
    mois_reel       : int
    ca_bgt_annuel   : float
    ca_reel_ytd     : float
    ca_forecast     : float
    ca_reste_bgt    : float
    ca_ecart_vs_bgt : float
    ebe_bgt_annuel  : float
    ebe_reel_ytd    : float
    ebe_forecast    : float
    ebe_ecart_vs_bgt: float
    rex_bgt_annuel  : float
    rex_reel_ytd    : float
    rex_forecast    : float
    rex_ecart_vs_bgt: float
    tx_ebe_forecast : float
    tx_rex_forecast : float


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS INTERNES (privés — préfixe _)
# ══════════════════════════════════════════════════════════════════════════════

def _safe_div(numerateur: float, denominateur: float, defaut: float = 0.0) -> float:
    """
    Division scalaire sécurisée — retourne `defaut` si le dénominateur est nul.

    Paramètres
    ----------
    numerateur   : valeur numérateur
    denominateur : valeur dénominateur
    defaut       : valeur retournée si |dénominateur| < 1e-9 (défaut : 0.0)

    Retourne
    --------
    float : numerateur / denominateur, ou defaut si division impossible.

    Notes
    -----
    Seuil 1e-9 (et non 0) pour couvrir les erreurs d'arrondi virgule flottante.
    Utilisé exclusivement dans les calculs de taux (tx_mc, tx_ebe…) où le
    dénominateur CA peut être nul pour un nouveau site.
    """
    return numerateur / denominateur if abs(denominateur) > 1e-9 else defaut


def _ytd_sig(
    data      : DashboardData,
    site_code : Optional[str] = None,
) -> Dict[str, Tuple[float, float]]:
    """
    Extrait les SIG YTD (réel, budget) depuis data.sig_ytd.

    Paramètres
    ----------
    data      : DashboardData
    site_code : code site → site spécifique | None → consolidé groupe

    Retourne
    --------
    dict {kpi: (reel_ytd, budget_ytd)}
    où kpi ∈ {"CA_net", "MC", "VA", "EBE", "REX", "RCAI", "RN"}

    Notes
    -----
    La consolidation groupe est faite par simple somme ligne par ligne.
    C'est arithmétiquement correct car les SIG sont additifs entre sites
    (pas de transactions intra-groupe dans ce modèle de données).
    """
    if site_code:
        ligne = data.sig_ytd.loc[site_code]
    else:
        ligne = data.sig_ytd.sum()   # consolidation : Σ tous les sites

    return {
        kpi: (
            float(ligne.get(f"{kpi}_rel", 0.0)),   # réel YTD
            float(ligne.get(f"{kpi}_bgt", 0.0)),   # budget YTD
        )
        for kpi in ("CA_net", "MC", "VA", "EBE", "REX", "RCAI", "RN")
    }


def _annuel_sig(
    data      : DashboardData,
    site_code : Optional[str] = None,
) -> Dict[str, float]:
    """
    Extrait les SIG budget annuels (12 mois) depuis data.sig_annuel.

    Paramètres
    ----------
    data      : DashboardData
    site_code : code site → site spécifique | None → consolidé groupe

    Retourne
    --------
    dict {kpi: valeur_annuelle_budget}
    """
    if site_code:
        ligne = data.sig_annuel.loc[site_code]
    else:
        ligne = data.sig_annuel.sum()

    return {
        kpi: float(ligne.get(kpi, 0.0))
        for kpi in ("CA_net", "MC", "VA", "EBE", "REX", "RCAI", "RN")
    }


def _compute_atterrissage_kpi(
    reel_ytd      : float,
    bgt_ytd       : float,
    bgt_annuel    : float,
    mois_reel     : int,
    poids_tendance: float = POIDS_ATTERRISSAGE_TENDANCE,
) -> float:
    """
    Projette la valeur de fin d'exercice pour un KPI unique.

    Méthode hybride (tendance pondérée + budget pur)
    ─────────────────────────────────────────────────
    1. Calcule le ratio YTD : ratio = réel_YTD / budget_YTD
       Ce ratio mesure la sur/sous-performance relative à ce jour.

    2. Applique ce ratio aux mois restants, pondéré par poids_tendance :
       facteur = (1 - poids) × 1.0 + poids × ratio

    3. Projection finale :
       atterrissage = réel_YTD + (bgt_annuel - bgt_YTD) × facteur

    Cas limites
    ───────────
    • bgt_ytd ≈ 0 : pas de base pour calculer le ratio → budget pur (facteur=1)
    • ratio >> 1   : site en très forte surperformance → projection optimiste
    • ratio << 0   : site en perte (EBE/REX négatifs) → projection conservatrice

    Paramètres
    ----------
    reel_ytd      : réel cumulé Jan → mois_reel
    bgt_ytd       : budget cumulé Jan → mois_reel (même périmètre)
    bgt_annuel    : budget total 12 mois
    mois_reel     : mois courant (1–12)
    poids_tendance: pondération de la tendance YTD (0 = budget pur, 1 = tendance pure)

    Retourne
    --------
    float : projection du KPI sur l'exercice complet

    Exemple
    -------
    >>> # Site BGR : CA réel jan-avr = 134.6K€, budget = 147.6K€, budget annuel = 430.2K€
    >>> # ratio = 134.6 / 147.6 = 0.912  (-8.8%)
    >>> # bgt_reste = 430.2 - 147.6 = 282.6K€
    >>> # facteur = 0.3 × 1.0 + 0.7 × 0.912 = 0.938
    >>> # atterrissage = 134.6 + 282.6 × 0.938 ≈ 399.9K€  (vs budget 430.2K€)
    """
    bgt_reste = bgt_annuel - bgt_ytd

    # Failsafe : si pas de budget YTD (nouveau site, budget partiel)
    if abs(bgt_ytd) < 1e-9:
        return reel_ytd + bgt_reste   # budget pur

    ratio_tendance = _safe_div(reel_ytd, bgt_ytd, defaut=1.0)

    # Facteur de projection : combine la tendance observée et le budget pur
    facteur_reste = (1 - poids_tendance) * 1.0 + poids_tendance * ratio_tendance

    return reel_ytd + bgt_reste * facteur_reste


# ══════════════════════════════════════════════════════════════════════════════
# API PUBLIQUE
# ══════════════════════════════════════════════════════════════════════════════

def compute_kpi_strip(
    data      : DashboardData,
    site_code : Optional[str] = None,
) -> KPIStrip:
    """
    Calcule les 15 KPIs pour la bande d'en-tête du dashboard.

    C'est la première fonction appelée par le tour de contrôle (écran 1)
    et par chaque vue site (écran 2). Elle produit les chiffres clés
    que le DG lit en moins de 10 secondes.

    Paramètres
    ----------
    data      : DashboardData issu de load_data()
    site_code : None → consolidé réseau | str → site spécifique (ex. "LYO_C")

    Retourne
    --------
    KPIStrip
        Dataclass avec 15 indicateurs + méta.
        Voir la documentation de KPIStrip pour le détail des attributs.

    Exemple
    -------
    >>> kpi = compute_kpi_strip(data)
    >>> print(f"CA atterrissage : {kpi.ca_atterrissage/1e3:.0f}K€")
    >>> print(f"EBE YTD : {kpi.tx_ebe_reel:.1f}%")

    >>> kpi_site = compute_kpi_strip(data, site_code="LYO_E")
    >>> print(f"LYO_E — REX écart : {kpi_site.rex_ecart_abs/1e3:+.1f}K€")
    """
    ytd = _ytd_sig(data, site_code)
    ann = _annuel_sig(data, site_code)
    mr  = data.mois_reel

    # ── Projections de fin d'exercice ─────────────────────────────────────────
    ca_att  = _compute_atterrissage_kpi(ytd["CA_net"][0], ytd["CA_net"][1], ann["CA_net"], mr)
    ebe_att = _compute_atterrissage_kpi(ytd["EBE"][0],    ytd["EBE"][1],    ann["EBE"],    mr)
    rex_att = _compute_atterrissage_kpi(ytd["REX"][0],    ytd["REX"][1],    ann["REX"],    mr)

    ca_r,  ca_b  = ytd["CA_net"]
    mc_r,  mc_b  = ytd["MC"]
    ebe_r, ebe_b = ytd["EBE"]
    rex_r, rex_b = ytd["REX"]

    return KPIStrip(
        # ── CA ─────────────────────────────────────────────────────────────
        ca_ytd_reel     = ca_r,
        ca_ytd_budget   = ca_b,
        ca_ecart_abs    = ca_r - ca_b,
        ca_ecart_pct    = _safe_div(ca_r - ca_b, abs(ca_b)) * 100,
        ca_annuel_bgt   = ann["CA_net"],
        ca_atterrissage = ca_att,
        # ── Marge commerciale ──────────────────────────────────────────────
        mc_ytd_reel     = mc_r,
        mc_ytd_budget   = mc_b,
        tx_mc_reel      = _safe_div(mc_r, ca_r) * 100,
        tx_mc_budget    = _safe_div(mc_b, ca_b) * 100,
        # ── EBE ────────────────────────────────────────────────────────────
        ebe_ytd_reel     = ebe_r,
        ebe_ytd_budget   = ebe_b,
        ebe_ecart_abs    = ebe_r - ebe_b,
        tx_ebe_reel      = _safe_div(ebe_r, ca_r) * 100,
        tx_ebe_budget    = _safe_div(ebe_b, ca_b) * 100,
        ebe_atterrissage = ebe_att,
        # ── REX ────────────────────────────────────────────────────────────
        rex_ytd_reel     = rex_r,
        rex_ytd_budget   = rex_b,
        rex_ecart_abs    = rex_r - rex_b,
        tx_rex_reel      = _safe_div(rex_r, ca_r) * 100,
        rex_atterrissage = rex_att,
        # ── Méta ────────────────────────────────────────────────────────────
        mois_reel        = mr,
        n_mois_restants  = 12 - mr,
        annee            = data.annee,
        scope            = site_code if site_code else "consolidé",
    )


def compute_atterrissage(
    data          : DashboardData,
    site_code     : Optional[str] = None,
    poids_tendance: float = POIDS_ATTERRISSAGE_TENDANCE,
) -> Atterrissage:
    """
    Calcule la projection détaillée de fin d'exercice (CA, EBE, REX).

    Différence avec compute_kpi_strip()
    ─────────────────────────────────────
    • kpi_strip   : 15 indicateurs compacts pour l'en-tête
    • atterrissage : 3 KPIs détaillés avec décomposition (YTD + reste + écart)
                     Utilisé pour le tableau de bord direction et l'export PDF.

    Paramètres
    ----------
    data          : DashboardData
    site_code     : None → consolidé | str → site spécifique
    poids_tendance: Pondération de la tendance YTD dans la projection.
                    Plage : 0.0 (budget pur) à 1.0 (tendance pure).
                    Défaut : 0.70 (70% tendance, 30% budget)

    Retourne
    --------
    Atterrissage
        Voir la documentation de la dataclass Atterrissage.

    Notes
    -----
    Calibration du poids :
      • poids_tendance = 0.0 → très conservateur (budget comme seule référence)
        Utile pour les sites stables avec peu de volatilité
      • poids_tendance = 0.7 → recommandé pour la majorité des PME réseau
      • poids_tendance = 1.0 → tendance pure (sensible aux anomalies ponctuelles)
        À éviter si un mois a eu un événement exceptionnel non récurrent
    """
    ytd = _ytd_sig(data, site_code)
    ann = _annuel_sig(data, site_code)
    mr  = data.mois_reel

    def att(kpi: str) -> float:
        """Calcule l'atterrissage pour un KPI donné."""
        reel, bgt = ytd[kpi]
        return _compute_atterrissage_kpi(reel, bgt, ann[kpi], mr, poids_tendance)

    ca_f  = att("CA_net")
    ebe_f = att("EBE")
    rex_f = att("REX")

    return Atterrissage(
        scope           = site_code or "consolidé",
        annee           = data.annee,
        mois_reel       = mr,
        # CA
        ca_bgt_annuel   = ann["CA_net"],
        ca_reel_ytd     = ytd["CA_net"][0],
        ca_forecast     = ca_f,
        ca_reste_bgt    = ann["CA_net"] - ytd["CA_net"][1],
        ca_ecart_vs_bgt = ca_f - ann["CA_net"],
        # EBE
        ebe_bgt_annuel  = ann["EBE"],
        ebe_reel_ytd    = ytd["EBE"][0],
        ebe_forecast    = ebe_f,
        ebe_ecart_vs_bgt= ebe_f - ann["EBE"],
        # REX
        rex_bgt_annuel  = ann["REX"],
        rex_reel_ytd    = ytd["REX"][0],
        rex_forecast    = rex_f,
        rex_ecart_vs_bgt= rex_f - ann["REX"],
        # Taux de marge projetés
        tx_ebe_forecast = _safe_div(ebe_f, ca_f) * 100,
        tx_rex_forecast = _safe_div(rex_f, ca_f) * 100,
    )


def compute_atterrissage_groupe(
    data          : DashboardData,
    poids_tendance: float = POIDS_ATTERRISSAGE_TENDANCE,
) -> pd.DataFrame:
    """
    Tableau d'atterrissages pour l'ensemble du réseau (groupe + chaque site).

    C'est la vue de synthèse idéale pour le comité de direction mensuel
    et pour la première page de l'export PDF.

    Paramètres
    ----------
    data          : DashboardData
    poids_tendance: Pondération tendance (voir compute_atterrissage)

    Retourne
    --------
    pd.DataFrame — 8 lignes (1 consolidé + 7 sites)
        Index   : scope ("consolidé", "LYO_C", "LYO_E", …)
        Colonnes:
          ca_bgt, ca_ytd_reel, ca_forecast, ca_ecart_bgt,
          ebe_bgt, ebe_ytd_reel, ebe_forecast, ebe_ecart_bgt,
          rex_bgt, rex_ytd_reel, rex_forecast, rex_ecart_bgt,
          tx_ebe_forecast, tx_rex_forecast
        Tous les montants sont en euros. Diviser par 1 000 pour l'affichage K€.

    Exemple
    -------
    >>> att_df = compute_atterrissage_groupe(data)
    >>> print((att_df[["ca_forecast","tx_ebe_forecast"]] / [1e3, 1]).round(1))
    """
    enregistrements = []
    for scope in [None] + data.sites:
        att = compute_atterrissage(data, scope, poids_tendance)
        enregistrements.append({
            "scope"           : att.scope,
            "ca_bgt"          : att.ca_bgt_annuel,
            "ca_ytd_reel"     : att.ca_reel_ytd,
            "ca_forecast"     : att.ca_forecast,
            "ca_ecart_bgt"    : att.ca_ecart_vs_bgt,
            "ebe_bgt"         : att.ebe_bgt_annuel,
            "ebe_ytd_reel"    : att.ebe_reel_ytd,
            "ebe_forecast"    : att.ebe_forecast,
            "ebe_ecart_bgt"   : att.ebe_ecart_vs_bgt,
            "rex_bgt"         : att.rex_bgt_annuel,
            "rex_ytd_reel"    : att.rex_reel_ytd,
            "rex_forecast"    : att.rex_forecast,
            "rex_ecart_bgt"   : att.rex_ecart_vs_bgt,
            "tx_ebe_forecast" : att.tx_ebe_forecast,
            "tx_rex_forecast" : att.tx_rex_forecast,
        })
    return pd.DataFrame(enregistrements).set_index("scope")


def compute_alertes(
    data              : DashboardData,
    seuil_ecart_pct   : float = SEUIL_ECART_PCT_DEFAUT,
    seuil_ecart_abs   : float = SEUIL_ECART_ABS_DEFAUT,
    site_code         : Optional[str] = None,
    classes_exclues   : Optional[List[str]] = None,
) -> List[Alerte]:
    """
    Détecte les dérives matérielles compte par compte sur la période YTD.

    Algorithme de détection
    ────────────────────────
    1. Agrège les montants YTD par (site, compte)
    2. Calcule l'écart absolu et le pourcentage d'écart
    3. Applique le double filtre de matérialité :
         |écart_%| ≥ seuil_pct  ET  |écart_€| ≥ seuil_abs
    4. Calcule l'impact sur le résultat : impact = écart × sens
         • impact > 0 → favorable (plus de CA ou moins de charges)
         • impact < 0 → défavorable
    5. Attribue une priorité selon l'intensité de l'impact :
         Priorité 1 : |impact| ≥ 4 × seuil_abs  (critique)
         Priorité 2 : |impact| ≥ 2 × seuil_abs  (important)
         Priorité 3 : sinon                      (à surveiller)

    Paramètres
    ----------
    data              : DashboardData
    seuil_ecart_pct   : seuil minimum d'écart en % pour déclencher une alerte
                        Défaut : 5.0% — ajustable selon la maturité CDG du client
    seuil_ecart_abs   : seuil minimum d'écart en € pour déclencher une alerte
                        Défaut : 2 000€ — filtre les micro-comptes
    site_code         : None → tous sites | str → site spécifique
    classes_exclues   : classes analytiques à exclure de la détection
                        Défaut : ["Dotations", "IS et participation"]
                        Ces classes sont hors contrôle opérationnel immédiat

    Retourne
    --------
    list[Alerte]
        Triée par priorité croissante puis impact croissant (les pires en tête).
        Liste vide si aucune dérive matérielle n'est détectée.

    Exemple
    -------
    >>> alertes = compute_alertes(data, site_code="BGR", seuil_ecart_pct=3.0)
    >>> resume = summary_alertes(alertes)
    >>> print(f"{resume['critiques']} alertes critiques sur BGR")
    """
    classes_exclues = classes_exclues or ["Dotations", "IS et participation"]

    # Filtrer sur les mois réalisés uniquement
    df = data.df[
        (data.df["mois"] <= data.mois_reel) &
        (data.df["montant_reel"].notna())
    ].copy()

    if site_code:
        df = df[df["site_code"] == site_code]

    # Exclure les classes hors contrôle (dotations figées, IS calculé annuellement)
    df = df[~df["classe_cdg"].isin(classes_exclues)]

    # Agrégation YTD par site × compte
    agg = (
        df.groupby([
            "site_code", "site_libelle", "compte_code", "compte_libelle",
            "classe_cdg", "sous_classe", "sens",
        ])
        .agg(
            budget_ytd=("montant_budget", "sum"),
            reel_ytd  =("montant_reel",   "sum"),
        )
        .reset_index()
    )

    # Calcul des métriques d'alerte
    agg["ecart_abs"] = agg["reel_ytd"] - agg["budget_ytd"]
    agg["ecart_pct"] = np.where(
        agg["budget_ytd"].abs() > 1e-9,
        agg["ecart_abs"] / agg["budget_ytd"].abs() * 100,
        0.0,
    )
    # Impact sur le résultat : écart × sens
    # Positif = favorable, Négatif = défavorable
    agg["impact"]        = agg["ecart_abs"] * agg["sens"]
    agg["est_favorable"] = agg["impact"] > 0

    # Application du double critère de matérialité
    masque_materiel = (
        (agg["ecart_pct"].abs() >= seuil_ecart_pct) &
        (agg["ecart_abs"].abs() >= seuil_ecart_abs)
    )
    alertes_df = agg[masque_materiel].copy()

    # Attribution de la priorité selon l'intensité relative de l'impact
    def _priorite(ligne) -> int:
        intensite = abs(ligne["impact"]) / (seuil_ecart_abs + 1e-9)
        if intensite >= 4:
            return 1   # Critique : impact > 4× le seuil minimum
        elif intensite >= 2:
            return 2   # Important : impact entre 2× et 4× le seuil
        return 3       # À surveiller : juste au-dessus du seuil

    alertes_df["priorite"] = alertes_df.apply(_priorite, axis=1)

    # Tri : priorité croissante (1 en premier), puis impact croissant (pire en tête)
    alertes_df = alertes_df.sort_values(["priorite", "impact"])

    return [
        Alerte(
            site_code     = row["site_code"],
            site_libelle  = row["site_libelle"],
            compte_code   = row["compte_code"],
            compte_libelle= row["compte_libelle"],
            classe_cdg    = row["classe_cdg"],
            budget_ytd    = float(row["budget_ytd"]),
            reel_ytd      = float(row["reel_ytd"]),
            ecart_abs     = float(row["ecart_abs"]),
            ecart_pct     = float(row["ecart_pct"]),
            est_favorable = bool(row["est_favorable"]),
            priorite      = int(row["priorite"]),
        )
        for _, row in alertes_df.iterrows()
    ]


def compute_ranking(
    data      : DashboardData,
    kpi       : str = "REX",
    base      : str = "forecast",
    ascending : bool = False,
) -> pd.DataFrame:
    """
    Classe les sites selon un KPI et une base de comparaison.

    Paramètres
    ----------
    data      : DashboardData
    kpi       : KPI de classement — "CA_net" | "EBE" | "REX"
    base      : référence temporelle :
                  "forecast"      → projection fin d'année (hybride)
                  "ytd_reel"      → réel cumulé Jan → mois_reel
                  "budget_annuel" → budget annuel 12 mois (référence statique)
    ascending : True → du plus faible au plus fort (ex. tri pertes en tête)

    Retourne
    --------
    pd.DataFrame — 7 lignes (une par site)
        Colonnes : rang, site_code, site_libelle, departement, valeur, tx_pct
        valeur  : montant du KPI (€)
        tx_pct  : valeur / CA (même base) × 100 (%)

    Exemple
    -------
    >>> # Top 3 sites par REX forecast
    >>> top3 = compute_ranking(data, kpi="REX").head(3)
    >>> for _, row in top3.iterrows():
    ...     print(f"{row['rang']}. {row['site_libelle']} : {row['valeur']/1e3:.1f}K€")
    """
    att_df = compute_atterrissage_groupe(data)

    # Mapping (kpi, base) → colonne dans att_df
    col_map: Dict[Tuple[str, str], str] = {
        ("CA_net", "forecast")      : "ca_forecast",
        ("CA_net", "ytd_reel")      : "ca_ytd_reel",
        ("CA_net", "budget_annuel") : "ca_bgt",
        ("EBE",    "forecast")      : "ebe_forecast",
        ("EBE",    "ytd_reel")      : "ebe_ytd_reel",
        ("EBE",    "budget_annuel") : "ebe_bgt",
        ("REX",    "forecast")      : "rex_forecast",
        ("REX",    "ytd_reel")      : "rex_ytd_reel",
        ("REX",    "budget_annuel") : "rex_bgt",
    }
    col    = col_map.get((kpi, base), "rex_forecast")
    ca_col = col_map.get(("CA_net", base), "ca_forecast")

    df_rank = att_df.loc[data.sites, [col, ca_col]].copy()
    df_rank.index.name = "site_code"
    df_rank.columns = ["valeur", "ca"]
    df_rank["tx_pct"] = df_rank.apply(
        lambda r: _safe_div(r["valeur"], r["ca"]) * 100, axis=1
    )
    df_rank = df_rank.sort_values("valeur", ascending=ascending)
    df_rank["rang"] = range(1, len(df_rank) + 1)

    # Enrichissement avec les métadonnées site
    meta = data.df_sites.set_index("site_code")[["site_libelle", "departement"]]
    df_rank = df_rank.join(meta).reset_index()
    return df_rank[["rang", "site_code", "site_libelle", "departement", "valeur", "tx_pct"]]


def compute_contribution_reseau(
    data : DashboardData,
    kpi  : str = "CA_net",
    base : str = "forecast",
) -> pd.DataFrame:
    """
    Calcule la contribution de chaque site au total réseau (%).

    Utile pour les graphiques en anneau (donut chart) dans le tour de contrôle,
    permettant au DG de visualiser la répartition de l'activité.

    Paramètres
    ----------
    data : DashboardData
    kpi  : KPI de référence (défaut : "CA_net" pour la part de CA)
    base : "forecast" | "ytd_reel" | "budget_annuel"

    Retourne
    --------
    pd.DataFrame
        Colonnes : rang, site_code, site_libelle, departement, valeur,
                   tx_pct (% du KPI), contribution_pct (% du total réseau)
    """
    ranking = compute_ranking(data, kpi, base, ascending=False)
    total   = ranking["valeur"].sum()
    ranking["contribution_pct"] = (ranking["valeur"] / abs(total) * 100).round(1)
    return ranking


def compute_waterfall_mensuel(
    data      : DashboardData,
    site_code : str,
    mois      : int,
) -> pd.DataFrame:
    """
    Prépare les données pour le waterfall chart mensuel Budget → Réel.

    Le waterfall (graphique en cascade) est l'outil de diagnostic par excellence
    en CDG : il visualise comment chaque driver (classe de charges ou produits)
    contribue à l'écart entre le budget et le réel d'un mois.

    Structure du waterfall retourné
    ─────────────────────────────────
    Ligne 1 : "BUDGET" — point de départ (total budget du mois)
    Lignes 2–N : une ligne par classe CDG non nulle (contribution à l'écart)
    Ligne N+1 : "RÉEL" — total réel du mois

    La contribution est positive si la classe améliore le résultat,
    négative si elle le dégrade.

    Paramètres
    ----------
    data      : DashboardData
    site_code : code site à analyser (ex. "LYO_E")
    mois      : mois cible (doit être ≤ mois_reel pour avoir un réel)

    Retourne
    --------
    pd.DataFrame
        Colonnes : classe_cdg, ordre_classe, budget, reel, contribution, type
        type ∈ {"budget_initial", "driver", "total_reel"}

    Exemple
    -------
    >>> wf = compute_waterfall_mensuel(data, "LYO_E", mois=3)
    >>> # Révèle que l'écart de -5K€ vient principalement de la ligne "Achats"
    >>> # (problème fournisseur — diagnostic immédiat)
    """
    df_ = data.df[
        (data.df["site_code"] == site_code) &
        (data.df["mois"] == mois) &
        (data.df["montant_reel"].notna())
    ].copy()

    # Agrégation par classe
    drivers = (
        df_
        .groupby(["classe_cdg", "ordre_classe"])
        .agg(budget=("montant_budget", "sum"), reel=("montant_reel", "sum"))
        .reset_index()
        .sort_values("ordre_classe")
    )
    drivers["contribution"] = drivers["reel"] - drivers["budget"]

    total_bgt = float(drivers["budget"].sum())
    total_rel = float(drivers["reel"].sum())

    # Construction du DataFrame waterfall avec lignes encadrantes
    lignes = [
        # Ligne de départ : niveau budget total du mois
        {"classe_cdg": "BUDGET", "budget": total_bgt,
         "reel": total_bgt, "contribution": 0.0,
         "type": "budget_initial", "ordre_classe": -1},
    ]
    for _, ligne in drivers.iterrows():
        lignes.append({**ligne.to_dict(), "type": "driver"})
    # Ligne d'arrivée : niveau réel total du mois
    lignes.append({
        "classe_cdg": "RÉEL", "budget": total_rel,
        "reel": total_rel, "contribution": total_rel - total_bgt,
        "type": "total_reel", "ordre_classe": 999,
    })

    return pd.DataFrame(lignes)


def compute_evolution_mensuelle(
    data      : DashboardData,
    site_code : Optional[str] = None,
    kpi       : str = "CA_net",
) -> pd.DataFrame:
    """
    Série mensuelle budget vs réel pour un KPI donné.

    C'est la base de données des graphiques de courbes comparatifs
    sur l'écran 2 (drill-down site).

    Paramètres
    ----------
    data      : DashboardData
    site_code : None → consolidé réseau | str → site spécifique
    kpi       : KPI SIG à extraire — "CA_net" | "MC" | "EBE" | "REX" | "RCAI" | "RN"

    Retourne
    --------
    pd.DataFrame — 12 lignes (une par mois), trié par mois croissant
        Colonnes : site_code, mois, kpi, budget, reel, ecart, ecart_pct,
                   mois_label, est_realise

    Exemple
    -------
    >>> evol = compute_evolution_mensuelle(data, site_code="VLF", kpi="EBE")
    >>> # → 12 lignes avec budget et réel mensuel de l'EBE VLF
    >>> # → reel = NaN pour les mois 5–12 (non réalisés)
    """
    df_m = data.sig_mensuel[data.sig_mensuel["kpi"] == kpi].copy()

    if site_code:
        df_m = df_m[df_m["site_code"] == site_code]
    else:
        # Consolidation : somme tous les sites par mois
        df_m = (
            df_m.groupby("mois")
            .agg(budget=("budget","sum"), reel=("reel","sum"), ecart=("ecart","sum"))
            .reset_index()
        )
        df_m["site_code"] = "consolidé"

    df_m["mois_label"] = df_m["mois"].map(MOIS_LABELS)
    budget_abs = df_m["budget"].replace(0, np.nan).abs()
    df_m["ecart_pct"] = ((df_m["reel"] - df_m["budget"]) / budget_abs * 100).round(1)
    df_m["est_realise"] = df_m["reel"].notna()

    return df_m.sort_values("mois").reset_index(drop=True)


def summary_alertes(alertes: List[Alerte]) -> Dict:
    """
    Produit un résumé synthétique d'une liste d'alertes.

    Utile pour l'affichage dans les badges et compteurs du dashboard
    (ex. "3 alertes critiques · 2 sites concernés").

    Paramètres
    ----------
    alertes : liste produite par compute_alertes()

    Retourne
    --------
    dict avec clés :
      "total"          : nombre total d'alertes
      "critiques"      : alertes priorité 1
      "importantes"    : alertes priorité 2
      "surveillance"   : alertes priorité 3
      "favorables"     : alertes avec impact positif (bonnes surprises)
      "defavorables"   : alertes avec impact négatif (dérives)
      "sites_en_alerte": liste des codes sites avec au moins une alerte défavorable

    Exemple
    -------
    >>> alertes = compute_alertes(data)
    >>> resume = summary_alertes(alertes)
    >>> badge = f"🔴 {resume['critiques']} | ⚠️ {resume['importantes']}"
    """
    if not alertes:
        return {
            "total": 0, "critiques": 0, "importantes": 0, "surveillance": 0,
            "favorables": 0, "defavorables": 0, "sites_en_alerte": [],
        }
    return {
        "total"          : len(alertes),
        "critiques"      : sum(1 for a in alertes if a.priorite == 1),
        "importantes"    : sum(1 for a in alertes if a.priorite == 2),
        "surveillance"   : sum(1 for a in alertes if a.priorite == 3),
        "favorables"     : sum(1 for a in alertes if a.est_favorable),
        "defavorables"   : sum(1 for a in alertes if not a.est_favorable),
        "sites_en_alerte": list({a.site_code for a in alertes if not a.est_favorable}),
    }


# ══════════════════════════════════════════════════════════════════════════════
# EXÉCUTION DIRECTE
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    from loader import load_data

    chemin = sys.argv[1] if len(sys.argv) > 1 else "data/sample_budget_v2.xlsx"
    data   = load_data(chemin)

    print("\n" + "═"*70)
    print("KPI STRIP — Consolidé réseau")
    print("═"*70)
    kpi = compute_kpi_strip(data)
    print(f"  CA     : {kpi.ca_ytd_reel/1e3:.1f}K€ réel | {kpi.ca_ytd_budget/1e3:.1f}K€ budget | {kpi.ca_ecart_pct:+.1f}%")
    print(f"           Atterrissage {kpi.ca_atterrissage/1e3:.0f}K€ (budget annuel {kpi.ca_annuel_bgt/1e3:.0f}K€)")
    print(f"  EBE    : {kpi.ebe_ytd_reel/1e3:.1f}K€ ({kpi.tx_ebe_reel:.1f}%) | att. {kpi.ebe_atterrissage/1e3:.0f}K€")
    print(f"  REX    : {kpi.rex_ytd_reel/1e3:.1f}K€ ({kpi.tx_rex_reel:.1f}%) | att. {kpi.rex_atterrissage/1e3:.0f}K€")

    print("\n" + "─"*70)
    print("ATTERRISSAGE PAR SITE (K€)")
    att_df = compute_atterrissage_groupe(data)
    cols   = ["ca_forecast","ca_ecart_bgt","ebe_forecast","tx_ebe_forecast","rex_forecast","tx_rex_forecast"]
    print((att_df[cols] / [1e3,1e3,1e3,1,1e3,1]).round(1).to_string())

    print("\n" + "─"*70)
    print("ALERTES (seuil 5% / 2 000€)")
    alertes = compute_alertes(data)
    resume  = summary_alertes(alertes)
    print(f"  {resume['total']} alertes | 🔴 {resume['critiques']} critiques | "
          f"{resume['defavorables']} défavorables | Sites : {resume['sites_en_alerte']}")
    for a in alertes[:5]:
        flag = "✅" if a.est_favorable else "🔴"
        print(f"  {flag}[P{a.priorite}] {a.site_code} | {a.compte_libelle[:42]:42s} | "
              f"{a.ecart_abs/1e3:+.1f}K€ ({a.ecart_pct:+.1f}%)")

    print("\n" + "─"*70)
    print("RANKING REX (forecast)")
    rank = compute_ranking(data, "REX", "forecast")
    print(rank.to_string(index=False))
