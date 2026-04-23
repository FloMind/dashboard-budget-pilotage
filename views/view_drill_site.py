"""
views/view_drill_site.py
Écran 2 — Drill-down site (vue directeur de site)

Layout :
  Row 1 : KPI strip site (CA / EBE / REX + taux de marge)
  Row 2 : Courbes mensuelles Budget vs Réel (sélecteur KPI)
  Row 3 : Tableau P&L mensuel détaillé (budget vs réel, toutes classes)
  Row 4 : Top 5 écarts du site
"""
from __future__ import annotations
import streamlit as st
import pandas as pd
import numpy as np

from loader import DashboardData, get_site_data, get_top_ecarts
from metrics import (
    compute_kpi_strip, compute_atterrissage, compute_evolution_mensuelle,
)
from components.formatters import (
    fmt_ke, fmt_pct, delta_str, cadence_label_long, mois_label,
)
from components.charts import monthly_comparison_chart, ecarts_bar_chart
from components.style import kpi_card, kpi_row, page_header, section_title


_KPI_LABELS = {
    "CA_net": "CA net",
    "MC"    : "Marge commerciale",
    "VA"    : "Valeur ajoutée",
    "EBE"   : "EBE",
    "REX"   : "Résultat d'exploitation",
    "RCAI"  : "RCAI",
}


def render(data: DashboardData) -> None:
    """Point d'entrée de la vue Drill-down site."""

    # ── Sélecteur site ────────────────────────────────────────────────────────
    col_sel, col_title = st.columns([1, 3])
    with col_sel:
        sites_labels = {
            sc: data.df_sites.set_index("site_code").loc[sc, "site_libelle"]
            for sc in data.sites
        }
        site_code = st.selectbox(
            "Site",
            options=data.sites,
            format_func=lambda x: sites_labels[x],
            key="drill_site",
        )

    site_row  = data.df_sites.set_index("site_code").loc[site_code]
    with col_title:
        page_header(
            title    = f"📍 {site_row['site_libelle']}",
            subtitle = f"{site_row['departement']} · {site_row['responsable']} · {cadence_label_long(data.mois_reel)}",
            badges   = [site_row["type_site"], f"Ouverture {site_row['date_ouverture']}"],
        )

    # ── 1. KPI STRIP SITE ────────────────────────────────────────────────────
    kpi = compute_kpi_strip(data, site_code)
    att = compute_atterrissage(data, site_code)

    delta_mc_pt = kpi.tx_mc_reel - kpi.tx_mc_budget

    kpi_row([
        kpi_card(
            label     = "CA YTD RÉEL",
            value     = fmt_ke(kpi.ca_ytd_reel),
            delta     = f"{kpi.ca_ecart_pct:+.1f}% vs budget",
            sub       = f"Budget : {fmt_ke(kpi.ca_ytd_budget)}",
            favorable = kpi.ca_ecart_pct >= 0,
            color     = "blue",
        ),
        kpi_card(
            label     = "TAUX DE MARGE",
            value     = fmt_pct(kpi.tx_mc_reel, force_sign=False),
            delta     = f"{delta_mc_pt:+.1f}pt vs budget",
            sub       = f"Budget : {fmt_pct(kpi.tx_mc_budget, force_sign=False)}",
            favorable = delta_mc_pt >= 0,
            color     = "green",
        ),
        kpi_card(
            label     = "EBE YTD RÉEL",
            value     = fmt_ke(kpi.ebe_ytd_reel),
            delta     = f"{kpi.tx_ebe_reel:.1f}% CA",
            sub       = f"Budget : {fmt_ke(kpi.ebe_ytd_budget)}",
            favorable = kpi.ebe_ytd_reel >= kpi.ebe_ytd_budget,
            color     = "amber",
        ),
        kpi_card(
            label     = "REX YTD RÉEL",
            value     = fmt_ke(kpi.rex_ytd_reel),
            delta     = f"{kpi.tx_rex_reel:.1f}% CA",
            sub       = f"Budget : {fmt_ke(kpi.rex_ytd_budget)}",
            favorable = kpi.rex_ytd_reel >= kpi.rex_ytd_budget,
            color     = "purple",
        ),
        kpi_card(
            label     = "ATTERRISSAGE REX",
            value     = fmt_ke(att.rex_forecast),
            delta     = fmt_ke(att.rex_ecart_vs_bgt) + " vs objectif",
            sub       = f"Budget annuel : {fmt_ke(att.rex_bgt_annuel)}",
            favorable = att.rex_ecart_vs_bgt >= 0,
            color     = "cyan",
        ),
    ], n_cols=5)

    st.divider()

    # ── 2. COURBES MENSUELLES ─────────────────────────────────────────────────
    col_kpi_sel, _ = st.columns([2, 4])
    with col_kpi_sel:
        kpi_choisi = st.selectbox(
            "KPI à afficher",
            options=list(_KPI_LABELS.keys()),
            format_func=lambda x: _KPI_LABELS[x],
            index=0,
            key="drill_kpi",
        )

    df_evol = compute_evolution_mensuelle(data, site_code, kpi_choisi)
    fig_monthly = monthly_comparison_chart(
        df_evol,
        kpi_label=_KPI_LABELS[kpi_choisi],
        height=320,
    )
    st.plotly_chart(fig_monthly, use_container_width=True, key="drill_monthly")

    st.divider()

    # ── 3. TABLEAU P&L MENSUEL ────────────────────────────────────────────────
    section_title("P&L mensuel — Budget vs Réel par classe")

    # Construction du tableau pivot : ligne = classe CDG, colonne = mois
    df_site = get_site_data(data, site_code, mois_max=data.mois_reel)

    # Agrégat mensuel × classe
    pivot_bgt = (
        df_site.groupby(["classe_cdg", "ordre_classe", "mois"])["montant_budget"]
        .sum()
        .unstack("mois")
        .sort_values("ordre_classe")
    )
    pivot_rel = (
        df_site.groupby(["classe_cdg", "ordre_classe", "mois"])["montant_reel"]
        .sum()
        .unstack("mois")
        .sort_values("ordre_classe")
    )

    # Affichage interleaved Budget / Réel par mois
    mois_cols = list(range(1, data.mois_reel + 1))
    rows = []
    for (classe, ordre) in pivot_bgt.index:
        row_bgt = {"Classe": classe, "Type": "Budget"}
        row_rel = {"Classe": classe, "Type": "Réel"}
        row_eca = {"Classe": classe, "Type": "Écart"}
        for m in mois_cols:
            b = pivot_bgt.loc[(classe, ordre), m] / 1000 if m in pivot_bgt.columns else 0.0
            r = pivot_rel.loc[(classe, ordre), m] / 1000 if m in pivot_rel.columns else np.nan
            row_bgt[mois_label(m)] = round(b, 1)
            row_rel[mois_label(m)] = round(r, 1) if not np.isnan(r) else None
            row_eca[mois_label(m)] = round(r - b, 1) if not np.isnan(r) else None
        rows.extend([row_bgt, row_rel, row_eca])

    df_pl = pd.DataFrame(rows)

    # Colorisation des lignes Écart
    def _style_pl(row):
        if row["Type"] == "Écart":
            # Si écart > 0 sur un produit ou < 0 sur une charge → vert
            return ["font-weight: bold; opacity: 0.85"] * len(row)
        elif row["Type"] == "Budget":
            return ["color: #94a3b8"] * len(row)
        return [""] * len(row)

    st.dataframe(
        df_pl.style.apply(_style_pl, axis=1),
        use_container_width=True,
        hide_index=True,
        height=420,
        column_config={
            "Type": st.column_config.TextColumn(width="small"),
            "Classe": st.column_config.TextColumn(width="medium"),
        },
    )
    st.caption("Montants en K€. Lignes 'Écart' = Réel − Budget.")

    st.divider()

    # ── 4. TOP ÉCARTS DU SITE ─────────────────────────────────────────────────
    col_top, col_info = st.columns([3, 2], gap="large")

    with col_top:
        section_title(f"Top 8 dérives défavorables (YTD)")
        top_ecarts = get_top_ecarts(data, site_code=site_code, n=8)
        if len(top_ecarts) > 0:
            fig_ecarts = ecarts_bar_chart(
                top_ecarts, n=8,
                titre=f"Top dérives — {sites_labels[site_code]} (YTD)",
                height=280,
            )
            st.plotly_chart(fig_ecarts, use_container_width=True, key="drill_ecarts")
        else:
            st.success("✅ Aucune dérive matérielle sur ce site.")

    with col_info:
        st.markdown("**Informations site**")
        info = {
            "Code"       : site_code,
            "Site"       : site_row["site_libelle"],
            "Département": site_row["departement"],
            "Type"       : site_row["type_site"],
            "Responsable": site_row["responsable"],
            "Ouverture"  : site_row["date_ouverture"],
            "CA budget"  : fmt_ke(site_row.get("ca_budget", 0)),
            "EBE budget" : fmt_ke(site_row.get("ebe_budget", 0)),
            "Tx EBE bgt" : fmt_pct(site_row.get("tx_ebe_budget", 0), force_sign=False),
        }
        for label, val in info.items():
            st.markdown(f"**{label}** : {val}")
