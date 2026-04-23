"""
views/view_ecarts.py
Écran 3 — Analyse des écarts (vue contrôleur de gestion)

Layout :
  Row 1 : Filtres (site, seuil %, seuil €, sens)
  Row 2 : Graphique Top N écarts (barres horizontales)
  Row 3 : Tableau détaillé des dérives avec scores de matérialité
  Row 4 : Waterfall mensuel du site/mois sélectionné
"""
from __future__ import annotations
import streamlit as st
import pandas as pd
import numpy as np

from loader import DashboardData, get_top_ecarts
from metrics import compute_alertes, compute_waterfall_mensuel, summary_alertes
from components.formatters import (
    fmt_ke, fmt_pct, priorite_label, sens_label, mois_label,
)
from components.charts import ecarts_bar_chart, waterfall_chart


def render(data: DashboardData) -> None:
    """Point d'entrée de la vue Analyse des écarts."""

    st.markdown("### 🔍 Analyse des écarts — Diagnostic YTD")
    st.caption(
        "Double critère de matérialité : |écart %| ≥ seuil ET |écart €| ≥ seuil. "
        "Seuls les comptes vérifiant les deux conditions sont affichés."
    )

    # ── 1. FILTRES ────────────────────────────────────────────────────────────
    with st.expander("⚙️ Paramètres de filtrage", expanded=True):
        f1, f2, f3, f4, f5 = st.columns(5)

        with f1:
            sites_options = ["Tous les sites"] + data.sites
            site_filtre   = st.selectbox("Site", options=sites_options, key="ec_site")
            site_code     = None if site_filtre == "Tous les sites" else site_filtre

        with f2:
            seuil_pct = st.slider(
                "Seuil écart %", min_value=1.0, max_value=25.0,
                value=5.0, step=0.5, key="ec_pct",
                help="Seuil minimum d'écart en % pour déclencher une alerte",
            )

        with f3:
            seuil_abs = st.select_slider(
                "Seuil écart €",
                options=[500, 1_000, 2_000, 5_000, 10_000],
                value=2_000, key="ec_abs",
                format_func=lambda x: fmt_ke(x),
                help="Seuil minimum en valeur absolue — filtre les micro-comptes",
            )

        with f4:
            sens_filtre = st.selectbox(
                "Sens",
                options=["Défavorables", "Favorables", "Tous"],
                key="ec_sens",
            )
            sens_map = {"Défavorables": "defavorable", "Favorables": "favorable", "Tous": "all"}

        with f5:
            n_top = st.number_input("Top N", min_value=3, max_value=20, value=10, key="ec_n")

    # ── 2. CALCUL ALERTES ─────────────────────────────────────────────────────
    alertes = compute_alertes(
        data,
        seuil_ecart_pct=seuil_pct,
        seuil_ecart_abs=seuil_abs,
        site_code=site_code,
    )
    resume = summary_alertes(alertes)

    # Métriques résumées
    col_t, col_c, col_i, col_s, col_f, col_d = st.columns(6)
    col_t.metric("Total", resume["total"])
    col_c.metric("🔴 Critiques",   resume["critiques"])
    col_i.metric("🟠 Importants",  resume["importantes"])
    col_s.metric("🟡 Surveillance",resume["surveillance"])
    col_f.metric("✅ Favorables",  resume["favorables"])
    col_d.metric("❌ Défavorables",resume["defavorables"])

    if not alertes:
        st.success(
            f"✅ Aucune dérive matérielle avec les seuils actuels "
            f"({seuil_pct:.0f}% et {fmt_ke(seuil_abs)})."
        )
        return

    st.divider()

    # ── 3. GRAPHIQUE TOP ÉCARTS ───────────────────────────────────────────────
    col_chart, col_details = st.columns([2, 3], gap="large")

    with col_chart:
        st.markdown(f"**Top {n_top} — {sens_filtre.lower()}**")

        top = get_top_ecarts(
            data,
            site_code=site_code,
            n=int(n_top),
            sens_ecart=sens_map[sens_filtre],
        )
        if len(top) > 0:
            fig = ecarts_bar_chart(
                top,
                n=int(n_top),
                titre=f"Top {n_top} écarts {sens_filtre.lower()} (YTD)",
                height=max(300, len(top) * 36 + 80),
            )
            st.plotly_chart(fig, use_container_width=True, key="ec_bars")
        else:
            st.info("Aucun écart dans ce sens avec les filtres actuels.")

    # ── 4. TABLEAU DÉTAILLÉ ───────────────────────────────────────────────────
    with col_details:
        st.markdown("**Tableau détaillé des alertes**")

        # Filtrage selon le sens sélectionné
        if sens_filtre == "Défavorables":
            alertes_filtre = [a for a in alertes if not a.est_favorable]
        elif sens_filtre == "Favorables":
            alertes_filtre = [a for a in alertes if a.est_favorable]
        else:
            alertes_filtre = alertes

        if not alertes_filtre:
            st.info("Aucune alerte avec ce filtre.")
        else:
            rows = []
            for a in alertes_filtre:
                rows.append({
                    "P"      : a.priorite,
                    "Impact" : sens_label(a.est_favorable),
                    "Site"   : a.site_code,
                    "Classe" : a.classe_cdg,
                    "Compte" : a.compte_code,
                    "Libellé": a.compte_libelle[:36],
                    "Bgt YTD": round(a.budget_ytd / 1000, 1),
                    "Réel YTD": round(a.reel_ytd / 1000, 1),
                    "Écart K€": round(a.ecart_abs / 1000, 1),
                    "Écart %" : round(a.ecart_pct, 1),
                })

            df_tbl = pd.DataFrame(rows)

            def _color_ecart(val):
                if isinstance(val, (int, float)):
                    if val < 0:
                        return "color: #ef4444; font-weight: bold"
                    elif val > 0:
                        return "color: #22c55e; font-weight: bold"
                return ""

            st.dataframe(
                df_tbl.style.map(_color_ecart, subset=["Écart K€", "Écart %"]),
                use_container_width=True,
                hide_index=True,
                height=340,
                column_config={
                    "P"       : st.column_config.NumberColumn("P", format="%d", width="small"),
                    "Bgt YTD" : st.column_config.NumberColumn("Bgt K€", format="%.1f"),
                    "Réel YTD": st.column_config.NumberColumn("Réel K€", format="%.1f"),
                    "Écart K€": st.column_config.NumberColumn("Écart K€", format="%.1f"),
                    "Écart %" : st.column_config.NumberColumn("Écart %", format="%.1f%%"),
                },
            )

    st.divider()

    # ── 5. WATERFALL MENSUEL ──────────────────────────────────────────────────
    st.markdown("**Décomposition mensuelle Budget → Réel par site**")
    st.caption("Sélectionner un site et un mois réalisé pour décomposer l'écart mensuel.")

    col_wf_site, col_wf_mois, col_wf_graph = st.columns([1, 1, 4])

    with col_wf_site:
        wf_site = st.selectbox(
            "Site",
            options=data.sites,
            format_func=lambda x: data.df_sites.set_index("site_code").loc[x, "site_libelle"],
            key="wf_site",
        )

    with col_wf_mois:
        mois_options = list(range(1, data.mois_reel + 1))
        wf_mois = st.selectbox(
            "Mois",
            options=mois_options,
            format_func=mois_label,
            index=data.mois_reel - 1,
            key="wf_mois",
        )

    with col_wf_graph:
        wf_data = compute_waterfall_mensuel(data, wf_site, wf_mois)
        wf_dict = {
            "drivers"    : wf_data[wf_data["type"] == "driver"],
            "total_bgt"  : float(wf_data[wf_data["type"] == "budget_initial"]["budget"].iloc[0]),
            "total_rel"  : float(wf_data[wf_data["type"] == "total_reel"]["reel"].iloc[0]),
            "ecart_total": float(wf_data[wf_data["type"] == "total_reel"]["contribution"].iloc[0]),
        }
        site_lib = data.df_sites.set_index("site_code").loc[wf_site, "site_libelle"]
        fig_wf = waterfall_chart(
            wf_dict,
            titre=f"Waterfall {site_lib} — {mois_label(wf_mois)} {data.annee}",
            height=360,
        )
        st.plotly_chart(fig_wf, use_container_width=True, key="wf_mensuel")

    # ── 6. ZONE COMMENTAIRE CDG ───────────────────────────────────────────────
    st.markdown("**📝 Commentaire CDG**")
    st.caption(
        "Zone de saisie libre pour le contrôleur de gestion. "
        "À connecter à une base de données persistante en production."
    )
    commentaire = st.text_area(
        label="Commentaire",
        placeholder=(
            f"Analyse des écarts {site_lib} — {mois_label(wf_mois)} {data.annee}\n\n"
            "Points clés :\n• …\n• …\n\nActions correctives :\n• …"
        ),
        height=120,
        key=f"comment_{wf_site}_{wf_mois}",
        label_visibility="collapsed",
    )
    if commentaire:
        st.success("✅ Commentaire saisi (persistance à implémenter via commentaires.json)")
