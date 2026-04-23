"""
views/view_tour_de_controle.py
Écran 1 — Tour de contrôle réseau (vue DG)

Layout :
  Row 1 : KPI strip (CA / EBE / REX / Atterrissage)
  Row 2 : Waterfall YTD consolidé | Alertes réseau
  Row 3 : Heatmap EBE multi-sites × mois
  Row 4 : Tableau atterrissage réseau
"""
from __future__ import annotations
import streamlit as st
import pandas as pd

from loader import DashboardData, get_ytd_by_classe, get_waterfall_data, get_heatmap_data
from metrics import (
    compute_kpi_strip, compute_alertes, compute_atterrissage_groupe,
    compute_contribution_reseau, summary_alertes, compute_waterfall_mensuel,
)
from components.formatters import (
    fmt_ke, fmt_pct, delta_str, priorite_label, sens_label, cadence_label_long,
)
from components.charts import (
    waterfall_chart, heatmap_chart, donut_contribution, ecarts_bar_chart,
)
from components.style import kpi_card, kpi_row, page_header, section_title


def render(data: DashboardData) -> None:
    """Point d'entrée de la vue Tour de Contrôle."""

    mois_labels = ["Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"]

    # ── En-tête ───────────────────────────────────────────────────────────────
    page_header(
        title    = f"🗺️ Tour de contrôle réseau — {data.annee}",
        subtitle = cadence_label_long(data.mois_reel),
        badges   = [
            f"{len(data.sites)} sites",
            f"{data.df['compte_code'].nunique()} comptes PCG",
            f"Données au {mois_labels[data.mois_reel-1]} {data.annee}",
        ],
    )

    # ── 1. KPI STRIP ─────────────────────────────────────────────────────────
    kpi     = compute_kpi_strip(data)
    att_ebe = kpi.ebe_atterrissage
    bgt_ebe = float(data.sig_annuel.loc[:, "EBE"].sum())
    ecart_att_ca  = kpi.ca_atterrissage - kpi.ca_annuel_bgt
    ecart_att_ebe = att_ebe - bgt_ebe

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
            label     = "ATTERRISSAGE CA",
            value     = fmt_ke(kpi.ca_atterrissage),
            delta     = fmt_ke(ecart_att_ca) + " vs objectif",
            sub       = f"Budget annuel : {fmt_ke(kpi.ca_annuel_bgt)}",
            favorable = ecart_att_ca >= 0,
            color     = "cyan",
        ),
        kpi_card(
            label     = "EBE YTD RÉEL",
            value     = fmt_ke(kpi.ebe_ytd_reel),
            delta     = f"{kpi.tx_ebe_reel:.1f}% CA · {kpi.ebe_ytd_reel - kpi.ebe_ytd_budget:+.0f}€ vs bgt",
            sub       = f"Budget : {fmt_ke(kpi.ebe_ytd_budget)}",
            favorable = kpi.ebe_ytd_reel >= kpi.ebe_ytd_budget,
            color     = "amber",
        ),
        kpi_card(
            label     = "REX YTD RÉEL",
            value     = fmt_ke(kpi.rex_ytd_reel),
            delta     = f"{kpi.tx_rex_reel:.1f}% CA",
            sub       = f"Budget : {fmt_ke(kpi.rex_ytd_budget)}",
            favorable = kpi.rex_ytd_reel >= 0,
            color     = "purple",
        ),
        kpi_card(
            label     = "ATTERRISSAGE EBE",
            value     = fmt_ke(att_ebe),
            delta     = fmt_ke(ecart_att_ebe) + " vs objectif",
            sub       = f"Budget annuel : {fmt_ke(bgt_ebe)}",
            favorable = ecart_att_ebe >= 0,
            color     = "cyan",
        ),
    ], n_cols=5)

    st.divider()

    # ── 2. WATERFALL + ALERTES ────────────────────────────────────────────────
    col_wf, col_alertes = st.columns([3, 2], gap="large")

    with col_wf:
        st.markdown("**Décomposition de l'écart YTD — tous sites**")

        # Waterfall consolidé : agrégation YTD toutes classes
        df_ytd = get_ytd_by_classe(data)   # tous sites
        # waterfall_chart attend "contribution" — get_ytd_by_classe retourne "ecart"
        df_ytd["contribution"] = df_ytd["ecart"]
        total_bgt = float(df_ytd["budget"].sum())
        total_rel = float(df_ytd["reel"].sum())

        wf_data = {
            "drivers"    : df_ytd,
            "total_bgt"  : total_bgt,
            "total_rel"  : total_rel,
            "ecart_total": total_rel - total_bgt,
        }
        fig_wf = waterfall_chart(wf_data, titre="Budget → Réel YTD (résultat, K€)")
        st.plotly_chart(fig_wf, use_container_width=True, key="wf_tour")

    with col_alertes:
        alertes = compute_alertes(data)
        resume  = summary_alertes(alertes)

        section_title("Alertes réseau")

        # Compteurs alertes — 3 cartes compactes
        kpi_row([
            kpi_card(
                label     = "CRITIQUES",
                value     = str(resume["critiques"]),
                favorable = resume["critiques"] == 0,
                color     = "red" if resume["critiques"] > 0 else "green",
            ),
            kpi_card(
                label     = "IMPORTANTS",
                value     = str(resume["importantes"]),
                favorable = resume["importantes"] == 0,
                color     = "amber" if resume["importantes"] > 0 else "green",
            ),
            kpi_card(
                label     = "SURVEILLANCE",
                value     = str(resume["surveillance"]),
                color     = "slate" if resume["surveillance"] == 0 else "amber",
            ),
        ], n_cols=3)

        if alertes:
            rows = []
            for a in alertes[:8]:
                rows.append({
                    "Site"   : a.site_code,
                    "Compte" : a.compte_libelle[:28],
                    "Écart K€": f"{a.ecart_abs/1000:+.1f}",
                    "Écart %" : f"{a.ecart_pct:+.1f}%",
                    "Impact" : sens_label(a.est_favorable),
                    "P"      : a.priorite,
                })
            df_alert = pd.DataFrame(rows)
            st.dataframe(
                df_alert,
                use_container_width=True,
                hide_index=True,
                height=280,
                column_config={
                    "P": st.column_config.NumberColumn("Prio", format="%d"),
                    "Écart K€": st.column_config.TextColumn("Écart K€"),
                },
            )
        else:
            st.success("✅ Aucune dérive matérielle détectée sur le réseau.")

    st.divider()

    # ── 3. HEATMAP ────────────────────────────────────────────────────────────
    section_title("Écart % vs budget — Sites × mois (YTD)")
    st.caption("Vert = surperformance · Rouge = sous-performance · Gris = non réalisé")

    col_hm_ctrl, _ = st.columns([2, 4])
    with col_hm_ctrl:
        kpi_hm = st.selectbox(
            "KPI heatmap",
            options=["EBE", "CA_net", "REX", "MC"],
            index=0,
            key="hm_kpi",
        )

    pivot = get_heatmap_data(data, kpi=kpi_hm, base="ecart_pct")

    # Filtrer seulement les mois réalisés pour éviter le bruit
    cols_realises = [c for c in pivot.columns if c <= data.mois_reel]
    pivot_ytd = pivot[cols_realises]

    fig_hm = heatmap_chart(
        pivot_ytd,
        titre=f"Écart % {kpi_hm} vs budget",
        seuil=50.0,
        height=240,
    )
    st.plotly_chart(fig_hm, use_container_width=True, key="hm_tour")

    st.divider()

    # ── 4. TABLEAU ATTERRISSAGE RÉSEAU ────────────────────────────────────────
    section_title("Atterrissages fin d'exercice — Réseau complet")

    att_df = compute_atterrissage_groupe(data)

    # Mise en forme lisible
    display = pd.DataFrame({
        "Scope"          : att_df.index,
        "CA budget (K€)" : (att_df["ca_bgt"] / 1000).round(0),
        "CA YTD réel (K€)": (att_df["ca_ytd_reel"] / 1000).round(1),
        "CA forecast (K€)": (att_df["ca_forecast"] / 1000).round(0),
        "Δ CA vs bgt"    : att_df["ca_ecart_bgt"].apply(lambda x: fmt_ke(x)),
        "EBE forecast (K€)": (att_df["ebe_forecast"] / 1000).round(1),
        "Tx EBE %"       : att_df["tx_ebe_forecast"].round(1),
        "REX forecast (K€)": (att_df["rex_forecast"] / 1000).round(1),
        "Tx REX %"       : att_df["tx_rex_forecast"].round(1),
    })

    def _style_row(row):
        """Couleur de fond selon la performance REX."""
        val = row.get("REX forecast (K€)", 0)
        if val < 0:
            return ["background-color: rgba(239,68,68,0.08)"] * len(row)
        elif val > 0:
            return ["background-color: rgba(34,197,94,0.06)"] * len(row)
        return [""] * len(row)

    st.dataframe(
        display.style.apply(_style_row, axis=1),
        use_container_width=True,
        hide_index=True,
        height=310,
        column_config={
            "Tx EBE %": st.column_config.NumberColumn(format="%.1f %%"),
            "Tx REX %": st.column_config.NumberColumn(format="%.1f %%"),
        },
    )

    # ── 5. CONTRIBUTION CA RÉSEAU ─────────────────────────────────────────────
    col_donut, col_rank = st.columns(2, gap="large")

    with col_donut:
        section_title("Contribution CA réseau (forecast)")
        df_contrib = compute_contribution_reseau(data, kpi="CA_net")
        fig_donut  = donut_contribution(df_contrib, titre="Part CA par site")
        st.plotly_chart(fig_donut, use_container_width=True, key="donut_ca")

    with col_rank:
        section_title("Ranking REX (forecast fin d'exercice)")
        from metrics import compute_ranking
        rank = compute_ranking(data, kpi="REX", base="forecast")
        rank_display = rank.copy()
        rank_display["valeur"]  = (rank_display["valeur"] / 1000).round(1)
        rank_display["tx_pct"]  = rank_display["tx_pct"].round(1)
        rank_display.columns    = ["#", "Code", "Site", "Département", "REX K€", "Tx REX %"]
        st.dataframe(
            rank_display,
            use_container_width=True,
            hide_index=True,
            height=270,
            column_config={
                "Tx REX %": st.column_config.NumberColumn(format="%.1f %%"),
            },
        )
