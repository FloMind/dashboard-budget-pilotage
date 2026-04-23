"""
app.py — FloMind Budget Dashboard
Point d'entrée Streamlit · v1.0
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import streamlit as st

st.set_page_config(
    page_title = "FloMind — Budget",
    page_icon  = "📊",
    layout     = "wide",
    initial_sidebar_state = "expanded",
)

from components.style import inject_css, sidebar_site_status, C
from loader import filter_to_mois
inject_css()

@st.cache_data(show_spinner="📂 Chargement…")
def get_data():
    from loader import load_data
    return load_data("data/sample_budget_v2.xlsx")

@st.cache_data
def get_filtered_data(mois_sel: int):
    return filter_to_mois(get_data(), mois_sel)

MOIS_LABELS = ["Jan","Fev","Mar","Avr","Mai","Jun","Jul","Aou","Sep","Oct","Nov","Dec"]

with st.sidebar:

    st.markdown(
        '<div style="padding:1.4rem 0.8rem 1.2rem;border-bottom:1px solid rgba(255,255,255,0.08);margin-bottom:0.75rem;">' +
        '<div style="font-size:0.62rem;font-weight:800;letter-spacing:0.22em;color:#60A5FA;text-transform:uppercase;line-height:1;">FloMind</div>' +
        '<div style="font-size:1.15rem;font-weight:700;color:#E2EAF6;letter-spacing:-0.01em;margin-top:0.15rem;line-height:1.2;">Budget<br>Dashboard</div>' +
        '<div style="font-size:0.65rem;color:#6B82A8;letter-spacing:0.05em;margin-top:0.35rem;">CDG &middot; DATA &middot; IA</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div style="font-size:0.62rem;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;' +
        'color:rgba(200,216,240,0.40);padding:0 0.6rem;margin-bottom:0.35rem;">Navigation</div>',
        unsafe_allow_html=True,
    )

    ECRANS = {
        "Tour de controle" : "tour",
        "Drill-down site"  : "drill",
        "Analyse des ecarts": "ecarts",
        "Rolling Forecast" : "forecast",
        "Reforecast CDG"   : "reforecast",
        "Guide d'utilisation": "aide",
    }
    ecran = ECRANS[st.radio(
        "nav",
        options=list(ECRANS.keys()),
        index=0,
        label_visibility="collapsed",
    )]

    try:
        data = get_data()

        mois_opts = {i: MOIS_LABELS[i-1] for i in range(1, data.mois_reel + 1)}
        mois_sel  = st.select_slider(
            "Periode d'analyse",
            options=list(mois_opts.keys()),
            value=data.mois_reel,
            format_func=lambda x: "Jan → " + mois_opts[x],
            key="mois_sel",
            help="Rejouer le dashboard a n'importe quel mois realise",
        )

        st.markdown(
            '<div style="margin:0.5rem 0;padding:0.7rem 0.6rem;background:rgba(255,255,255,0.04);' +
            'border-radius:8px;border:1px solid rgba(255,255,255,0.07);">' +
            '<div style="font-size:0.68rem;color:rgba(200,216,240,0.40);letter-spacing:0.08em;' +
            'text-transform:uppercase;margin-bottom:0.35rem;font-weight:600;">Exercice</div>' +
            f'<div style="font-size:0.82rem;color:#A8BCDA;line-height:1.9;">' +
            f'📅 {data.annee}<br>📆 Jan–{mois_opts[mois_sel]} analysé<br>' +
            f'🏪 {len(data.sites)} sites réseau<br>' +
            f'📋 {data.df["compte_code"].nunique()} comptes PCG</div></div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div style="font-size:0.62rem;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;' +
            'color:rgba(200,216,240,0.40);padding:0 0.6rem;margin:0.75rem 0 0.25rem;">Statut EBE YTD</div>',
            unsafe_allow_html=True,
        )

        data_sb = get_filtered_data(st.session_state.get("mois_sel", data.mois_reel))
        for sc in data.sites:
            ebe_r = float(data_sb.sig_ytd.loc[sc, "EBE_rel"])
            ebe_b = float(data_sb.sig_ytd.loc[sc, "EBE_bgt"])
            pct   = (ebe_r - ebe_b) / abs(ebe_b) * 100 if abs(ebe_b) > 1 else 0
            lib   = data.df_sites.set_index("site_code").loc[sc, "site_libelle"]
            sidebar_site_status(lib, pct)

    except FileNotFoundError:
        st.error("Fichier de données introuvable.")

    st.markdown(
        '<div style="position:fixed;bottom:0;left:0;width:230px;padding:0.8rem 1rem;' +
        'border-top:1px solid rgba(255,255,255,0.06);background:#1A2B4A;' +
        'font-size:0.62rem;color:#3D5278;line-height:1.6;">' +
        'FloMind Consulting<br>CDG &times; Data &times; IA pour PME' +
        '<br><span style="color:#2A3D5C;">v1.0 &middot; 2025</span></div>',
        unsafe_allow_html=True,
    )

try:
    data = get_data()
except FileNotFoundError:
    st.error("Fichier de données introuvable")
    st.stop()

mois_sel  = st.session_state.get("mois_sel", data.mois_reel)
data_view = get_filtered_data(mois_sel)

if ecran == "tour":
    from views.view_tour_de_controle import render
    render(data_view)
elif ecran == "drill":
    from views.view_drill_site import render
    render(data_view)
elif ecran == "ecarts":
    from views.view_ecarts import render
    render(data_view)
elif ecran == "forecast":
    from views.view_forecast import render
    render(data_view)
elif ecran == "reforecast":
    from views.view_reforecast_cdg import render
    render(data_view)
elif ecran == "aide":
    from views.view_aide import render
    render()
