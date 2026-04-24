"""
views/view_reforecast_cdg.py
Écran Reforecast CDG — Hypothèses typées + cascade SIG correcte
"""
from __future__ import annotations
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from loader import DashboardData
from forecast import rolling_forecast
from hypotheses_store import (
    HYPOTHESES_LIBRARY, KPIS_RFC, KPI_LABELS, MOIS_LABELS,
    load_hypotheses, save_hypotheses, add_hypothesis, delete_hypothesis,
    get_hypotheses_for_site, compute_all_hypotheses_impact,
    compute_hypothesis_monthly_impact, get_categorie_list,
    get_hypotheses_by_categorie,
)
from components.style import page_header, section_title, kpi_card, kpi_row, C, PLOTLY_THEME
from components.formatters import fmt_ke, fmt_pct


def _get_site_kpi_series(data, site_code, kpi):
    df_m = data.sig_mensuel[
        (data.sig_mensuel["site_code"] == site_code) &
        (data.sig_mensuel["kpi"] == kpi)
    ].sort_values("mois")
    budget_m = df_m["budget"].tolist()
    reel_m   = [
        float(v) if not (isinstance(v, float) and np.isnan(v)) else None
        for v in df_m["reel"].tolist()
    ]
    return budget_m, reel_m


def _get_taux_marge(data, site_code):
    try:
        ca = float(data.sig_ytd.loc[site_code, "CA_net_rel"])
        mc = float(data.sig_ytd.loc[site_code, "MC_rel"])
        if abs(ca) > 1:
            return mc / ca
    except Exception:
        pass
    return 0.38


def _get_budget_pers_serv(data, site_code):
    df_site = data.df[data.df["site_code"] == site_code]
    pers = (
        df_site[df_site["classe_cdg"] == "Charges personnel"]
        .groupby("mois")["montant_budget"].sum()
        .reindex(range(1, 13), fill_value=0.0).abs().tolist()
    )
    serv = (
        df_site[df_site["classe_cdg"].isin(["Services ext. 61", "Services ext. 62"])]
        .groupby("mois")["montant_budget"].sum()
        .reindex(range(1, 13), fill_value=0.0).abs().tolist()
    )
    return pers, serv


def _forecast_chart(budget_m, reel_m, rfc_m, att_m, mois_reel, titre, height=400):
    x = MOIS_LABELS
    fig = go.Figure()
    fig.update_layout(**PLOTLY_THEME, title_text=titre, height=height)

    fig.add_trace(go.Scatter(
        x=x, y=[v/1000 for v in budget_m], name="Budget", mode="lines",
        line=dict(color=C["slate"], dash="dot", width=1.5),
        hovertemplate="Budget %{x}: <b>%{y:.1f} K€</b><extra></extra>",
    ))

    reel_display = [v/1000 if i < mois_reel and v is not None else None
                    for i, v in enumerate(reel_m)]
    fig.add_trace(go.Scatter(
        x=x, y=reel_display, name="Réel", mode="lines+markers",
        line=dict(color=C["blue"], width=2.5),
        marker=dict(size=7, color=C["blue"], line=dict(color="white", width=1.5)),
        connectgaps=False,
        hovertemplate="Réel %{x}: <b>%{y:.1f} K€</b><extra></extra>",
    ))

    rfc_display = [None] * mois_reel + [v/1000 for v in rfc_m[mois_reel:]]
    if mois_reel > 0 and reel_m[mois_reel - 1] is not None:
        rfc_display[mois_reel - 1] = reel_m[mois_reel - 1] / 1000
    fig.add_trace(go.Scatter(
        x=x, y=rfc_display, name="Reforecast CDG", mode="lines+markers",
        line=dict(color="#7C3AED", width=2.2, dash="dashdot"),
        marker=dict(size=6, color="#7C3AED", symbol="diamond",
                    line=dict(color="white", width=1)),
        connectgaps=False,
        hovertemplate="RFC %{x}: <b>%{y:.1f} K€</b><extra></extra>",
    ))

    att_display = [None] * mois_reel + [v/1000 for v in att_m[mois_reel:]]
    if mois_reel > 0 and reel_m[mois_reel - 1] is not None:
        att_display[mois_reel - 1] = reel_m[mois_reel - 1] / 1000
    fig.add_trace(go.Scatter(
        x=x, y=att_display, name="Atterrissage (algo)", mode="lines+markers",
        line=dict(color=C["amber"], width=1.5, dash="dash"),
        marker=dict(size=5, color=C["amber"]),
        connectgaps=False,
        hovertemplate="Atterrissage %{x}: <b>%{y:.1f} K€</b><extra></extra>",
    ))

    if 0 < mois_reel < 12:
        fig.add_vline(
            x=mois_reel - 0.5,
            line=dict(color="rgba(26,43,74,0.15)", dash="dash", width=1),
            annotation=dict(text="Aujourd'hui", font=dict(size=9, color=C["text_muted"]),
                            yanchor="top"),
        )
    fig.update_yaxes(ticksuffix=" K")
    return fig


def render(data: DashboardData) -> None:
    page_header(
        title    = "🔄 Reforecast CDG",
        subtitle = f"Révision budgétaire {data.annee} — 58 hypothèses typées avec cascade CA→MC→VA→EBE",
        badges   = [f"{data.mois_reel} mois réalisés", f"{12 - data.mois_reel} mois à projeter"],
    )

    st.markdown("""\
> **Budget** = objectif N-1, immuable.  
> **Reforecast** = révision CDG par hypothèses opérationnelles → impact calculé en cascade SIG.  
> **Atterrissage** = projection algorithmique (tendance + WLS).
    """)

    if data.mois_reel == 12:
        st.info("Exercice clôturé — reforecast non applicable.")
        return

    hyp_data = load_hypotheses()

    col_site, col_kpi, _ = st.columns([2, 2, 3])
    with col_site:
        site_code = st.selectbox(
            "Site", options=data.sites,
            format_func=lambda x: data.df_sites.set_index("site_code").loc[x, "site_libelle"],
            key="rfc_site",
        )
    with col_kpi:
        kpi = st.selectbox(
            "KPI à analyser", options=KPIS_RFC,
            format_func=lambda x: KPI_LABELS[x], key="rfc_kpi",
        )

    site_lib = data.df_sites.set_index("site_code").loc[site_code, "site_libelle"]
    st.divider()

    budget_ca_m, reel_ca_m   = _get_site_kpi_series(data, site_code, "CA_net")
    budget_kpi_m, reel_kpi_m = _get_site_kpi_series(data, site_code, kpi)
    taux_marge               = _get_taux_marge(data, site_code)
    budget_pers_m, budget_serv_m = _get_budget_pers_serv(data, site_code)

    impact_cumul = compute_all_hypotheses_impact(
        hyp_data, site_code, budget_ca_m, taux_marge,
        budget_pers_m, budget_serv_m, data.mois_reel,
    )

    rfc_kpi_m = []
    for i in range(12):
        m = i + 1
        if m <= data.mois_reel and reel_kpi_m[i] is not None:
            rfc_kpi_m.append(reel_kpi_m[i])
        else:
            rfc_kpi_m.append(budget_kpi_m[i] + impact_cumul[kpi][i])

    r_algo   = rolling_forecast(data, site_code, kpi, "hybride", n_sim=300)
    att_kpi_m = r_algo.forecast_p50

    tab1, tab2, tab3, tab4 = st.tabs([
        "➕ Ajouter une hypothèse",
        "📋 Hypothèses actives",
        "📊 Graphique comparatif",
        "🌐 Récap réseau",
    ])

    # ── TAB 1 — AJOUTER ──────────────────────────────────────────────────────
    with tab1:
        section_title("Bibliothèque d'hypothèses")
        st.caption(
            "58 hypothèses typées · 5 catégories · "
            "Cascade automatique CA → MC → VA → EBE selon le type"
        )

        col_cat, col_type = st.columns([2, 3])
        with col_cat:
            categorie = st.selectbox("Catégorie", options=get_categorie_list(), key="rfc_cat")
        hyps_cat = get_hypotheses_by_categorie(categorie)
        with col_type:
            type_id = st.selectbox(
                "Type d'hypothèse",
                options=list(hyps_cat.keys()),
                format_func=lambda x: hyps_cat[x]["label"],
                key="rfc_type",
            )

        hyp_lib = HYPOTHESES_LIBRARY[type_id]
        st.info(f"ℹ️ {hyp_lib['description']}")

        cascade_str = " → ".join(hyp_lib["kpis_impactes"])
        st.markdown(f"**Impact cascade :** `{cascade_str}`")
        st.markdown("---")

        st.markdown("**Paramètres**")
        param_vals = {}
        n_params = len(hyp_lib["params"])
        cols_params = st.columns(min(n_params, 4))

        for idx, pdef in enumerate(hyp_lib["params"]):
            col = cols_params[idx % len(cols_params)]
            key_p  = f"rfc_p_{type_id}_{pdef['key']}"
            label_p = f"{pdef['label']} ({pdef['unit']})" if pdef.get("unit") else pdef["label"]
            help_p  = pdef.get("help", "") or None

            with col:
                if pdef["type"] == "mois":
                    dv = pdef.get("default") or (data.mois_reel + 1)
                    dv = max(data.mois_reel + 1, min(int(dv), 12))
                    opts = list(range(data.mois_reel + 1, 13))
                    if not opts:
                        st.caption("Tous les mois sont réalisés.")
                        val = 12
                    else:
                        val = st.selectbox(
                            label_p, options=opts,
                            format_func=lambda x: MOIS_LABELS[x - 1],
                            index=max(0, dv - data.mois_reel - 1),
                            key=key_p, help=help_p,
                        )
                elif pdef["type"] in ("pct", "pct_signe", "float", "float_signe"):
                    dv = float(pdef.get("default") or 0)
                    val = st.number_input(
                        label_p,
                        min_value=float(pdef.get("min", -9999)),
                        max_value=float(pdef.get("max", 9999)),
                        value=dv, step=0.1, key=key_p, help=help_p,
                    )
                else:
                    dv = int(pdef.get("default") or 0)
                    val = st.number_input(
                        label_p,
                        min_value=int(pdef.get("min", 0)),
                        max_value=int(pdef.get("max", 9999)),
                        value=dv, key=key_p, help=help_p,
                    )
                param_vals[pdef["key"]] = val

        col_lbl, col_note = st.columns(2)
        with col_lbl:
            label_libre = st.text_input("Libellé personnalisé (optionnel)",
                                        placeholder=hyp_lib["label"],
                                        key=f"rfc_label_{type_id}")
        with col_note:
            note_libre = st.text_input("Justification / contexte (optionnel)",
                                       key=f"rfc_note_{type_id}")

        # Prévisualisation
        st.markdown("**Prévisualisation de l'impact**")
        preview = compute_hypothesis_monthly_impact(
            {"type_id": type_id, "params": param_vals},
            budget_ca_m, taux_marge, budget_pers_m, budget_serv_m, data.mois_reel,
        )
        prev_rows = []
        for kpi_p in KPIS_RFC:
            total = sum(preview[kpi_p])
            if abs(total) > 0.01:
                row = {"KPI": KPI_LABELS[kpi_p]}
                for i, d in enumerate(preview[kpi_p]):
                    row[MOIS_LABELS[i]] = f"{d/1000:+.1f}" if d != 0 else "—"
                row["TOTAL"] = f"{total/1000:+.1f} K€"
                prev_rows.append(row)

        if prev_rows:
            st.dataframe(pd.DataFrame(prev_rows), use_container_width=True,
                         hide_index=True, height=160)
        else:
            st.caption("Aucun impact sur les mois futurs avec ces paramètres.")

        if st.button("✅ Ajouter cette hypothèse", type="primary", key="rfc_add"):
            hyp_data = add_hypothesis(
                hyp_data, type_id, site_code, param_vals,
                label=label_libre, note=note_libre,
            )
            save_hypotheses(hyp_data)
            st.success(f"✅ Ajoutée : {label_libre or hyp_lib['label']}")
            st.rerun()

    # ── TAB 2 — HYPOTHÈSES ACTIVES ───────────────────────────────────────────
    with tab2:
        hyps_site = get_hypotheses_for_site(hyp_data, site_code)
        section_title(f"Hypothèses actives — {site_lib}")

        if not hyps_site:
            st.info("Aucune hypothèse pour ce site. Utilisez l'onglet '➕ Ajouter'.")
        else:
            for hyp in hyps_site:
                lib_h     = HYPOTHESES_LIBRARY.get(hyp["type_id"], {})
                cascade   = " → ".join(lib_h.get("kpis_impactes", []))
                impact_h  = compute_hypothesis_monthly_impact(
                    hyp, budget_ca_m, taux_marge,
                    budget_pers_m, budget_serv_m, data.mois_reel,
                )
                total_kpi = sum(impact_h.get(kpi, [0]*12))

                with st.expander(
                    f"**{hyp['label']}** · Impact {kpi} : {total_kpi/1000:+.1f} K€",
                    expanded=False,
                ):
                    c1, c2 = st.columns([5, 1])
                    with c1:
                        st.markdown(f"**Type** : {lib_h.get('label','')} · **Cascade** : `{cascade}`")
                        if hyp.get("note"):
                            st.markdown(f"**Note** : {hyp['note']}")
                        st.caption(f"Params : {hyp['params']} · Ajoutée {hyp.get('created_at','')[:10]}")
                    with c2:
                        if st.button("🗑️", key=f"del_{hyp['uuid']}"):
                            hyp_data = delete_hypothesis(hyp_data, hyp["uuid"])
                            save_hypotheses(hyp_data)
                            st.rerun()

        st.divider()
        all_hyps = hyp_data.get("hypotheses", [])
        section_title("Toutes hypothèses — réseau complet")
        if all_hyps:
            _rows_all = []
            for h in all_hyps:
                lib_h = HYPOTHESES_LIBRARY.get(h["type_id"], {})
                _rows_all.append({
                    "Site": h["site_code"],
                    "Catégorie": lib_h.get("categorie","").split(" ",1)[-1],
                    "Hypothèse": h["label"],
                    "Note": h.get("note","—"),
                    "Ajoutée": h.get("created_at","")[:10],
                })
            st.dataframe(pd.DataFrame(_rows_all), use_container_width=True,
                         hide_index=True, height=250)
            if st.button("🗑️ Tout effacer (réseau)", type="secondary"):
                hyp_data["hypotheses"] = []
                save_hypotheses(hyp_data)
                st.rerun()
        else:
            st.info("Aucune hypothèse sur le réseau.")

    # ── TAB 3 — GRAPHIQUE ────────────────────────────────────────────────────
    with tab3:
        nb_hyps = len(get_hypotheses_for_site(hyp_data, site_code))
        if nb_hyps == 0:
            st.warning("Aucune hypothèse → Reforecast CDG = Budget. Ajoutez des hypothèses via '➕'.")

        fig = _forecast_chart(
            budget_kpi_m, reel_kpi_m, rfc_kpi_m, att_kpi_m, data.mois_reel,
            titre=f"{KPI_LABELS[kpi]} — {site_lib} — {data.annee}",
        )
        st.plotly_chart(fig, use_container_width=True, key="rfc_chart_hyp")

        ytd_reel  = sum(v for v in reel_kpi_m[:data.mois_reel] if v is not None)
        bgt_total = sum(budget_kpi_m)
        rfc_total = sum(rfc_kpi_m)
        att_total = r_algo.total_forecast

        kpi_row([
            kpi_card("BUDGET ANNUEL",    fmt_ke(bgt_total),  color="slate"),
            kpi_card("RÉEL YTD",         fmt_ke(ytd_reel),   color="blue"),
            kpi_card("REFORECAST CDG",   fmt_ke(rfc_total),
                     delta=fmt_ke(rfc_total - bgt_total) + " vs budget",
                     favorable=rfc_total >= bgt_total, color="purple"),
            kpi_card("ATTERRISSAGE ALGO", fmt_ke(att_total),
                     delta=fmt_ke(att_total - bgt_total) + " vs budget",
                     favorable=att_total >= bgt_total, color="amber"),
            kpi_card("ÉCART RFC vs ALGO", fmt_ke(rfc_total - att_total),
                     favorable=abs(rfc_total - att_total) < abs(bgt_total) * 0.03,
                     color="green" if abs(rfc_total - att_total) < abs(bgt_total) * 0.03 else "red"),
        ], n_cols=5)

        hyps_site_d = get_hypotheses_for_site(hyp_data, site_code)
        if hyps_site_d:
            st.divider()
            section_title("Décomposition des hypothèses actives")
            detail_rows = []
            for hyp in hyps_site_d:
                imp = compute_hypothesis_monthly_impact(
                    hyp, budget_ca_m, taux_marge,
                    budget_pers_m, budget_serv_m, data.mois_reel,
                )
                lib_h = HYPOTHESES_LIBRARY.get(hyp["type_id"], {})
                detail_rows.append({
                    "Hypothèse"        : hyp["label"],
                    "Cascade"          : " → ".join(lib_h.get("kpis_impactes", [])),
                    f"Impact {kpi} K€" : round(sum(imp[kpi]) / 1000, 1),
                    "Note"             : hyp.get("note", "—"),
                })
            df_d = pd.DataFrame(detail_rows)

            def _ci(val):
                if isinstance(val, (int, float)):
                    if val > 0: return "color:#059669;font-weight:600"
                    if val < 0: return "color:#DC2626;font-weight:600"
                return ""

            st.dataframe(df_d.style.map(_ci, subset=[f"Impact {kpi} K€"]),
                         use_container_width=True, hide_index=True, height=220)

    # ── TAB 4 — RÉCAP RÉSEAU ─────────────────────────────────────────────────
    with tab4:
        section_title(f"Récapitulatif réseau — {KPI_LABELS[kpi]}")
        recap_rows = []
        for sc in data.sites:
            site_l   = data.df_sites.set_index("site_code").loc[sc, "site_libelle"]
            bca_m, _ = _get_site_kpi_series(data, sc, "CA_net")
            bkpi_m, rkpi_m = _get_site_kpi_series(data, sc, kpi)
            tm       = _get_taux_marge(data, sc)
            bp_m, bs_m = _get_budget_pers_serv(data, sc)
            imp = compute_all_hypotheses_impact(
                hyp_data, sc, bca_m, tm, bp_m, bs_m, data.mois_reel,
            )
            rfc_sc = [
                rkpi_m[i] if (i+1 <= data.mois_reel and rkpi_m[i] is not None)
                else bkpi_m[i] + imp[kpi][i]
                for i in range(12)
            ]
            r_sc  = rolling_forecast(data, sc, kpi, "hybride", n_sim=200)
            bgt_s = sum(bkpi_m)
            ytd_s = sum(v for v in rkpi_m[:data.mois_reel] if v is not None)
            rfc_s = sum(rfc_sc)
            att_s = r_sc.total_forecast
            recap_rows.append({
                "Site"            : site_l,
                "Budget K€"       : round(bgt_s/1000, 1),
                "Réel YTD K€"     : round(ytd_s/1000, 1),
                "Reforecast K€"   : round(rfc_s/1000, 1),
                "Atterrissage K€" : round(att_s/1000, 1),
                "Δ RFC vs Bgt"    : round((rfc_s - bgt_s)/1000, 1),
                "Δ RFC vs Algo"   : round((rfc_s - att_s)/1000, 1),
                "Hyp."            : len(get_hypotheses_for_site(hyp_data, sc)),
            })

        bgt_g = sum(r["Budget K€"]     for r in recap_rows)
        rfc_g = sum(r["Reforecast K€"] for r in recap_rows)
        att_g = sum(r["Atterrissage K€"] for r in recap_rows)
        recap_rows.append({
            "Site": "GROUPE",
            "Budget K€": round(bgt_g, 1),
            "Réel YTD K€": round(sum(r["Réel YTD K€"] for r in recap_rows), 1),
            "Reforecast K€": round(rfc_g, 1),
            "Atterrissage K€": round(att_g, 1),
            "Δ RFC vs Bgt": round(rfc_g - bgt_g, 1),
            "Δ RFC vs Algo": round(rfc_g - att_g, 1),
            "Hyp.": sum(r["Hyp."] for r in recap_rows[:-1] if isinstance(r.get("Hyp."), int)),
        })

        df_recap = pd.DataFrame(recap_rows)

        def _sd(val):
            if isinstance(val, (int, float)):
                if val > 0: return "color:#059669;font-weight:600"
                if val < 0: return "color:#DC2626;font-weight:600"
            return ""

        st.dataframe(
            df_recap.style.map(_sd, subset=["Δ RFC vs Bgt", "Δ RFC vs Algo"]),
            use_container_width=True, hide_index=True, height=330,
            column_config={
                "Budget K€"       : st.column_config.NumberColumn(format="%.1f"),
                "Réel YTD K€"     : st.column_config.NumberColumn(format="%.1f"),
                "Reforecast K€"   : st.column_config.NumberColumn(format="%.1f"),
                "Atterrissage K€" : st.column_config.NumberColumn(format="%.1f"),
                "Δ RFC vs Bgt"    : st.column_config.NumberColumn("Δ vs Budget K€", format="%.1f"),
                "Δ RFC vs Algo"   : st.column_config.NumberColumn("Δ vs Algo K€",   format="%.1f"),
            },
        )
