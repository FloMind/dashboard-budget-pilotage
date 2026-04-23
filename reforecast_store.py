"""
reforecast_store.py
══════════════════════════════════════════════════════════════════════════════
Persistance et calculs du Reforecast CDG.

Distinction fondamentale :
  Budget      → objectif N-1, immuable
  Reforecast  → révision formelle par le CDG en cours d'année
                intègre des hypothèses opérationnelles (recrutement, appel
                d'offres, travaux, problème fournisseur résolu…)
  Atterrissage → projection algorithmique (tendance + WLS), sans jugement CDG

Structure JSON (data/reforecast.json) :
{
  "meta": {"annee": 2025, "last_updated": "2025-04-23T14:30:00"},
  "sites": {
    "LYO_C": {
      "note": "Recrutement commercial Q4 — +8% CA attendu",
      "CA_net": {"10": 72000, "11": 75000, "12": 80000},
      "EBE":    {"10": 8500,  "11": 9200,  "12": 10000},
      "REX":    {"10": 5000,  "11": 5800,  "12": 6500}
    }
  }
}

Seuls les mois FUTURS (> mois_reel) sont stockés — les mois passés sont
toujours le réel constaté, immuable.
══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

DEFAULT_PATH = Path("data/reforecast.json")

KPIS_REFORECAST = ["CA_net", "EBE", "REX"]   # KPIs disponibles pour le reforecast
KPI_LABELS = {
    "CA_net": "CA net (K€)",
    "EBE"   : "EBE (K€)",
    "REX"   : "REX (K€)",
}


# ════════════════════════════════════════════════════════════════════════════
# PERSISTANCE
# ════════════════════════════════════════════════════════════════════════════

def load_reforecast(path: Path = DEFAULT_PATH) -> dict:
    """Charge le JSON de reforecast. Retourne {} si le fichier n'existe pas."""
    if not Path(path).exists():
        return {"meta": {}, "sites": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"meta": {}, "sites": {}}


def save_reforecast(rf_data: dict, path: Path = DEFAULT_PATH) -> None:
    """Sauvegarde le JSON de reforecast avec timestamp."""
    rf_data.setdefault("meta", {})
    rf_data["meta"]["last_updated"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rf_data, f, indent=2, ensure_ascii=False)


def set_reforecast_values(
    rf_data      : dict,
    site_code    : str,
    kpi          : str,
    mois_values  : Dict[int, float],  # {mois: valeur_revisee}
    note         : str = "",
) -> dict:
    """
    Enregistre les valeurs révisées pour un site/KPI dans le dict reforecast.
    Ne modifie pas le fichier — appeler save_reforecast() ensuite.
    """
    rf_data.setdefault("sites", {})
    rf_data["sites"].setdefault(site_code, {})
    rf_data["sites"][site_code][kpi] = {str(m): float(v) for m, v in mois_values.items()}
    if note:
        rf_data["sites"][site_code]["note"] = note
    return rf_data


def get_reforecast_note(rf_data: dict, site_code: str) -> str:
    """Retourne la note CDG du site ou '' si absente."""
    return rf_data.get("sites", {}).get(site_code, {}).get("note", "")


# ════════════════════════════════════════════════════════════════════════════
# CALCULS
# ════════════════════════════════════════════════════════════════════════════

def get_monthly_reforecast(
    rf_data    : dict,
    site_code  : str,
    kpi        : str,
    mois_reel  : int,
    budget_m   : List[float],  # 12 valeurs budget mensuel
    reel_m     : List[float],  # 12 valeurs réel (NaN pour mois futurs)
) -> List[float]:
    """
    Retourne la série mensuelle 12 mois pour le reforecast :
      - Mois ≤ mois_reel   : réel constaté (immuable)
      - Mois > mois_reel   : valeur saisie par le CDG, ou budget si absent

    Paramètres
    ----------
    budget_m : liste de 12 valeurs budget (index 0 = janvier)
    reel_m   : liste de 12 valeurs réel   (NaN pour mois futurs)
    """
    result = list(budget_m)  # base = budget sur 12 mois

    # Mois réalisés → réel
    for i in range(mois_reel):
        v = reel_m[i]
        result[i] = float(v) if v is not None and not (isinstance(v, float) and np.isnan(v)) else float(budget_m[i])

    # Mois futurs → valeurs saisies si disponibles
    rf_site = rf_data.get("sites", {}).get(site_code, {})
    rf_kpi  = rf_site.get(kpi, {})
    for m_str, val in rf_kpi.items():
        m = int(m_str)
        if m > mois_reel and 1 <= m <= 12:
            result[m - 1] = float(val)

    return result


def compute_reforecast_totals(
    rf_data  : dict,
    data,             # DashboardData
) -> dict:
    """
    Calcule les totaux reforecast annuels par site et par KPI.

    Retourne
    --------
    dict : {site_code: {kpi: total_reforecast}}
    """
    from loader import filter_to_mois

    totals = {}
    for sc in data.sites:
        totals[sc] = {}
        for kpi in KPIS_REFORECAST:
            # Budget mensuel
            df_bgt = data.sig_mensuel[
                (data.sig_mensuel["site_code"] == sc) &
                (data.sig_mensuel["kpi"] == kpi)
            ].sort_values("mois")
            budget_m = df_bgt["budget"].tolist()
            reel_m   = [
                float(v) if not (isinstance(v, float) and np.isnan(v)) else None
                for v in df_bgt["reel"].tolist()
            ]

            monthly = get_monthly_reforecast(
                rf_data, sc, kpi, data.mois_reel, budget_m, reel_m
            )
            totals[sc][kpi] = sum(monthly)

    return totals


def has_reforecast(rf_data: dict, site_code: str = None) -> bool:
    """Retourne True si au moins un reforecast a été saisi (pour le site donné ou globalement)."""
    sites = rf_data.get("sites", {})
    if site_code:
        site = sites.get(site_code, {})
        return any(k in site for k in KPIS_REFORECAST)
    return any(
        any(k in site_data for k in KPIS_REFORECAST)
        for site_data in sites.values()
    )
