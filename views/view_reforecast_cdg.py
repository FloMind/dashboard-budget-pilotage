"""
views/view_reforecast_cdg.py
Écran Reforecast CDG — saisie des hypothèses révisées.

Layout :
  Row 1 : Sélecteur site + note CDG
  Row 2 : Tableau de saisie mensuelle (budget | réel | reforecast editable)
  Row 3 : Graphique comparatif Budget vs Réel vs Reforecast vs Atterrissage
  Row 4 : Tableau récap tous sites
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from loader import DashboardData
from forecast import rolling_forecast
from reforecast_store import (
    load_reforecast, save_reforecast, set_reforecast_values,
    get_reforecast_note, get_monthly_reforecast, compute_reforecast_totals,
    has_reforecast, KPIS_REFORECAST, KPI_LABELS, DEFAULT_PATH,
)
from components.style import page_header, section_title, kpi_card, kpi_row, C
from components.charts import PLOTLY_THEME
from components.formatters import fmt_ke, fmt_pct

MOIS_LABELS = ["Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"]


def _forecast_chart_with_rfc(
    budget_m  : list,
    reel_m    : list,
    rfc_m     : list,
    att_m     : list,
    mois_reel : int,
    titre     : str,
    height    : int = 380,
) -> go.Figure:
    """Graphique comparatif Budget / Réel / Reforecast / Atterrissage."""
    x = MOIS_LABELS

    fig = go.Figure()
    fig.update_layout(**PLOTLY_THEME, title_text=titre, height=height,
                      barmode="overlay")

    # Budget
    fig.add_trace(go.Scatter(
        x=x, y=[v/1000 for v in budget_m],
        name="Budget", mode="lines",
        line=dict(color=C["slate"], dash="dot", width=1.5),
        hovertemplate="Budget %{x}: <b>%{y:.1f} K€</b><extra></extra>",
    ))

    # Réel (mois réalisés)
    reel_display = [v/1000 if i < mois_reel and v is not None else None
                    for i, v in enumerate(reel_m)]
    fig.add_trace(go.Scatter(
        x=x, y=reel_display,
        name="Réel", mode="lines+markers",
        line=dict(color=C["blue"], width=2.5),
        marker=dict(size=7, color=C["blue"], line=dict(color="white", width=1.5)),
        connectgaps=False,
        hovertemplate="Réel %{x}: <b>%{y:.1f} K€</b><extra></extra>",
    ))

    # Reforecast CDG
    rfc_display = [v/1000 for v in rfc_m]
    # Griser les mois réalisés (on les affiche mais en transparence)
    fig.add_trace(go.Scatter(
        x=x, y=rfc_display,
        name="Reforecast CDG", mode="lines+markers",
        line=dict(color="#7C3AED", width=2, dash="dashdot"),
        marker=dict(size=6, color="#7C3AED", symbol="diamond",
                    line=dict(color="white", width=1)),
        hovertemplate="RFC %{x}: <b>%{y:.1f} K€</b><extra></extra>",
    ))

    # Atterrissage algorithmique (mois futurs seulement)
    att_display = [None] * mois_reel + [v/1000 for v in att_m[mois_reel:]]
    if mois_reel > 0 and reel_m[mois_reel-1] is not None:
        # Pont entre réel et atterrissage
        att_display[mois_reel-1] = reel_m[mois_reel-1] / 1000
    fig.add_trace(go.Scatter(
        x=x, y=att_display,
        name="Atterrissage (algo)", mode="lines+markers",
        line=dict(color=C["amber"], width=1.5, dash="dash"),
        marker=dict(size=5, color=C["amber"]),
        connectgaps=False,
        hovertemplate="Atterrissage %{x}: <b>%{y:.1f} K€</b><extra></extra>",
    ))

    # Ligne verticale séparant réel / futur
    if 0 < mois_reel < 12:
        fig.add_vline(
            x=mois_reel - 0.5,
            line=dict(color="rgba(26,43,74,0.15)", dash="dash", width=1),
            annotation=dict(text="Aujourd'hui", font=dict(size=9, color=C["text_muted"]),
                           yanchor="top"),
        )

    fig.update_xaxes(**dict(PLOTLY_THEME["xaxis"]))
    fig.update_yaxes(**dict(PLOTLY_THEME["yaxis"]), ticksuffix=" K")
    return fig


def render(data: DashboardData) -> None:
    """Point d'entrée de la vue Reforecast CDG."""

    page_header(
        title    = "🔄 Reforecast CDG",
        subtitle = f"Révision budgétaire {data.annee} — hypothèses opérationnelles CDG",
        badges   = [f"{data.mois_reel} mois réalisés", f"{12 - data.mois_reel} mois à projeter"],
    )

    st.markdown("""
> **Budget** = objectif fixé en N-1, immuable.  
> **Reforecast** = révision formelle par le CDG, intégrant des hypothèses opérationnelles  
> (recrutement, appel d'offres, problème fournisseur résolu, travaux…).  
> **Atterrissage** = projection algorithmique (tendance + WLS), sans jugement CDG.
    """)

    if data.mois_reel == 12:
        st.info("L'exercice est clôturé — le reforecast n'est plus applicable.")
        return

    # Charger les données reforecast persistées
    rf_data = load_reforecast()

    st.divider()

    # ── 1. SAISIE PAR SITE ────────────────────────────────────────────────────
    section_title("Saisie des hypothèses révisées")

    col_site, col_kpi, _ = st.columns([2, 2, 3])
    with col_site:
        site_code = st.selectbox(
            "Site",
            options=data.sites,
            format_func=lambda x: data.df_sites.set_index("site_code").loc[x, "site_libelle"],
            key="rfc_site",
        )
    with col_kpi:
        kpi = st.selectbox(
            "KPI à réviser",
            options=KPIS_REFORECAST,
            format_func=lambda x: KPI_LABELS[x],
            key="rfc_kpi",
        )

    # Note CDG
    note_key    = f"rfc_note_{site_code}"
    note_actuelle = get_reforecast_note(rf_data, site_code)
    note = st.text_input(
        "Hypothèse / justification (optionnel)",
        value=st.session_state.get(note_key, note_actuelle),
        placeholder="Ex: Recrutement commercial Q4, appel d'offres Rydge, travaux terminés...",
        key=note_key,
    )

    # Récupérer budget et réel mensuels
    df_kpi = data.sig_mensuel[
        (data.sig_mensuel["site_code"] == site_code) &
        (data.sig_mensuel["kpi"] == kpi)
    ].sort_values("mois")

    budget_m = df_kpi["budget"].tolist()
    reel_m   = [
        float(v) if not (isinstance(v, float) and np.isnan(v)) else None
        for v in df_kpi["reel"].tolist()
    ]

    # Valeurs reforecast actuellement sauvegardées
    rfc_saved = rf_data.get("sites", {}).get(site_code, {}).get(kpi, {})

    # ── Tableau de saisie ─────────────────────────────────────────────────────
    st.markdown(f"**Révision mensuelle — {KPI_LABELS[kpi]} — {data.df_sites.set_index('site_code').loc[site_code, 'site_libelle']}**")
    st.caption("Saisissez les valeurs révisées pour les mois futurs. Les mois réalisés affichent le réel et ne sont pas modifiables.")

    # Construction du DataFrame d'édition
    rows = []
    for i, m in enumerate(range(1, 13)):
        is_realise = m <= data.mois_reel
        bgt = budget_m[i] / 1000
        rel = (reel_m[i] / 1000) if (not is_realise is False and reel_m[i] is not None) else None
        rfc_val = float(rfc_saved.get(str(m), budget_m[i])) / 1000 if not is_realise else None

        rows.append({
            "Mois"        : MOIS_LABELS[i],
            "Statut"      : "✓ Réalisé" if is_realise else "◷ Futur",
            "Budget K€"   : round(bgt, 1),
            "Réel K€"     : round(rel, 1) if rel is not None else None,
            "RFC K€"      : round(rfc_val, 1) if rfc_val is not None else None,
        })

    df_edit = pd.DataFrame(rows)

    # Séparer mois réalisés (lecture seule) et futurs (éditables)
    df_realise = df_edit[df_edit["Statut"] == "✓ Réalisé"].copy()
    df_futur   = df_edit[df_edit["Statut"] == "◷ Futur"].copy()

    col_tbl1, col_tbl2 = st.columns([1, 1], gap="large")

    with col_tbl1:
        st.markdown("**Mois réalisés (lecture seule)**")
        st.dataframe(
            df_realise[["Mois", "Budget K€", "Réel K€"]],
            use_container_width=True,
            hide_index=True,
            height=min(35 * len(df_realise) + 40, 380),
        )

    with col_tbl2:
        st.markdown("**Mois futurs — saisie reforecast**")
        if len(df_futur) == 0:
            st.info("Tous les mois sont réalisés.")
        else:
            df_edited = st.data_editor(
                df_futur[["Mois", "Budget K€", "RFC K€"]],
                use_container_width=True,
                hide_index=True,
                height=min(35 * len(df_futur) + 40, 380),
                column_config={
                    "Mois"      : st.column_config.TextColumn("Mois", disabled=True),
                    "Budget K€" : st.column_config.NumberColumn("Budget K€", disabled=True, format="%.1f"),
                    "RFC K€"    : st.column_config.NumberColumn("Reforecast K€", format="%.1f",
                                    help="Saisissez votre estimation révisée (K€)"),
                },
                key=f"rfc_editor_{site_code}_{kpi}",
            )

            # Bouton Sauvegarder
            if st.button("💾 Sauvegarder le reforecast", type="primary", key="rfc_save"):
                # Extraire les valeurs éditées
                mois_vals = {}
                for _, row in df_edited.iterrows():
                    m_idx  = MOIS_LABELS.index(row["Mois"]) + 1
                    val_ke = row["RFC K€"]
                    if val_ke is not None and not (isinstance(val_ke, float) and np.isnan(val_ke)):
                        mois_vals[m_idx] = float(val_ke) * 1000

                if mois_vals:
                    rf_data = set_reforecast_values(rf_data, site_code, kpi, mois_vals, note)
                    save_reforecast(rf_data)
                    st.success(f"✅ Reforecast {KPI_LABELS[kpi]} — {site_code} sauvegardé")
                    st.rerun()
                else:
                    st.warning("Aucune valeur saisie.")

    st.divider()

    # ── 2. GRAPHIQUE COMPARATIF ───────────────────────────────────────────────
    section_title("Budget vs Réel vs Reforecast vs Atterrissage")

    # Calculer atterrissage algorithmique
    r_algo = rolling_forecast(data, site_code, kpi, "hybride", n_sim=500)
    att_m  = r_algo.forecast_p50

    rfc_m = get_monthly_reforecast(
        rf_data, site_code, kpi, data.mois_reel, budget_m, reel_m
    )

    site_lib = data.df_sites.set_index("site_code").loc[site_code, "site_libelle"]
    fig = _forecast_chart_with_rfc(
        budget_m, reel_m, rfc_m, att_m,
        data.mois_reel,
        titre=f"{KPI_LABELS[kpi]} — {site_lib} — {data.annee}",
    )
    st.plotly_chart(fig, use_container_width=True, key="rfc_chart")

    # KPI cards comparaison
    ytd_reel  = sum(v for v in reel_m[:data.mois_reel] if v is not None)
    bgt_total = sum(budget_m)
    rfc_total = sum(rfc_m)
    att_total = r_algo.total_forecast

    kpi_row([
        kpi_card("BUDGET ANNUEL",  fmt_ke(bgt_total), color="slate"),
        kpi_card("RÉEL YTD",       fmt_ke(ytd_reel),  color="blue"),
        kpi_card(
            "REFORECAST CDG",
            fmt_ke(rfc_total),
            delta=fmt_ke(rfc_total - bgt_total) + " vs budget",
            favorable=rfc_total >= bgt_total,
            color="purple",
        ),
        kpi_card(
            "ATTERRISSAGE ALGO",
            fmt_ke(att_total),
            delta=fmt_ke(att_total - bgt_total) + " vs budget",
            favorable=att_total >= bgt_total,
            color="amber",
        ),
        kpi_card(
            "ÉCART RFC vs ALGO",
            fmt_ke(rfc_total - att_total),
            favorable=abs(rfc_total - att_total) < bgt_total * 0.03,
            color="green" if abs(rfc_total - att_total) < bgt_total * 0.03 else "red",
        ),
    ], n_cols=5)

    st.divider()

    # ── 3. TABLEAU RÉCAP RÉSEAU ───────────────────────────────────────────────
    section_title("Récapitulatif réseau — tous sites")

    rf_totals = compute_reforecast_totals(rf_data, data)

    rows_recap = []
    for sc in data.sites:
        site_l = data.df_sites.set_index("site_code").loc[sc, "site_libelle"]
        r      = rolling_forecast(data, sc, kpi, "hybride", n_sim=200)
        bgt_s  = r.total_budget
        rfc_s  = rf_totals[sc][kpi]
        att_s  = r.total_forecast
        ytd_s  = r.total_reel_ytd
        note_s = get_reforecast_note(rf_data, sc)

        rows_recap.append({
            "Site"            : site_l,
            "Budget K€"       : round(bgt_s / 1000, 1),
            "Réel YTD K€"     : round(ytd_s / 1000, 1),
            "Reforecast K€"   : round(rfc_s / 1000, 1),
            "Atterrissage K€" : round(att_s / 1000, 1),
            "Δ RFC vs Bgt"    : round((rfc_s - bgt_s) / 1000, 1),
            "Δ RFC vs Algo"   : round((rfc_s - att_s) / 1000, 1),
            "Note CDG"        : note_s if note_s else "—",
        })

    # Ligne consolidé
    bgt_tot_g  = sum(r["Budget K€"]       for r in rows_recap)
    ytd_tot_g  = sum(r["Réel YTD K€"]     for r in rows_recap)
    rfc_tot_g  = sum(r["Reforecast K€"]   for r in rows_recap)
    att_tot_g  = sum(r["Atterrissage K€"] for r in rows_recap)
    rows_recap.append({
        "Site"            : "GROUPE",
        "Budget K€"       : round(bgt_tot_g, 1),
        "Réel YTD K€"     : round(ytd_tot_g, 1),
        "Reforecast K€"   : round(rfc_tot_g, 1),
        "Atterrissage K€" : round(att_tot_g, 1),
        "Δ RFC vs Bgt"    : round(rfc_tot_g - bgt_tot_g, 1),
        "Δ RFC vs Algo"   : round(rfc_tot_g - att_tot_g, 1),
        "Note CDG"        : "",
    })

    df_recap = pd.DataFrame(rows_recap)

    def _style_delta(val):
        if isinstance(val, (int, float)):
            if val > 0:  return "color: #059669; font-weight: 600"
            if val < 0:  return "color: #DC2626; font-weight: 600"
        return ""

    st.dataframe(
        df_recap.style.map(_style_delta, subset=["Δ RFC vs Bgt", "Δ RFC vs Algo"]),
        use_container_width=True,
        hide_index=True,
        height=310,
        column_config={
            "Budget K€"       : st.column_config.NumberColumn(format="%.1f"),
            "Réel YTD K€"     : st.column_config.NumberColumn(format="%.1f"),
            "Reforecast K€"   : st.column_config.NumberColumn(format="%.1f"),
            "Atterrissage K€" : st.column_config.NumberColumn(format="%.1f"),
            "Δ RFC vs Bgt"    : st.column_config.NumberColumn("Δ vs Budget K€", format="%.1f"),
            "Δ RFC vs Algo"   : st.column_config.NumberColumn("Δ vs Algo K€",   format="%.1f"),
        },
    )

    # Avertissement si aucun reforecast saisi
    if not has_reforecast(rf_data):
        st.info(
            "ℹ️ Aucun reforecast saisi pour le moment. "
            "Les colonnes Reforecast affichent le budget par défaut. "
            "Saisissez vos hypothèses dans le tableau ci-dessus."
        )
