"""
views/view_forecast.py
Écran 4 — Rolling Forecast (différenciateur FloMind)

Layout :
  Row 1 : Filtres (site, KPI, méthode, cadence)
  Row 2 : Graphique forecast principal (réel + P50 + bande P10-P90)
  Row 3 : Métriques atterrissage + comparaison méthodes
  Row 4 : Tableau mensuel détaillé
"""
from __future__ import annotations
import streamlit as st
import pandas as pd
import numpy as np

from loader import DashboardData
from forecast import (
    rolling_forecast, forecast_to_dataframe,
    multi_methode_forecast, forecast_groupe, cadence_label,
)
from components.formatters import fmt_ke, fmt_pct, mois_label
from components.charts import forecast_chart
from components.style import kpi_card, kpi_row, page_header, section_title


_KPI_OPTIONS = {
    "CA_net": "CA net (chiffre d'affaires)",
    "MC"    : "Marge commerciale",
    "VA"    : "Valeur ajoutée",
    "EBE"   : "EBE (excédent brut d'exploitation)",
    "REX"   : "REX (résultat d'exploitation)",
    "RCAI"  : "RCAI (résultat courant avant IS)",
}

_METHODE_INFO = {
    "hybride" : "🔀 Hybride (recommandé) — 55% tendance + 45% WLS",
    "tendance": "📈 Tendance — ratio YTD appliqué au budget restant",
    "wls"     : "📉 WLS — régression pondérée sur les réalisés",
    "budget"  : "📋 Budget — réel YTD + budget restant (baseline)",
}


def render(data: DashboardData) -> None:
    """Point d'entrée de la vue Rolling Forecast."""

    st.markdown("### 📡 Rolling Forecast")
    st.caption(
        "Différenciateur FloMind : deux références simultanées (budget ET forecast), "
        "bande P10–P90, agir avant que le problème soit consommé."
    )

    # ── 1. FILTRES ────────────────────────────────────────────────────────────
    col_site, col_kpi, col_meth, col_nsim = st.columns([2, 2, 2, 1])

    with col_site:
        site_options = ["Tous les sites (groupe)"] + data.sites
        site_sel = st.selectbox(
            "Site",
            options=site_options,
            format_func=lambda x: (
                x if x == "Tous les sites (groupe)"
                else data.df_sites.set_index("site_code").loc[x, "site_libelle"]
            ),
            key="fc_site",
        )
        site_code = None if site_sel == "Tous les sites (groupe)" else site_sel

    with col_kpi:
        kpi = st.selectbox(
            "KPI",
            options=list(_KPI_OPTIONS.keys()),
            format_func=lambda x: _KPI_OPTIONS[x],
            index=0,
            key="fc_kpi",
        )

    with col_meth:
        methode = st.selectbox(
            "Méthode",
            options=list(_METHODE_INFO.keys()),
            format_func=lambda x: _METHODE_INFO[x],
            index=0,
            key="fc_methode",
        )

    with col_nsim:
        n_sim = st.select_slider(
            "Simulations P10/P90",
            options=[200, 500, 1_000, 2_000],
            value=1_000,
            key="fc_nsim",
            help="Plus de simulations = bandes plus précises, calcul plus long",
        )

    # ── 2. CALCUL FORECAST ────────────────────────────────────────────────────
    cadence = cadence_label(data.mois_reel)

    if site_code:
        # Forecast d'un site spécifique
        with st.spinner("Calcul du forecast…"):
            result = rolling_forecast(data, site_code, kpi, methode, n_sim=n_sim)
        df_fc = forecast_to_dataframe(result)
        site_lib = data.df_sites.set_index("site_code").loc[site_code, "site_libelle"]
        titre_graphique = f"{_KPI_OPTIONS[kpi]} — {site_lib}"

    else:
        # Mode "groupe" : on affiche le forecast du groupe consolidé
        # On calcule le forecast de chaque site et on les somme
        with st.spinner("Calcul du forecast groupe (7 sites)…"):
            fg = forecast_groupe(data, kpi=kpi, methode=methode)

        # Afficher le tableau groupe directement
        st.markdown(f"**Atterrissage réseau — Cadence {cadence}**")

        display = fg[["site_libelle", "budget_annuel", "reel_ytd",
                       "forecast_p50", "forecast_p10", "forecast_p90", "ecart_pct"]].copy()
        display.columns = ["Site", "Budget K€", "Réel YTD K€", "Forecast P50 K€",
                           "P10 K€", "P90 K€", "Écart %"]
        for col in ["Budget K€", "Réel YTD K€", "Forecast P50 K€", "P10 K€", "P90 K€"]:
            display[col] = (display[col] / 1000).round(1)
        display["Écart %"] = display["Écart %"].round(1)

        def _style_ecart(val):
            if isinstance(val, (float, int)):
                if val < -5:
                    return "color: #ef4444; font-weight: bold"
                elif val > 5:
                    return "color: #22c55e; font-weight: bold"
            return ""

        st.dataframe(
            display.style.map(_style_ecart, subset=["Écart %"]),
            use_container_width=True,
            hide_index=True,
            height=310,
            column_config={
                "Écart %": st.column_config.NumberColumn(format="%.1f%%"),
            },
        )

        st.info(
            "💡 Sélectionnez un site spécifique pour voir le graphique de forecast mensuel "
            "et la comparaison des méthodes."
        )
        return

    # ── 3. GRAPHIQUE FORECAST PRINCIPAL ───────────────────────────────────────
    st.markdown(
        f"**{titre_graphique}** — Cadence **{cadence}** · Méthode : *{methode}*"
    )

    fig_fc = forecast_chart(df_fc, kpi_label=_KPI_OPTIONS[kpi], height=400)
    st.plotly_chart(fig_fc, use_container_width=True, key="fc_main")

    # ── 4. KPI ATTERRISSAGE ───────────────────────────────────────────────────
    kpi_row([
        kpi_card(
            label = "BUDGET ANNUEL",
            value = fmt_ke(result.total_budget),
            sub   = "Objectif 12 mois",
            color = "slate",
        ),
        kpi_card(
            label = f"RÉEL YTD · {cadence.split('+')[0]} MOIS",
            value = fmt_ke(result.total_reel_ytd),
            sub   = f"Cadence {cadence}",
            color = "blue",
        ),
        kpi_card(
            label     = "FORECAST P50",
            value     = fmt_ke(result.total_forecast),
            delta     = fmt_ke(result.ecart_vs_budget) + " vs budget",
            sub       = f"Écart : {result.ecart_pct:+.1f}%",
            favorable = result.ecart_vs_budget >= 0,
            color     = "amber",
        ),
        kpi_card(
            label = "P10 — PESSIMISTE",
            value = fmt_ke(result.total_p10),
            sub   = "1 chance / 10 de faire moins",
            color = "red",
        ),
        kpi_card(
            label = "P90 — OPTIMISTE",
            value = fmt_ke(result.total_p90),
            sub   = "1 chance / 10 de faire mieux",
            color = "green",
        ),
    ], n_cols=5)

    st.divider()

    # ── 5. COMPARAISON DES MÉTHODES ───────────────────────────────────────────
    col_comp, col_tbl = st.columns([3, 2], gap="large")

    with col_comp:
        section_title("Comparaison des méthodes de forecast")

        multi = multi_methode_forecast(data, site_code, kpi, methodes=list(_METHODE_INFO.keys()))
        df_fore = multi[multi["is_forecast"]].copy()

        # Tableau comparatif : atterrissage annuel par méthode
        # Cache session_state : 4 × rolling_forecast(n_sim=200) = ~800 simulations
        # évitées à chaque rerender. Clé = (site, kpi, mois_reel).
        _comp_key = f"_fc_comp_{site_code}_{kpi}_{data.mois_reel}_{data.annee}"
        if _comp_key not in st.session_state:
            st.session_state[_comp_key] = {
                m: rolling_forecast(data, site_code, kpi, m, n_sim=200)
                for m in _METHODE_INFO.keys()
            }
        results_comp = st.session_state[_comp_key]

        totaux = []
        for m, r_m in results_comp.items():
            totaux.append({
                "Méthode"   : _METHODE_INFO[m],
                "Forecast"  : fmt_ke(r_m.total_forecast),
                "vs Budget" : fmt_ke(r_m.ecart_vs_budget),
                "Écart %"   : fmt_pct(r_m.ecart_pct),
                "P10"       : fmt_ke(r_m.total_p10),
                "P90"       : fmt_ke(r_m.total_p90),
            })

        st.dataframe(
            pd.DataFrame(totaux),
            use_container_width=True,
            hide_index=True,
            height=200,
        )

    with col_tbl:
        st.markdown("**Série mensuelle — méthode hybride**")
        df_detail = df_fc[["mois_label", "budget", "reel", "forecast_p50",
                            "forecast_p10", "forecast_p90", "is_forecast"]].copy()
        for col in ["budget", "reel", "forecast_p50", "forecast_p10", "forecast_p90"]:
            df_detail[col] = (df_detail[col] / 1000).round(1)

        df_detail.columns = ["Mois", "Budget", "Réel", "P50", "P10", "P90", "Forecast"]
        df_detail["Réel"]    = df_detail["Réel"].where(~df_detail["Forecast"], None)
        df_detail["Forecast"] = df_detail["Forecast"].map({True: "▶", False: "✓"})

        st.dataframe(
            df_detail,
            use_container_width=True,
            hide_index=True,
            height=400,
            column_config={
                "Budget"  : st.column_config.NumberColumn(format="%.1f K€"),
                "Réel"    : st.column_config.NumberColumn(format="%.1f K€"),
                "P50"     : st.column_config.NumberColumn(format="%.1f K€"),
                "P10"     : st.column_config.NumberColumn(format="%.1f K€"),
                "P90"     : st.column_config.NumberColumn(format="%.1f K€"),
                "Forecast": st.column_config.TextColumn("Prévi?", width="small"),
            },
        )

    # ── 6. NOTE MÉTHODOLOGIQUE ────────────────────────────────────────────────
    with st.expander("ℹ️ Méthodologie — Comment lire ce graphique ?"):
        st.markdown("""
**Ligne grise pointillée — Budget annuel**
Objectif fixé en début d'année. Référence statique.

**Ligne bleue pleine — Réel**
Données constatées (Jan → mois courant). Certitude totale.

**Ligne orange — Forecast P50**
Projection centrale pour les mois restants. Méthode hybride :
combinaison pondérée du ratio de tendance YTD et d'une régression WLS.

**Bande orange transparente — Intervalle P10-P90**
Plage d'incertitude calculée par bootstrap sur les résidus historiques.
- **Bande étroite** → performance régulière, peu volatile
- **Bande large**   → site imprévisible, vigilance accrue

**Méthodes disponibles**
| Méthode | Principe | Quand l'utiliser |
|---------|----------|-----------------|
| Budget | Reste de l'année = budget pur | Baseline optimiste, début d'exercice |
| Tendance | Ratio YTD appliqué au reste | Présentation Codir, lisible DG |
| WLS | Régression pondérée sur réalisés | Mois 7+ avec inflexion récente |
| **Hybride** | 55% Tendance + 45% WLS | **Recommandé** — équilibre robustesse/réactivité |
        """)
