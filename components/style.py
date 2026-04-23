"""
components/style.py
══════════════════════════════════════════════════════════════════════════════
FloMind Budget Dashboard — Système de design

Contenu :
  1. inject_css()          → CSS global injecté dans app.py
  2. kpi_card()            → carte KPI HTML custom (remplace st.metric)
  3. kpi_row()             → ligne de cartes KPI
  4. page_header()         → en-tête de page avec titre + sous-titre
  5. section_title()       → titre de section (h3 stylé)
  6. badge()               → badge coloré inline
  7. alert_summary()       → résumé alertes coloré
  8. PLOTLY_THEME          → template Plotly unifié

Philosophie de design FloMind :
  • "Premium financial terminal" — deep navy, pas gris générique
  • Chiffres en tabular-nums pour l'alignement
  • Border-top colorée par type de KPI (signature visuelle)
  • Vert/rouge stricts pour favorable/défavorable — jamais ambigus
  • Inter pour le texte, JetBrains Mono pour les valeurs numériques
══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations
from typing import Optional
import streamlit as st

# ════════════════════════════════════════════════════════════════════════════
# PALETTE — source unique de vérité pour tous les fichiers Python
# ════════════════════════════════════════════════════════════════════════════

C = {
    # Fonds light
    "bg"          : "#F4F7FC",
    "surface"     : "#FFFFFF",
    "surface_2"   : "#EBF0FB",
    "surface_3"   : "#DDE5F5",

    # Bordures légères
    "border"      : "rgba(26,43,74,0.10)",
    "border_hover": "rgba(26,43,74,0.20)",
    "border_focus": "rgba(37,99,235,0.4)",

    # Texte dark-on-light
    "text"        : "#1A2B4A",
    "text_muted"  : "#5B7098",
    "text_dim"    : "#94A3B8",

    # Accents sémantiques
    "blue"        : "#2563EB",
    "blue_dim"    : "rgba(37,99,235,0.10)",
    "green"       : "#059669",
    "green_dim"   : "rgba(5,150,105,0.10)",
    "red"         : "#DC2626",
    "red_dim"     : "rgba(220,38,38,0.10)",
    "amber"       : "#D97706",
    "amber_dim"   : "rgba(217,119,6,0.10)",
    "slate"       : "#94A3B8",
    "purple"      : "#7C3AED",

    # Types KPI → border-top
    "kpi_ca"      : "#2563EB",
    "kpi_mc"      : "#059669",
    "kpi_ebe"     : "#D97706",
    "kpi_rex"     : "#7C3AED",
    "kpi_att"     : "#0891B2",
    "kpi_neutral" : "#94A3B8",
}
# ════════════════════════════════════════════════════════════════════════════
# CSS GLOBAL
# ════════════════════════════════════════════════════════════════════════════

_CSS = """
/* ── Polices ───────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Variables CSS (miroir de la palette Python) ───────────────────────── */
:root {
    --bg          : #F4F7FC;
    --surface     : #FFFFFF;
    --surface-2   : #EBF0FB;
    --surface-3   : #DDE5F5;
    --border      : rgba(26,43,74,0.10);
    --border-h    : rgba(26,43,74,0.20);
    --text        : #1A2B4A;
    --text-muted  : #5B7098;
    --text-dim    : #94A3B8;
    --blue        : #2563EB;
    --green       : #059669;
    --red         : #DC2626;
    --amber       : #D97706;
    --slate       : #94A3B8;
    --radius      : 10px;
    --radius-sm   : 6px;
    --radius-lg   : 14px;
    --trans       : 0.18s ease;
}
/* ── Base ───────────────────────────────────────────────────────────────── */
* { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }

html, body, .stApp {
    background: var(--bg) !important;
    color: var(--text);
}

.block-container {
    padding: 1.25rem 2rem 3rem 2rem !important;
    max-width: 100% !important;
}

/* ── Header Streamlit ───────────────────────────────────────────────────── */
header[data-testid="stHeader"] {
    background: var(--bg) !important;
    border-bottom: 1px solid var(--border);
    backdrop-filter: blur(8px);
}
/* Cache le bouton hamburger et le menu par défaut */
[data-testid="stToolbar"] { display: none !important; }

/* ── Sidebar ────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: #1A2B4A !important;
    border-right: none !important;
    width: 230px !important;
}
[data-testid="stSidebar"] > div:first-child {
    padding-top: 0 !important;
}

/* Navigation radio — style custom ─────────────────────── */
[data-testid="stSidebar"] .stRadio > label {
    font-size: 0.72rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-dim);
    padding: 0.2rem 0;
    font-weight: 500;
}
[data-testid="stSidebar"] .stRadio [data-testid="stWidgetLabel"] {
    font-size: 0.72rem;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: rgba(200,216,240,0.5);
}
[data-testid="stSidebar"] .stRadio [role="radiogroup"] {
    gap: 2px;
}
[data-testid="stSidebar"] .stRadio [role="radio"] + div {
    font-size: 0.88rem;
    font-weight: 400;
    color: var(--text-muted);
    padding: 0.5rem 0.75rem;
    border-radius: var(--radius-sm);
    transition: background var(--trans), color var(--trans);
    cursor: pointer;
}
[data-testid="stSidebar"] .stRadio [aria-checked="true"] + div {
    background: rgba(96,165,250,0.18);
    color: #60A5FA;
    font-weight: 500;
}

/* ── Dividers ─────────────────────────────────────────────────────────── */
hr {
    border: none;
    border-top: 1px solid var(--border) !important;
    margin: 1rem 0 !important;
}

/* ── Metrics Streamlit natifs (fallback si st.metric est utilisé) ───────── */
[data-testid="stMetric"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-top: 2px solid var(--blue);
    border-radius: var(--radius);
    padding: 0.9rem 1.1rem 0.8rem;
    transition: border-color var(--trans), box-shadow var(--trans);
}
[data-testid="stMetric"]:hover {
    border-color: var(--border-h);
    box-shadow: 0 4px 20px rgba(26,43,74,0.12);
}
[data-testid="stMetricLabel"] {
    font-size: 0.72rem !important;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-muted) !important;
    font-weight: 500;
}
[data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', 'Inter', monospace !important;
    font-variant-numeric: tabular-nums;
    font-size: 1.5rem !important;
    font-weight: 600 !important;
    color: var(--text) !important;
    letter-spacing: -0.02em;
    line-height: 1.2;
}
[data-testid="stMetricDelta"] {
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    margin-top: 0.2rem;
}
[data-testid="stMetricDelta"] [data-testid="stMetricDeltaIcon-Up"] + div { color: var(--green) !important; }
[data-testid="stMetricDelta"] [data-testid="stMetricDeltaIcon-Down"] + div { color: var(--red) !important; }

/* ── Dataframes ─────────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border-radius: var(--radius) !important;
    overflow: hidden;
    border: 1px solid var(--border) !important;
}
[data-testid="stDataFrame"] > div {
    border-radius: var(--radius);
}

/* ── Selectbox, sliders ─────────────────────────────────────────────────── */
[data-testid="stSelectbox"] > div > div {
    background: var(--surface-2) !important;
    border-color: var(--border) !important;
    border-radius: var(--radius-sm) !important;
    transition: border-color var(--trans);
}
[data-testid="stSelectbox"] > div > div:hover {
    border-color: var(--border-h) !important;
}

/* ── Expanders ──────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    margin-bottom: 0.5rem;
    box-shadow: 0 1px 3px rgba(26,43,74,0.06);
}
[data-testid="stExpander"]:hover {
    border-color: var(--border-h) !important;
}
[data-testid="stExpander"] summary {
    font-size: 0.88rem;
    font-weight: 500;
    color: var(--text-muted);
    padding: 0.7rem 1rem;
}

/* ── Boutons ────────────────────────────────────────────────────────────── */
[data-testid="stBaseButton-secondary"] {
    background: var(--surface-2) !important;
    border: 1px solid var(--border) !important;
    color: var(--text-muted) !important;
    font-size: 0.84rem !important;
    font-weight: 500 !important;
    border-radius: var(--radius-sm) !important;
    transition: background var(--trans), border-color var(--trans), color var(--trans);
}
[data-testid="stBaseButton-secondary"]:hover {
    background: var(--surface-3) !important;
    border-color: var(--border-h) !important;
    color: var(--text) !important;
}

/* ── TextArea / Zone commentaire ────────────────────────────────────────── */
textarea {
    background: var(--surface-2) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text) !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.88rem !important;
    resize: vertical;
    transition: border-color var(--trans);
}
textarea:focus {
    border-color: var(--blue) !important;
    box-shadow: 0 0 0 3px rgba(91,139,255,0.15) !important;
    outline: none !important;
}

/* ── Plotly charts ──────────────────────────────────────────────────────── */
.js-plotly-plot, .plotly {
    border-radius: var(--radius) !important;
    overflow: hidden;
}
.modebar {
    background: rgba(12,22,37,0.7) !important;
    border-radius: var(--radius-sm) !important;
}
.modebar-btn path { fill: var(--text-muted) !important; }
.modebar-btn:hover path { fill: var(--text) !important; }

/* ── Tooltips Plotly ────────────────────────────────────────────────────── */
.hoverlayer .hovertext {
    background: var(--surface-2) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text) !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 12px !important;
    box-shadow: 0 8px 30px rgba(0,0,0,0.5) !important;
}

/* ── Scrollbar custom ───────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--surface-3); border-radius: 10px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb:hover { background: var(--slate); }

/* ── Spinner ────────────────────────────────────────────────────────────── */
[data-testid="stSpinner"] { color: var(--blue) !important; }

/* ── Success / Error messages ───────────────────────────────────────────── */
[data-testid="stNotification"] {
    border-radius: var(--radius) !important;
    border: 1px solid var(--border) !important;
}

/* ── KPI Cards HTML custom ──────────────────────────────────────────────── */
.fm-kpi-row {
    display: grid;
    gap: 1rem;
    margin-bottom: 1.25rem;
}
.fm-kpi-row-5 { grid-template-columns: repeat(5, 1fr); }
.fm-kpi-row-4 { grid-template-columns: repeat(4, 1fr); }
.fm-kpi-row-6 { grid-template-columns: repeat(6, 1fr); }
.fm-kpi-row-3 { grid-template-columns: repeat(3, 1fr); }

.fm-kpi {
    background: var(--surface);
    border: 1px solid var(--border);
    border-top: 2px solid var(--slate);
    border-radius: var(--radius);
    padding: 1rem 1.15rem 0.85rem;
    box-shadow: 0 1px 4px rgba(26,43,74,0.07);
    transition: border-color var(--trans), box-shadow var(--trans), transform var(--trans);
    position: relative;
    overflow: hidden;
}
.fm-kpi:hover {
    border-color: var(--border-h);
    box-shadow: 0 4px 16px rgba(26,43,74,0.12);
    transform: translateY(-1px);
}

/* Variantes couleur border-top */
.fm-kpi-blue   { border-top-color: var(--blue) !important; }
.fm-kpi-green  { border-top-color: var(--green) !important; }
.fm-kpi-amber  { border-top-color: var(--amber) !important; }
.fm-kpi-red    { border-top-color: var(--red) !important; }
.fm-kpi-purple { border-top-color: #8B5CF6 !important; }
.fm-kpi-cyan   { border-top-color: #06B6D4 !important; }

.fm-kpi-label {
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 0.4rem;
    line-height: 1;
}
.fm-kpi-value {
    font-family: 'JetBrains Mono', 'Inter', monospace;
    font-variant-numeric: tabular-nums;
    font-size: 1.55rem;
    font-weight: 600;
    color: var(--text);
    letter-spacing: -0.03em;
    line-height: 1.15;
    margin-bottom: 0.35rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.fm-kpi-delta {
    font-size: 0.76rem;
    font-weight: 500;
    color: var(--text-muted);
    display: flex;
    align-items: center;
    gap: 0.3rem;
    line-height: 1;
}
.fm-kpi-delta.favorable  { color: var(--green); }
.fm-kpi-delta.defavorable { color: var(--red); }
.fm-kpi-delta.neutral    { color: var(--text-muted); }
.fm-kpi-arrow { font-size: 0.65rem; }
.fm-kpi-sub {
    font-size: 0.68rem;
    color: var(--text-dim);
    margin-top: 0.25rem;
    font-variant-numeric: tabular-nums;
}

/* ── Section header ─────────────────────────────────────────────────────── */
.fm-section {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-muted);
    border-left: 2.5px solid var(--blue);
    padding-left: 0.6rem;
    margin-bottom: 0.75rem;
    line-height: 1;
}

/* ── Badges ──────────────────────────────────────────────────────────────── */
.fm-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 0.2rem 0.55rem;
    border-radius: 20px;
    letter-spacing: 0.03em;
}
.fm-badge-blue   { background: rgba(91,139,255,0.12); color: #7FAAFF; }
.fm-badge-green  { background: rgba(0,196,140,0.12);  color: #00C48C; }
.fm-badge-red    { background: rgba(255,69,101,0.12); color: #FF7090; }
.fm-badge-amber  { background: rgba(255,176,32,0.12); color: #FFB020; }
.fm-badge-gray   { background: rgba(74,85,104,0.20);  color: #8A9BB5; }

/* ── Page header ────────────────────────────────────────────────────────── */
.fm-page-title {
    font-size: 1.35rem;
    font-weight: 700;
    color: var(--text);
    letter-spacing: -0.02em;
    line-height: 1.25;
}
.fm-page-subtitle {
    font-size: 0.8rem;
    color: var(--text-muted);
    margin-top: 0.2rem;
    font-weight: 400;
}

/* ── Sidebar status dots ────────────────────────────────────────────────── */
.fm-site-status {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.28rem 0.6rem;
    border-radius: var(--radius-sm);
    font-size: 0.74rem;
    color: rgba(200,216,240,0.70);
    transition: background var(--trans);
    cursor: default;
}
.fm-site-status:hover { background: rgba(255,255,255,0.04); }
.fm-site-status-name { font-weight: 400; }
.fm-site-status-val  {
    font-family: 'JetBrains Mono', monospace;
    font-variant-numeric: tabular-nums;
    font-size: 0.72rem;
    font-weight: 500;
}
.fm-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
    margin-right: 0.4rem;
}
.fm-dot-green  { background: var(--green); box-shadow: 0 0 5px var(--green); }
.fm-dot-amber  { background: var(--amber); box-shadow: 0 0 5px var(--amber); }
.fm-dot-red    { background: var(--red);   box-shadow: 0 0 5px var(--red); }
.fm-dot-gray   { background: var(--slate); }
"""


def inject_css() -> None:
    """Injecte la feuille de styles globale FloMind dans l'application Streamlit."""
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# COMPOSANTS HTML
# ════════════════════════════════════════════════════════════════════════════

def kpi_card(
    label    : str,
    value    : str,
    delta    : Optional[str]  = None,
    sub      : Optional[str]  = None,
    favorable: Optional[bool] = None,   # True=vert, False=rouge, None=neutre
    color    : str            = "blue",  # "blue"|"green"|"amber"|"red"|"purple"|"cyan"
) -> str:
    """
    Génère le HTML d'une carte KPI FloMind.

    Paramètres
    ----------
    label     : titre de la carte (en majuscules, court)
    value     : valeur principale affichée en grand (ex. "1 434.9 K€")
    delta     : ligne secondaire (ex. "+2.3% vs budget")
    sub       : ligne tertiaire discrète (ex. "Budget: 1 445.9 K€")
    favorable : None=neutre, True=vert, False=rouge
    color     : couleur de la border-top

    Retourne
    --------
    str : fragment HTML à passer dans st.markdown(unsafe_allow_html=True)
    """
    delta_class = "neutral"
    if favorable is True:
        delta_class = "favorable"
    elif favorable is False:
        delta_class = "defavorable"

    arrow = ""
    if favorable is True:
        arrow = '<span class="fm-kpi-arrow">▲</span>'
    elif favorable is False:
        arrow = '<span class="fm-kpi-arrow">▼</span>'

    delta_html = ""
    if delta:
        delta_html = f'<div class="fm-kpi-delta {delta_class}">{arrow}{delta}</div>'

    sub_html = f'<div class="fm-kpi-sub">{sub}</div>' if sub else ""

    return (
        f'<div class="fm-kpi fm-kpi-{color}">'
        f'<div class="fm-kpi-label">{label}</div>'
        f'<div class="fm-kpi-value">{value}</div>'
        + delta_html
        + sub_html
        + '</div>'
    )


def kpi_row(cards: list[str], n_cols: int = 5) -> None:
    """
    Affiche une rangée de cartes KPI dans une grille CSS.

    Paramètres
    ----------
    cards  : liste de strings HTML produits par kpi_card()
    n_cols : nombre de colonnes (3, 4 ou 5)
    """
    inner = "".join(cards)
    html  = f'<div class="fm-kpi-row fm-kpi-row-{n_cols}">{inner}</div>'
    st.markdown(html, unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "", badges: list[str] = None) -> None:
    """
    En-tête de page avec titre, sous-titre et badges optionnels.

    Exemple
    -------
    page_header("Tour de contrôle", "Exercice 2025 · Cadence 4+8", ["🟢 7 sites"])
    """
    badges_html = ""
    if badges:
        badges_items = "".join(f'<span class="fm-badge fm-badge-gray">{b}</span>' for b in badges)
        badges_html  = f'<div style="display:flex;gap:0.5rem;margin-top:0.5rem;flex-wrap:wrap;">{badges_items}</div>'

    html_ph = (
        f'<div style="margin-bottom:1.25rem;">'
        f'<div class="fm-page-title">{title}</div>'
        + (f'<div class="fm-page-subtitle">{subtitle}</div>' if subtitle else '')
        + badges_html
        + '</div>'
    )
    st.markdown(html_ph, unsafe_allow_html=True)


def section_title(text: str) -> None:
    """Titre de section avec barre verticale bleue — remplace st.markdown('**...**')."""
    st.markdown(f'<div class="fm-section">{text}</div>', unsafe_allow_html=True)


def badge(text: str, color: str = "gray") -> str:
    """
    Retourne le HTML d'un badge inline.

    Paramètres
    ----------
    text  : contenu du badge
    color : "blue"|"green"|"red"|"amber"|"gray"
    """
    return f'<span class="fm-badge fm-badge-{color}">{text}</span>'


def alert_summary_html(total: int, critiques: int, importants: int, sites: list) -> str:
    """HTML du résumé d'alertes pour la sidebar ou l'en-tête tour de contrôle."""
    if total == 0:
        return badge("✓ Aucune alerte", "green")
    parts = []
    if critiques  : parts.append(badge(f"● {critiques} critique{'s' if critiques>1 else ''}", "red"))
    if importants : parts.append(badge(f"● {importants} important{'s' if importants>1 else ''}", "amber"))
    rest = total - critiques - importants
    if rest       : parts.append(badge(f"{rest} surveillance", "gray"))
    return " ".join(parts)


def sidebar_site_status(
    site_libelle: str,
    ecart_pct   : float,
    valeur_str  : str = "",
) -> None:
    """Affiche un indicateur de statut de site dans la sidebar."""
    if ecart_pct > 3:
        dot_class, val_color = "fm-dot-green", C["green"]
    elif ecart_pct > -5:
        dot_class, val_color = "fm-dot-amber", C["amber"]
    else:
        dot_class, val_color = "fm-dot-red", C["red"]

    sign = "+" if ecart_pct > 0 else ""
    pct_str = f"{sign}{ecart_pct:.0f}%"

    st.markdown(
        f'<div class="fm-site-status">'
        f'<div style="display:flex;align-items:center;">'
        f'<div class="fm-dot {dot_class}"></div>'
        f'<span class="fm-site-status-name">{site_libelle[:18]}</span>'
        f'</div>'
        f'<span class="fm-site-status-val" style="color:{val_color};">{pct_str}</span>'
        f'</div>',
        unsafe_allow_html=True
    )


# ════════════════════════════════════════════════════════════════════════════
# TEMPLATE PLOTLY UNIFIÉ
# ════════════════════════════════════════════════════════════════════════════

PLOTLY_THEME = dict(
    paper_bgcolor = "rgba(0,0,0,0)",
    plot_bgcolor  = "rgba(0,0,0,0)",
    font = dict(
        family = "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
        color  = "#1A2B4A",
        size   = 12,
    ),
    title = dict(
        font  = dict(size=13, color="#5B7098", weight=600),
        x     = 0,
        xanchor = "left",
        pad   = dict(l=0, t=0),
    ),
    legend = dict(
        bgcolor     = "rgba(12,22,37,0.6)",
        bordercolor = "rgba(255,255,255,0.07)",
        borderwidth = 1,
        font        = dict(size=11, color="#5B7098"),
        orientation = "h",
        yanchor     = "bottom",
        y           = 1.02,
        xanchor     = "right",
        x           = 1,
    ),
    margin = dict(l=12, r=12, t=36, b=12),
    xaxis  = dict(
        gridcolor   = "rgba(26,43,74,0.07)",
        zeroline    = False,
        showline    = False,
        tickfont    = dict(color="#94A3B8", size=11),
        title_font  = dict(color="#94A3B8"),
    ),
    yaxis  = dict(
        gridcolor   = "rgba(26,43,74,0.07)",
        zeroline    = False,
        showline    = False,
        tickfont    = dict(color="#94A3B8", size=11),
        title_font  = dict(color="#94A3B8"),
    ),
    hoverlabel = dict(
        bgcolor     = "#1A2B4A",
        bordercolor = "rgba(255,255,255,0.10)",
        font        = dict(family="Inter, sans-serif", size=12, color="#FFFFFF"),
    ),
    colorway = [
        "#94A3B8",   # slate — budget
        "#2563EB",   # blue  — réel
        "#D97706",   # amber — forecast
        "#059669",   # green — favorable
        "#DC2626",   # red   — défavorable
        "#7C3AED",   # purple
        "#0891B2",   # cyan
    ],
)
