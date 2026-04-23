"""
core/forecast.py
══════════════════════════════════════════════════════════════════════════════
FloMind Budget Dashboard — Module Rolling Forecast

RÔLE DANS L'ARCHITECTURE
─────────────────────────
Ce module répond à la question centrale du DG réseau :
  "Si on continue comme ça, on finit où en décembre ?"

Il produit des projections mensuelles et annuelles avec des bandes
de confiance (P10/P50/P90) pour tout KPI SIG, tout site, toute méthode.

DIFFÉRENCIATEUR COMMERCIAL FLOMIND
────────────────────────────────────
Excel et Power BI affichent uniquement budget vs réel (diagnostic passé).
L'écran 4 du dashboard FloMind affiche :
  • Le réel YTD (où on en est)
  • Le budget annuel (l'objectif)
  • Le forecast rolling P50 (où on va finir)
  • La bande P10–P90 (l'incertitude de la projection)
  • Les deux références simultanément : budget ET forecast rolling

Ce double référentiel permet d'agir en avance de phase, avant que
le problème soit entièrement consommé.

TROIS MÉTHODES DE FORECAST
────────────────────────────
  "budget"   → Baseline : réel YTD + budget restant tel quel
               Simple, prudent, ne capte pas les tendances
               Utilisé comme référence (ligne pointillée)

  "tendance" → Ratio : applique le ratio réel/budget YTD aux mois restants
               Hypothèse : "si on continue comme ça"
               Lisible pour un DG, stable avec peu de points
               Recommandé pour les présentations Codir

  "wls"      → Weighted Least Squares : régression linéaire sur les réalisés
               Les mois récents ont plus de poids (decay exponentiel)
               Capte les inflexions récentes, instable en début d'année
               Utile à partir de mois 6–8

  "hybride"  → Combinaison pondérée tendance + WLS
               Pondération dynamique selon le mois courant :
                 mois ≤ 3 : 75% tendance + 25% WLS (peu de données)
                 mois 4–6 : 55% tendance + 45% WLS
                 mois ≥ 7 : 45% tendance + 55% WLS (WLS devient fiable)
               RECOMMANDÉ — équilibre robustesse et réactivité

BANDES DE CONFIANCE (P10/P90)
───────────────────────────────
Méthode bootstrap sur les résidus historiques :
  1. Calcule les résidus passés : (réel - budget) / |budget| par mois réalisé
  2. Tire N=1000 échantillons de résidus avec remise (bootstrap)
  3. Applique chaque échantillon au forecast P50
  4. Extrait les percentiles 10 et 90

Interprétation :
  P10 : atterrissage dans le scénario pessimiste (1 chance sur 10 de faire pire)
  P90 : atterrissage dans le scénario optimiste (1 chance sur 10 de faire mieux)
  Bande P10-P90 étroite → faible volatilité historique (site stable)
  Bande P10-P90 large   → forte volatilité (site imprévisible, attention)

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
# CONSTANTES
# ══════════════════════════════════════════════════════════════════════════════

# Labels courts des mois pour les graphiques
MOIS_LABELS: Dict[int, str] = {
    1:"Jan", 2:"Fév", 3:"Mar", 4:"Avr", 5:"Mai", 6:"Jun",
    7:"Jul", 8:"Aoû", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Déc",
}

# Décroissance exponentielle des poids WLS
# decay = 0.75 → le mois le plus récent a un poids (0.75^0 = 1.0),
#                 le précédent 0.75, l'avant-précédent 0.75² = 0.56, etc.
# Plus decay est élevé (proche de 1), plus les poids sont équilibrés.
# Plus decay est faible (proche de 0), plus on sur-pondère le dernier mois.
WLS_DECAY: float = 0.75

# Poids par défaut méthode hybride (pour mois_reel entre 4 et 6)
HYBRIDE_W_TENDANCE: float = 0.55
HYBRIDE_W_WLS     : float = 0.45

# Simulations Monte Carlo pour les bandes de confiance
# 1 000 simulations → bon équilibre précision / temps de calcul
# Augmenter à 5 000–10 000 pour des exports PDF haute précision
N_BOOTSTRAP   : int = 1_000
BOOTSTRAP_SEED: int = 42   # Seed fixé pour reproductibilité


# ══════════════════════════════════════════════════════════════════════════════
# DATACLASS DE SORTIE
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ForecastResult:
    """
    Résultat complet d'un rolling forecast pour un (site, KPI, méthode).

    Structure duale : séries mensuelles + agrégats annuels.

    Séries mensuelles (longueur 12)
    ─────────────────────────────────
    Pour chaque mois de 1 à 12, une valeur dans chaque série.

    budget       : Budget original mensuel (identique à data.sig_mensuel)
    reel         : Réel mensuel. None (pas NaN) pour les mois non réalisés.
                   Convention Python None plutôt que NaN pour la compatibilité
                   avec les sérialiseurs JSON (Plotly, export).
    forecast_p50 : Point central du forecast.
                   Pour les mois réalisés : identique au réel (≡ historique).
                   Pour les mois futurs   : projection selon la méthode choisie.
    forecast_p10 : Borne basse (10e percentile) — scenario pessimiste.
                   Pour les mois réalisés : identique au réel (pas d'incertitude).
    forecast_p90 : Borne haute (90e percentile) — scenario optimiste.
    is_forecast  : True si le mois est projeté (futur), False si réalisé.

    Agrégats annuels
    ─────────────────
    total_budget    : Somme des budgets mensuels (12 mois)
    total_reel_ytd  : Somme des réels (Jan → mois_reel seulement)
    total_forecast  : total_reel_ytd + somme(forecast_p50[mois_reel:])
                      → Projection de clôture d'exercice (scénario central)
    total_p10       : Borne basse annuelle (bootstrap)
    total_p90       : Borne haute annuelle (bootstrap)
    ecart_vs_budget : total_forecast - total_budget (€)
    ecart_pct       : (total_forecast - total_budget) / |total_budget| × 100 (%)

    Attributs méta
    ──────────────
    site_code : code site
    kpi       : KPI projeté ("CA_net", "EBE", etc.)
    methode   : méthode utilisée ("budget", "tendance", "wls", "hybride")
    mois_reel : dernier mois réalisé au moment du calcul
    annee     : exercice fiscal

    Exemple d'utilisation
    ──────────────────────
    >>> r = rolling_forecast(data, "LYO_C", "REX", "hybride")
    >>> print(f"Forecast REX LYO_C : {r.total_forecast/1e3:.1f}K€")
    >>> print(f"Incertitude : [{r.total_p10/1e3:.1f} ; {r.total_p90/1e3:.1f}]K€")
    >>> df = forecast_to_dataframe(r)  # → DataFrame 12 lignes pour Plotly
    """
    site_code      : str
    kpi            : str
    methode        : str
    mois_reel      : int
    annee          : int
    # Séries mensuelles
    mois           : List[int]
    mois_labels    : List[str]
    budget         : List[float]
    reel           : List[Optional[float]]   # None pour mois non réalisés
    forecast_p50   : List[float]
    forecast_p10   : List[float]
    forecast_p90   : List[float]
    is_forecast    : List[bool]
    # Agrégats annuels
    total_budget   : float
    total_reel_ytd : float
    total_forecast : float
    total_p10      : float
    total_p90      : float
    ecart_vs_budget: float
    ecart_pct      : float


# ══════════════════════════════════════════════════════════════════════════════
# PRÉPARATION DES DONNÉES
# ══════════════════════════════════════════════════════════════════════════════

def _get_series(
    data      : DashboardData,
    site_code : str,
    kpi       : str,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Extrait les séries mensuelles budget et réel pour un (site, KPI).

    Paramètres
    ----------
    data      : DashboardData
    site_code : code site (ex. "LYO_C")
    kpi       : KPI SIG (ex. "CA_net", "EBE", "REX")

    Retourne
    --------
    budget : np.ndarray shape (12,) — valeurs budget mensuelles
    reel   : np.ndarray shape (12,) — valeurs réelles (NaN si non réalisé)

    Lève
    ----
    ValueError si le site/KPI ne produit pas exactement 12 mois.
    """
    df_m = (
        data.sig_mensuel[
            (data.sig_mensuel["site_code"] == site_code) &
            (data.sig_mensuel["kpi"] == kpi)
        ]
        .sort_values("mois")
    )

    if len(df_m) != 12:
        raise ValueError(
            f"Données incomplètes : {site_code}/{kpi} → {len(df_m)} mois "
            f"(attendu 12). Vérifiez que le générateur a produit 12 mois."
        )

    return df_m["budget"].values.astype(float), df_m["reel"].values.astype(float)


# ══════════════════════════════════════════════════════════════════════════════
# MÉTHODES DE FORECAST (fonctions pures)
# ══════════════════════════════════════════════════════════════════════════════

def _forecast_budget(
    budget    : np.ndarray,
    reel      : np.ndarray,
    mois_reel : int,
) -> np.ndarray:
    """
    Méthode "budget" — ligne de base de référence.

    Algorithme
    ----------
    Pour les mois réalisés (1 → mois_reel) : utilise le réel.
    Pour les mois futurs (mois_reel+1 → 12)  : utilise le budget tel quel.

    Interprétation
    --------------
    "Si on suppose que le reste de l'année se déroule exactement comme prévu."
    C'est la méthode la plus optimiste pour un site en sous-performance.
    Utile comme borne supérieure dans l'affichage comparatif.

    Paramètres
    ----------
    budget    : budget mensuel (12 valeurs)
    reel      : réel mensuel (NaN pour les mois futurs)
    mois_reel : nombre de mois réalisés

    Retourne
    --------
    np.ndarray shape (12,) — forecast P50 "budget"
    """
    f = reel.copy()
    f[mois_reel:] = budget[mois_reel:]
    return f


def _forecast_tendance(
    budget    : np.ndarray,
    reel      : np.ndarray,
    mois_reel : int,
) -> np.ndarray:
    """
    Méthode "tendance" — ratio YTD appliqué au budget restant.

    Algorithme
    ----------
    1. ratio = Σ réel(1..n) / Σ budget(1..n)
    2. Pour chaque mois futur m : forecast(m) = budget(m) × ratio

    Hypothèse clé
    -------------
    La dynamique observée (sur/sous-performance) est persistante.
    "Si on continue au même rythme relatif que le YTD."

    Exemple
    -------
    Site BGR : réel YTD = 134.6K€, budget YTD = 147.6K€
    ratio = 0.912 (−8.8%)
    → Chaque mois restant est réduit de 8.8% par rapport au budget
    → Atterrissage conservateur, cohérent avec la tendance observée

    Avantages / Limites
    --------------------
    + Très lisible pour un DG ("on reproduit la tendance actuelle")
    + Stable avec peu de points (robuste en début d'année)
    - Ne capte pas les inflexions (si le problème s'aggrave ou se résout)
    - Sensible aux mois exceptionnels non récurrents (ex. fermeture site)

    Paramètres
    ----------
    budget    : budget mensuel (12 valeurs)
    reel      : réel mensuel (NaN pour les mois futurs)
    mois_reel : nombre de mois réalisés

    Retourne
    --------
    np.ndarray shape (12,) — forecast P50 "tendance"
    """
    ytd_bgt = np.sum(budget[:mois_reel])
    ytd_rel = np.nansum(reel[:mois_reel])

    # Protection contre la division par zéro
    ratio = ytd_rel / ytd_bgt if abs(ytd_bgt) > 1e-9 else 1.0

    f = reel.copy()
    f[mois_reel:] = budget[mois_reel:] * ratio
    return f


def _forecast_wls(
    budget    : np.ndarray,
    reel      : np.ndarray,
    mois_reel : int,
    decay     : float = WLS_DECAY,
) -> np.ndarray:
    """
    Méthode "wls" — régression linéaire pondérée sur les réalisés.

    Algorithme WLS (Weighted Least Squares)
    ─────────────────────────────────────────
    1. Construit la matrice X = [1, mois] pour les mois réalisés
    2. Applique des poids décroissants : w_i = decay^(n-1-i)
       Le mois le plus récent a le poids maximal (1.0)
    3. Résout β = (XᵀWX)⁻¹ XᵀWy (régression linéaire pondérée)
       via np.linalg.lstsq (stable numériquement)
    4. Projette la droite de tendance sur les mois futurs
    5. Applique la saisonnalité du budget sur la valeur projetée
       (évite une extrapolation linéaire brute qui ignore la saisonnalité)

    Gestion de l'instabilité
    ─────────────────────────
    Avec seulement 3–4 points de données, la régression linéaire peut
    produire des extrapolations aberrantes (pentes très fortes sur un outlier).
    Mesures de protection :
    • Fallback sur _forecast_tendance() si np.linalg.LinAlgError
    • Saisonnalisation par le budget : limite l'amplitude des projections
    • Dans l'hybride, WLS ne représente que 25–45% du forecast final

    Paramètres
    ----------
    budget    : budget mensuel (12 valeurs)
    reel      : réel mensuel (NaN pour les mois futurs)
    mois_reel : nombre de mois réalisés
    decay     : facteur de décroissance des poids (défaut : 0.75)
                0.5 = pondération très agressive (quasi-dernier mois seulement)
                0.9 = pondération quasi-uniforme (tous les mois similaires)

    Retourne
    --------
    np.ndarray shape (12,) — forecast P50 "wls"
    """
    n = mois_reel
    x = np.arange(1, n + 1, dtype=float)   # indices de mois (1, 2, 3, 4)
    y = reel[:n]                             # réels observés

    # Poids WLS : mois le plus récent = 1.0, mois le plus ancien = decay^(n-1)
    # Ex. avec n=4, decay=0.75 : w = [0.75^3, 0.75^2, 0.75, 1.0] = [0.42, 0.56, 0.75, 1.0]
    w = np.array([decay ** (n - 1 - i) for i in range(n)])

    # Matrice X augmentée : [intercept, pente]
    X = np.column_stack([np.ones(n), x])
    W = np.diag(w)   # matrice diagonale des poids

    try:
        # β = (XᵀWX)⁻¹ XᵀWy — résolution via lstsq (stable vs inversion directe)
        XtW  = X.T @ W
        beta = np.linalg.lstsq(XtW @ X, XtW @ y, rcond=None)[0]
        intercept, slope = beta
    except np.linalg.LinAlgError:
        # Matrice singulière (ex. tous les réels identiques) → fallback tendance
        return _forecast_tendance(budget, reel, mois_reel)

    # Projections brutes par la droite de tendance
    x_future     = np.arange(n + 1, 13, dtype=float)
    trend_future = intercept + slope * x_future

    # Application de la saisonnalité du budget
    # Idée : budget(m) / moyenne(budget futurs) = ratio de saisonnalité du mois m
    # On applique ce ratio à la valeur moyenne projetée par la tendance
    budget_future = budget[mois_reel:]
    moy_budget_future = np.mean(budget_future) if len(budget_future) > 0 else 1.0

    if abs(moy_budget_future) > 1e-9:
        saison_ratio  = budget_future / moy_budget_future
        moy_tendance  = np.mean(trend_future) if len(trend_future) > 0 else 0.0
        wls_future    = moy_tendance * saison_ratio
    else:
        # Budget futur nul (ex. nouveau site sans budget sur certains mois)
        wls_future = trend_future

    f = reel.copy()
    f[mois_reel:] = wls_future
    return f


def _forecast_hybride(
    budget        : np.ndarray,
    reel          : np.ndarray,
    mois_reel     : int,
    w_tendance    : float = HYBRIDE_W_TENDANCE,
    w_wls         : float = HYBRIDE_W_WLS,
    decay         : float = WLS_DECAY,
) -> np.ndarray:
    """
    Méthode "hybride" — combinaison pondérée tendance + WLS. RECOMMANDÉE.

    Pondération dynamique selon la maturité des données
    ─────────────────────────────────────────────────────
    En début d'année, peu de points → WLS instable → on sur-pondère tendance.
    En fin d'année, beaucoup de points → WLS fiable → on augmente son poids.

    Table des poids dynamiques :
      mois_reel ≤ 3 : 75% tendance + 25% WLS  (Q1 : données limitées)
      mois_reel 4–6 : 55% tendance + 45% WLS  (poids défaut — configuration actuelle)
      mois_reel ≥ 7 : 45% tendance + 55% WLS  (WLS devient dominant en fin d'année)

    Cette adaptation dynamique évite d'avoir à reconfigurer la méthode
    manuellement selon le mois de l'exercice.

    Paramètres
    ----------
    budget        : budget mensuel (12 valeurs)
    reel          : réel mensuel (NaN pour les mois futurs)
    mois_reel     : nombre de mois réalisés
    w_tendance    : poids tendance (défaut : 0.55 pour mois 4–6)
    w_wls         : poids WLS (défaut : 0.45 pour mois 4–6)
    decay         : facteur WLS (transmis à _forecast_wls)

    Retourne
    --------
    np.ndarray shape (12,) — forecast P50 "hybride"
    """
    # Ajustement dynamique des poids selon la disponibilité des données
    if mois_reel <= 3:
        # Début d'exercice : WLS instable avec < 4 points
        w_t, w_w = 0.75, 0.25
    elif mois_reel <= 6:
        # Milieu d'exercice : équilibre raisonnable (paramétrage par défaut)
        w_t, w_w = w_tendance, w_wls
    else:
        # Fin d'exercice : WLS devient le plus fiable avec beaucoup de données
        w_t, w_w = 0.45, 0.55

    f_tendance = _forecast_tendance(budget, reel, mois_reel)
    f_wls      = _forecast_wls(budget, reel, mois_reel, decay)

    # Combinaison linéaire des deux forecasts pour les mois futurs uniquement
    # Les mois réalisés conservent le réel (pas d'interpolation sur le passé)
    f = reel.copy()
    f[mois_reel:] = w_t * f_tendance[mois_reel:] + w_w * f_wls[mois_reel:]
    return f


# ══════════════════════════════════════════════════════════════════════════════
# BANDES DE CONFIANCE — BOOTSTRAP
# ══════════════════════════════════════════════════════════════════════════════

def _compute_bands_bootstrap(
    budget        : np.ndarray,
    reel          : np.ndarray,
    point_forecast: np.ndarray,
    mois_reel     : int,
    n_sim         : int = N_BOOTSTRAP,
    seed          : int = BOOTSTRAP_SEED,
) -> Tuple[np.ndarray, np.ndarray, float, float]:
    """
    Estime les bandes P10/P90 via bootstrap sur les résidus historiques.

    Modèle d'incertitude
    ─────────────────────
    Hypothèse : les erreurs futures suivent la même distribution
    que les erreurs passées, exprimées en pourcentage du budget.

    Étapes :
    1. Calcule les résidus historiques : r_i = (réel_i - budget_i) / |budget_i|
       pour chaque mois réalisé i ∈ [1, mois_reel].
    2. Pour chaque simulation k ∈ [1, n_sim] :
       a. Tire n_restants résidus avec remise dans {r_i}
       b. Applique les résidus tirés au forecast P50 :
          sim_future_k[m] = forecast_p50[m] × (1 + résidu_tiré_k[m])
       c. Calcule le total annuel simulé :
          total_k = Σ réel[1..mois_reel] + Σ sim_future_k
    3. Extrait les percentiles 10 et 90 des totaux simulés.

    Gestion des cas dégénérés
    ──────────────────────────
    Si moins de 2 résidus disponibles (ex. mois 1 ou 2) :
      → Utilise une distribution synthétique ±10% (hypothèse conservatrice)
    Si n_restants = 0 (exercice complet) :
      → Retourne des tableaux vides et les totaux réels

    Paramètres
    ----------
    budget         : budget mensuel (12 valeurs)
    reel           : réel mensuel (NaN pour mois futurs)
    point_forecast : forecast P50 (12 valeurs, réel pour mois passés)
    mois_reel      : nombre de mois réalisés
    n_sim          : nombre de simulations bootstrap (défaut : 1 000)
    seed           : graine aléatoire pour la reproductibilité

    Retourne
    --------
    p10_mensuel : np.ndarray shape (12 - mois_reel,) — bande basse mensuelle
    p90_mensuel : np.ndarray shape (12 - mois_reel,) — bande haute mensuelle
    total_p10   : float — atterrissage annuel pessimiste (P10)
    total_p90   : float — atterrissage annuel optimiste (P90)
    """
    n_restants = 12 - mois_reel

    # Cas : exercice terminé — pas de mois à projeter
    if n_restants == 0:
        return np.array([]), np.array([]), np.array([]), 0.0, 0.0, 0.0

    # Calcul des résidus historiques (en % du budget)
    residus_pct = []
    for i in range(mois_reel):
        if abs(budget[i]) > 1e-9 and not np.isnan(reel[i]):
            residus_pct.append((reel[i] - budget[i]) / abs(budget[i]))

    if len(residus_pct) < 2:
        # Pas assez de données → distribution synthétique ±10%
        # Couvre les cas très début d'année sans historique suffisant
        residus_pct = [-0.10, -0.05, 0.0, 0.05, 0.10]

    residus_arr = np.array(residus_pct)
    rng = np.random.default_rng(seed)

    # Simulations Monte Carlo
    monthly_sims = np.zeros((n_sim, n_restants))
    ytd_cumul    = float(np.nansum(reel[:mois_reel]))

    for sim in range(n_sim):
        # Tirage avec remise : n_restants résidus indépendants
        residus_tires  = rng.choice(residus_arr, size=n_restants, replace=True)
        # Application au forecast P50 de chaque mois futur
        sim_future     = point_forecast[mois_reel:] * (1.0 + residus_tires)
        monthly_sims[sim] = sim_future

    # Percentiles mensuels (axe 0 = simulations)
    # P10 ≤ P50 ≤ P90 garanti par construction (même distribution bootstrap)
    p10_mensuel = np.percentile(monthly_sims, 10, axis=0)
    p50_mensuel = np.percentile(monthly_sims, 50, axis=0)  # médiane bootstrap
    p90_mensuel = np.percentile(monthly_sims, 90, axis=0)

    # Totaux annuels simulés : YTD réel + reste simulé
    totaux    = ytd_cumul + monthly_sims.sum(axis=1)
    total_p10 = float(np.percentile(totaux, 10))
    total_p50 = float(np.percentile(totaux, 50))
    total_p90 = float(np.percentile(totaux, 90))

    return p10_mensuel, p50_mensuel, p90_mensuel, total_p10, total_p50, total_p90


# ══════════════════════════════════════════════════════════════════════════════
# API PUBLIQUE
# ══════════════════════════════════════════════════════════════════════════════

def rolling_forecast(
    data      : DashboardData,
    site_code : str,
    kpi       : str  = "CA_net",
    methode   : str  = "hybride",
    n_sim     : int  = N_BOOTSTRAP,
) -> ForecastResult:
    """
    Calcule le rolling forecast complet pour un (site, KPI).

    C'est la fonction principale du module. Elle orchestre :
    1. L'extraction des séries mensuelles
    2. Le calcul du point forecast selon la méthode choisie
    3. Le calcul des bandes de confiance P10/P90 (bootstrap)
    4. La construction du ForecastResult

    Paramètres
    ----------
    data      : DashboardData issu de load_data()
    site_code : code site — "LYO_C" | "LYO_E" | "VLF" | "MCN" | "BGR" | "CLM" | "ANC"
    kpi       : KPI à projeter — "CA_net" | "MC" | "VA" | "EBE" | "REX" | "RCAI" | "RN"
    methode   : méthode de forecast :
                  "budget"   → baseline budget pur
                  "tendance" → ratio YTD
                  "wls"      → régression WLS
                  "hybride"  → combinaison pondérée (RECOMMANDÉ)
    n_sim     : nombre de simulations bootstrap pour P10/P90 (défaut : 1 000)

    Retourne
    --------
    ForecastResult
        Voir la documentation de ForecastResult pour le détail.

    Lève
    ----
    ValueError si methode n'est pas dans {"budget", "tendance", "wls", "hybride"}
    ValueError si site_code/kpi ne produit pas 12 mois dans data.sig_mensuel

    Exemple
    -------
    >>> r = rolling_forecast(data, "LYO_C", "REX", "hybride")
    >>> print(f"REX forecast : {r.total_forecast/1e3:.1f}K€")
    >>> print(f"Budget       : {r.total_budget/1e3:.1f}K€")
    >>> print(f"Écart        : {r.ecart_pct:+.1f}%")
    >>> df = forecast_to_dataframe(r)   # → prêt pour Plotly
    """
    mr = data.mois_reel
    budget, reel = _get_series(data, site_code, kpi)

    # ── Dispatch vers la méthode de forecast choisie ──────────────────────────
    METHODES = {
        "budget"  : _forecast_budget,
        "tendance": _forecast_tendance,
        "wls"     : _forecast_wls,
        "hybride" : _forecast_hybride,
    }
    if methode not in METHODES:
        raise ValueError(
            f"Méthode inconnue : '{methode}'. "
            f"Valeurs autorisées : {list(METHODES.keys())}"
        )

    f_p50 = METHODES[methode](budget, reel, mr)

    # ── Bandes de confiance P10/P90 ───────────────────────────────────────────
    # Bootstrap : on passe le forecast déterministe comme ancre de simulation
    # mais on expose le percentile 50 des simulations comme P50 affiché.
    # Cela garantit P10 ≤ P50 ≤ P90 par construction (même distribution).
    f_det = f_p50.copy()   # forecast déterministe conservé en interne
    p10_m, p50_m, p90_m, total_p10, total_p50, total_p90 = _compute_bands_bootstrap(
        budget, reel, f_det, mr, n_sim=n_sim
    )

    # Construction des séries sur 12 mois
    # Mois réalisés : P10 = P50 = P90 = réel (certitude totale)
    # Mois futurs   : percentiles issus du bootstrap
    f_p10 = f_det.copy()
    f_p50 = f_det.copy()
    f_p90 = f_det.copy()
    if len(p50_m) > 0:
        f_p10[mr:] = p10_m
        f_p50[mr:] = p50_m   # médiane bootstrap, pas le forecast déterministe
        f_p90[mr:] = p90_m

    # ── Agrégats annuels ──────────────────────────────────────────────────────
    ytd_reel   = float(np.nansum(reel[:mr]))
    total_bgt  = float(np.sum(budget))
    # total_forecast = P50(Σ scénarios) — médiane de la distribution des totaux annuels
    # IMPORTANT : Σ P50_mensuel ≠ P50(Σ mois) → on utilise total_p50 du bootstrap
    # pour garantir total_p10 ≤ total_forecast ≤ total_p90 par construction
    # len(p50_m) > 0 = il y a des mois futurs (n_restants > 0)
    # total_p50 peut être négatif (EBE/REX en perte) → pas de condition sur le signe
    total_fc = total_p50 if len(p50_m) > 0 else float(ytd_reel)

    ecart_pct  = (
        (total_fc - total_bgt) / abs(total_bgt) * 100
        if abs(total_bgt) > 1e-9 else 0.0
    )

    # Exercice complet (n_restants=0) : P10=P50=P90=réel (pas d'incertitude)
    if total_p10 == 0.0 and total_p50 == 0.0 and total_p90 == 0.0:
        total_p10 = total_fc
        total_p50 = total_fc
        total_p90 = total_fc

    return ForecastResult(
        site_code      = site_code,
        kpi            = kpi,
        methode        = methode,
        mois_reel      = mr,
        annee          = data.annee,
        # Séries mensuelles
        mois           = list(range(1, 13)),
        mois_labels    = [MOIS_LABELS[m] for m in range(1, 13)],
        budget         = budget.tolist(),
        reel           = [float(v) if not np.isnan(v) else None for v in reel],
        forecast_p50   = f_p50.tolist(),
        forecast_p10   = f_p10.tolist(),
        forecast_p90   = f_p90.tolist(),
        is_forecast    = [m > mr for m in range(1, 13)],
        # Agrégats annuels
        total_budget   = total_bgt,
        total_reel_ytd = ytd_reel,
        total_forecast = total_fc,
        total_p10      = total_p10,
        total_p90      = total_p90,
        ecart_vs_budget= total_fc - total_bgt,
        ecart_pct      = ecart_pct,
    )


def forecast_to_dataframe(result: ForecastResult) -> pd.DataFrame:
    """
    Convertit un ForecastResult en DataFrame 12 lignes prêt pour Plotly.

    Paramètres
    ----------
    result : ForecastResult produit par rolling_forecast()

    Retourne
    --------
    pd.DataFrame — 12 lignes (une par mois)
        Colonnes :
          mois, mois_label  : identifiant temporel
          budget            : budget mensuel
          reel              : réel mensuel (NaN si non réalisé)
          forecast_p50      : point forecast (= réel si réalisé)
          forecast_p10      : borne basse (= réel si réalisé)
          forecast_p90      : borne haute (= réel si réalisé)
          is_forecast       : True si mois projeté
          valeur_active     : réel si réalisé, forecast_p50 sinon
                              → courbe continue pour le graphique Plotly
          ecart_budget      : valeur_active - budget (€)
          ecart_budget_pct  : (valeur_active - budget) / |budget| × 100 (%)

    Notes Plotly
    ─────────────
    Pour tracer le graphique forecast :
      • Ligne budget      : px.line(df, x="mois_label", y="budget")
      • Ligne active      : px.line(df, x="mois_label", y="valeur_active")
      • Bande P10-P90     : go.Scatter fill="tonexty" sur forecast_p10 et forecast_p90
      • Zone forecast     : filter df[df["is_forecast"]]
      • Zone réalisé      : filter df[~df["is_forecast"]]
    """
    df = pd.DataFrame({
        "mois"         : result.mois,
        "mois_label"   : result.mois_labels,
        "budget"       : result.budget,
        "reel"         : result.reel,
        "forecast_p50" : result.forecast_p50,
        "forecast_p10" : result.forecast_p10,
        "forecast_p90" : result.forecast_p90,
        "is_forecast"  : result.is_forecast,
    })

    # valeur_active : la courbe principale du graphique
    # Réel pour les mois passés, P50 pour les mois futurs → continuité visuelle
    df["valeur_active"] = np.where(
        ~df["is_forecast"],
        df["reel"],
        df["forecast_p50"],
    )

    # Écart vs budget pour les barres d'écart
    df["ecart_budget"] = df["valeur_active"] - df["budget"]
    df["ecart_budget_pct"] = np.where(
        df["budget"].abs() > 1e-9,
        df["ecart_budget"] / df["budget"].abs() * 100,
        0.0,
    )

    return df


def multi_methode_forecast(
    data      : DashboardData,
    site_code : str,
    kpi       : str = "CA_net",
    methodes  : Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Compare plusieurs méthodes de forecast sur un même (site, KPI).

    Utile pour l'affichage multi-courbes sur l'écran 4 :
    le DG voit simultanément budget, tendance et hybride
    pour évaluer l'incertitude entre les scénarios.

    Paramètres
    ----------
    data      : DashboardData
    site_code : code site
    kpi       : KPI à projeter
    methodes  : liste des méthodes à calculer
                Défaut : ["budget", "tendance", "hybride"]
                "budget" sert de référence, "tendance" et "hybride" de scénarios

    Retourne
    --------
    pd.DataFrame — format long, toutes méthodes concaténées
        Colonnes : mois, mois_label, methode, budget, reel, forecast_p50,
                   forecast_p10, forecast_p90, is_forecast, valeur_active,
                   ecart_budget, ecart_budget_pct, total_fc, ecart_annuel, ecart_pct

    Notes
    -----
    Le format long est directement compatible avec px.line(color="methode")
    pour afficher les courbes colorées par méthode dans Plotly Express.

    Exemple
    -------
    >>> multi = multi_methode_forecast(data, "LYO_E", kpi="EBE")
    >>> import plotly.express as px
    >>> fig = px.line(multi[multi["is_forecast"]], x="mois_label",
    ...               y="forecast_p50", color="methode")
    """
    methodes = methodes or ["budget", "tendance", "hybride"]
    dfs = []
    for m in methodes:
        r   = rolling_forecast(data, site_code, kpi, methode=m)
        df  = forecast_to_dataframe(r)
        df["methode"]      = m
        df["total_fc"]     = r.total_forecast
        df["ecart_annuel"] = r.ecart_vs_budget
        df["ecart_pct"]    = r.ecart_pct
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)


def forecast_groupe(
    data    : DashboardData,
    kpi     : str = "CA_net",
    methode : str = "hybride",
) -> pd.DataFrame:
    """
    Calcule le rolling forecast pour tous les sites + le consolidé groupe.

    Retourne une synthèse tabulaire (un site par ligne) avec les atterrissages.
    Utilisé pour la vue "atterrissage réseau" de l'écran 1 (tour de contrôle).

    Paramètres
    ----------
    data    : DashboardData
    kpi     : KPI à projeter (défaut : "CA_net")
    methode : méthode de forecast (défaut : "hybride")

    Retourne
    --------
    pd.DataFrame — 8 lignes (7 sites + 1 ligne groupe consolidée)
        Colonnes : site_code, site_libelle, kpi, methode,
                   budget_annuel, reel_ytd, forecast_p50, forecast_p10,
                   forecast_p90, ecart_vs_bgt, ecart_pct

    Notes
    -----
    La ligne groupe est la somme arithmétique des sites.
    ecart_pct du groupe est recalculé sur la somme des budgets,
    pas la moyenne des taux par site (convention correcte pour un réseau).

    Exemple
    -------
    >>> fg = forecast_groupe(data, kpi="REX")
    >>> print((fg[["site_libelle","forecast_p50","ecart_pct"]] /
    ...        [1, 1e3, 1]).round(1).to_string())
    """
    enregistrements = []
    for sc in data.sites:
        r = rolling_forecast(data, sc, kpi, methode)
        libelle = data.df_sites.set_index("site_code").loc[sc, "site_libelle"]
        enregistrements.append({
            "site_code"    : sc,
            "site_libelle" : libelle,
            "kpi"          : kpi,
            "methode"      : methode,
            "budget_annuel": r.total_budget,
            "reel_ytd"     : r.total_reel_ytd,
            "forecast_p50" : r.total_forecast,
            "forecast_p10" : r.total_p10,
            "forecast_p90" : r.total_p90,
            "ecart_vs_bgt" : r.ecart_vs_budget,
            "ecart_pct"    : r.ecart_pct,
        })

    df = pd.DataFrame(enregistrements)

    # Ligne consolidée : somme de tous les sites
    bgt_groupe = df["budget_annuel"].sum()
    fc_groupe  = df["forecast_p50"].sum()
    grp = {
        "site_code"    : "GROUPE",
        "site_libelle" : "Consolidé réseau",
        "kpi"          : kpi,
        "methode"      : methode,
        "budget_annuel": bgt_groupe,
        "reel_ytd"     : df["reel_ytd"].sum(),
        "forecast_p50" : fc_groupe,
        "forecast_p10" : df["forecast_p10"].sum(),
        "forecast_p90" : df["forecast_p90"].sum(),
        "ecart_vs_bgt" : df["ecart_vs_bgt"].sum(),
        "ecart_pct"    : (fc_groupe - bgt_groupe) / abs(bgt_groupe) * 100
                         if abs(bgt_groupe) > 1e-9 else 0.0,
    }
    return pd.concat([df, pd.DataFrame([grp])], ignore_index=True)


def cadence_label(mois_reel: int) -> str:
    """
    Retourne le label de cadence rolling pour l'affichage interface.

    Paramètres
    ----------
    mois_reel : mois courant (1–12)

    Retourne
    --------
    str : label au format "{réalisés}+{restants}" (ex. "4+8")

    Notes
    -----
    Cette terminologie est standard dans les directions financières :
    "4+8" = 4 mois réalisés + 8 mois en forecast
    Elle permet au DG d'identifier immédiatement le niveau de maturité
    de l'exercice et la fiabilité relative du forecast.

    Exemple
    -------
    >>> cadence_label(4)
    '4+8'
    >>> cadence_label(9)
    '9+3'
    """
    return f"{mois_reel}+{12 - mois_reel}"


# ══════════════════════════════════════════════════════════════════════════════
# EXÉCUTION DIRECTE
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    from loader import load_data

    chemin = sys.argv[1] if len(sys.argv) > 1 else "data/sample_budget_v2.xlsx"
    data   = load_data(chemin)

    print(f"\n{'═'*80}")
    print(f"ROLLING FORECAST — Cadence {cadence_label(data.mois_reel)} | Méthode : hybride")
    print(f"{'═'*80}")

    # ── Synthèse groupe tous KPIs ─────────────────────────────────────────────
    print("\n[ CA_net — Tous sites + groupe ]")
    fg = forecast_groupe(data, kpi="CA_net", methode="hybride")
    print(
        fg[["site_libelle","budget_annuel","reel_ytd","forecast_p50",
            "forecast_p10","forecast_p90","ecart_pct"]]
        .assign(
            budget_annuel=fg["budget_annuel"]/1e3,
            reel_ytd     =fg["reel_ytd"]/1e3,
            forecast_p50 =fg["forecast_p50"]/1e3,
            forecast_p10 =fg["forecast_p10"]/1e3,
            forecast_p90 =fg["forecast_p90"]/1e3,
        )
        .round({"budget_annuel":1,"reel_ytd":1,"forecast_p50":1,
                "forecast_p10":1,"forecast_p90":1,"ecart_pct":1})
        .to_string(index=False)
    )

    # ── Comparaison méthodes sur LYO_E (site en difficulté) ──────────────────
    print("\n[ EBE LYO_E — Comparaison méthodes (K€) ]")
    multi = multi_methode_forecast(data, "LYO_E", kpi="EBE")
    pivot = (
        multi[multi["is_forecast"]]
        .pivot_table(index="mois_label", columns="methode", values="forecast_p50")
        .reindex([MOIS_LABELS[m] for m in range(data.mois_reel+1, 13)])
    )
    r_ref = rolling_forecast(data, "LYO_E", "EBE", "budget")
    pivot["budget"] = [r_ref.budget[m-1] for m in range(data.mois_reel+1, 13)]
    print((pivot / 1e3).round(1).to_string())

    # ── Détail mensuel LYO_C / REX ────────────────────────────────────────────
    print("\n[ REX LYO_C — Série mensuelle hybride (K€) ]")
    r  = rolling_forecast(data, "LYO_C", "REX", "hybride")
    df = forecast_to_dataframe(r)
    print(
        df[["mois_label","budget","reel","forecast_p50","forecast_p10","forecast_p90","is_forecast"]]
        .assign(**{k: df[k]/1e3 for k in ["budget","forecast_p50","forecast_p10","forecast_p90"]})
        .assign(reel=df["reel"].apply(lambda x: round(x/1e3,1) if x is not None and not (isinstance(x, float) and np.isnan(x)) else None))
        .round(1).to_string(index=False)
    )
    print(
        f"\n  ↳ Forecast REX LYO_C : {r.total_forecast/1e3:.1f}K€ "
        f"[P10={r.total_p10/1e3:.1f} ; P90={r.total_p90/1e3:.1f}K€] "
        f"vs budget {r.total_budget/1e3:.1f}K€ ({r.ecart_pct:+.1f}%)"
    )
