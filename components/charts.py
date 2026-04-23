"""
components/charts.py
Constructeurs Plotly — version avec design system FloMind unifié.
Tous les graphiques utilisent PLOTLY_THEME de style.py.
"""
from __future__ import annotations
from typing import Dict, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from components.formatters import fmt_ke, mois_label
from components.style import PLOTLY_THEME, C


def _fig(**kwargs) -> go.Figure:
    """Crée une Figure avec le layout de base FloMind."""
    fig = go.Figure()
    layout = {**PLOTLY_THEME, **kwargs}
    fig.update_layout(**layout)
    return fig


def _apply_axes(fig, xaxis=None, yaxis=None):
    """Applique les overrides d'axes sur une figure existante."""
    if xaxis:
        base = dict(PLOTLY_THEME["xaxis"])
        base.update(xaxis)
        fig.update_xaxes(**base)
    if yaxis:
        base = dict(PLOTLY_THEME["yaxis"])
        base.update(yaxis)
        fig.update_yaxes(**base)
    return fig


# ════════════════════════════════════════════════════════════════════════════
# 1. WATERFALL
# ════════════════════════════════════════════════════════════════════════════

def waterfall_chart(wf_data: Dict, titre: str = "Budget → Réel", height: int = 380) -> go.Figure:
    """
    Waterfall Budget → drivers par classe CDG → Réel.

    Implémenté avec go.Bar empilées (base transparente + barre visible)
    car go.Waterfall n'a plus de propriété 'marker' en Plotly 6.x.
    Cela donne un contrôle complet sur la couleur de chaque barre.
    """
    drivers   = wf_data["drivers"]
    total_bgt = wf_data["total_bgt"]
    total_rel = wf_data["total_rel"]
    ecart     = wf_data["ecart_total"]

    df_d = drivers[drivers["contribution"].abs() > 1].copy()

    noms    = ["Budget"] + df_d["classe_cdg"].tolist() + ["Réel"]
    mesures = ["absolute"] + ["relative"] * len(df_d) + ["total"]
    valeurs = [total_bgt] + df_d["contribution"].tolist() + [total_rel]
    textes  = [fmt_ke(v) for v in valeurs]

    # Calculer les bases et hauteurs pour le stacked bar waterfall
    bases, heights, couleurs = [], [], []
    cumul = 0.0
    for nom, mesure, val in zip(noms, mesures, valeurs):
        if mesure == "absolute":
            bases.append(0)
            heights.append(val)
            couleurs.append(C["slate"])     # Budget → gris
            cumul = val
        elif mesure == "relative":
            if val >= 0:
                bases.append(cumul)
                heights.append(val)
                couleurs.append(C["green"]) # Favorable → vert
            else:
                bases.append(cumul + val)
                heights.append(-val)
                couleurs.append(C["red"])   # Défavorable → rouge
            cumul += val
        elif mesure == "total":
            bases.append(0)
            heights.append(cumul)
            couleurs.append(C["blue"] if cumul >= 0 else C["red"])  # Réel → bleu

    fig = _fig(title_text=titre, height=height, showlegend=False,
               barmode="stack")

    # Barre transparente (base invisible)
    fig.add_trace(go.Bar(
        x=noms, y=bases,
        marker=dict(color="rgba(0,0,0,0)", line=dict(width=0)),
        showlegend=False, hoverinfo="skip",
    ))

    # Barre visible (la vraie valeur)
    fig.add_trace(go.Bar(
        x=noms, y=heights,
        marker=dict(color=couleurs, line=dict(width=0)),
        text=textes,
        textposition="outside",
        textfont=dict(color=C["text_muted"], size=10, family="JetBrains Mono, monospace"),
        hovertemplate="<b>%{x}</b><br>%{text}<extra></extra>",
        showlegend=False,
    ))

    _apply_axes(fig,
        xaxis=dict(tickfont=dict(size=10, color=C["text_muted"])),
        yaxis=dict(showticklabels=False, showgrid=False),
    )
    return fig


# ════════════════════════════════════════════════════════════════════════════
# 2. HEATMAP
# ════════════════════════════════════════════════════════════════════════════

def heatmap_chart(pivot: pd.DataFrame, titre: str = "Écart % vs budget",
                  seuil: float = 50.0, height: int = 240) -> go.Figure:
    """Heatmap multi-sites × mois."""
    z = pivot.values.clip(-seuil, seuil)
    x = [mois_label(m) for m in pivot.columns]
    y = pivot.index.tolist()

    text = []
    for row in pivot.values:
        text.append([("" if pd.isna(v) else f"{v:+.0f}%") for v in row])

    colorscale = [
        [0.00, "#7F1D1D"],   # rouge foncé
        [0.25, C["red"]],
        [0.45, "#1C2D45"],   # neutre foncé
        [0.50, "#1C2D45"],
        [0.55, "#1C2D45"],
        [0.75, C["green"]],
        [1.00, "#065F46"],   # vert foncé
    ]

    fig = _fig(title_text=titre, height=height)
    fig.add_trace(go.Heatmap(
        z            = z,
        x            = x,
        y            = y,
        text         = text,
        texttemplate = "%{text}",
        textfont     = dict(size=10, color="white", family="JetBrains Mono, monospace"),
        colorscale   = colorscale,
        zmin         = -seuil,
        zmax         = seuil,
        showscale    = True,
        colorbar     = dict(
            title    = dict(text="Écart %", font=dict(color=C["text_muted"], size=9)),
            tickfont = dict(color=C["text_muted"], size=9),
            len      = 0.8,
            thickness= 12,
            bgcolor  = "rgba(0,0,0,0)",
        ),
        hoverongaps = False,
        hovertemplate = "<b>%{y}</b> — %{x}<br>Écart : %{text}<extra></extra>",
    ))
    fig.update_layout(xaxis=dict(side="top"))
    return fig


# ════════════════════════════════════════════════════════════════════════════
# 3. COURBES MENSUELLES
# ════════════════════════════════════════════════════════════════════════════

def monthly_comparison_chart(df_evol: pd.DataFrame, kpi_label: str = "CA net",
                             height: int = 320) -> go.Figure:
    """Budget (pointillé gris) vs Réel (bleu plein), séparateur vertical."""
    x   = df_evol["mois_label"].tolist()
    fig = _fig(title_text=f"{kpi_label} — Budget vs Réel", height=height,
               yaxis=dict(ticksuffix=" K", tickformat=",.0f"))

    # Budget
    fig.add_trace(go.Scatter(
        x=x, y=df_evol["budget"],
        name="Budget", mode="lines+markers",
        line=dict(color=C["slate"], dash="dot", width=1.5),
        marker=dict(size=4, color=C["slate"]),
        hovertemplate="Budget %{x}: <b>%{customdata}</b><extra></extra>",
        customdata=[fmt_ke(v) for v in df_evol["budget"]],
    ))

    # Réel
    df_r = df_evol[df_evol["est_realise"]]
    if len(df_r):
        fig.add_trace(go.Scatter(
            x=df_r["mois_label"].tolist(), y=df_r["reel"].tolist(),
            name="Réel", mode="lines+markers",
            line=dict(color=C["blue"], width=2.5),
            marker=dict(size=7, color=C["blue"],
                        line=dict(color=C["surface"], width=2)),
            hovertemplate="Réel %{x}: <b>%{customdata}</b><extra></extra>",
            customdata=[fmt_ke(v) for v in df_r["reel"]],
        ))

    mr = int(df_evol[df_evol["est_realise"]]["mois"].max()) if len(df_r) else 0
    if 0 < mr < 12:
        fig.add_vline(
            x=mr - 0.5,
            line=dict(color=C["border_hover"], dash="dash", width=1),
            annotation=dict(text="Aujourd'hui", font=dict(size=9, color=C["text_muted"]),
                           yanchor="top"),
        )
    _apply_axes(fig, yaxis=dict(tickformat=",.0f", ticksuffix=" K"))
    return fig


# ════════════════════════════════════════════════════════════════════════════
# 4. FORECAST
# ════════════════════════════════════════════════════════════════════════════

def forecast_chart(df_fc: pd.DataFrame, kpi_label: str = "CA net",
                   height: int = 400) -> go.Figure:
    """Budget + Réel + P50 + bande P10-P90."""
    x       = df_fc["mois_label"].tolist()
    df_reel = df_fc[~df_fc["is_forecast"]]
    df_fore = df_fc[df_fc["is_forecast"]]

    fig = _fig(title_text=f"{kpi_label} — Rolling Forecast", height=height)

    # Budget
    fig.add_trace(go.Scatter(
        x=x, y=df_fc["budget"],
        name="Budget", mode="lines",
        line=dict(color=C["slate"], dash="dot", width=1.5),
        hovertemplate="Budget %{x}: <b>%{customdata}</b><extra></extra>",
        customdata=[fmt_ke(v) for v in df_fc["budget"]],
    ))

    if len(df_fore):
        xf = df_fore["mois_label"].tolist()
        # P90 (borne haute — invisible, sert de fill target)
        fig.add_trace(go.Scatter(
            x=xf, y=df_fore["forecast_p90"].tolist(),
            mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip",
        ))
        # P10 (borne basse — fill vers P90)
        fig.add_trace(go.Scatter(
            x=xf, y=df_fore["forecast_p10"].tolist(),
            name="P10–P90",
            mode="lines", line=dict(width=0),
            fill="tonexty",
            fillcolor="rgba(255,176,32,0.10)",
            hovertemplate="P10 %{x}: <b>%{customdata}</b><extra></extra>",
            customdata=[fmt_ke(v) for v in df_fore["forecast_p10"]],
        ))

    # Réel
    if len(df_reel):
        fig.add_trace(go.Scatter(
            x=df_reel["mois_label"].tolist(), y=df_reel["reel"].tolist(),
            name="Réel", mode="lines+markers",
            line=dict(color=C["blue"], width=2.5),
            marker=dict(size=7, color=C["blue"],
                        line=dict(color=C["surface"], width=2)),
            hovertemplate="Réel %{x}: <b>%{customdata}</b><extra></extra>",
            customdata=[fmt_ke(v) for v in df_reel["reel"]],
        ))

    # P50 — pont réel → forecast
    if len(df_fore):
        x_pont, y_pont = [], []
        if len(df_reel):
            x_pont.append(df_reel.iloc[-1]["mois_label"])
            y_pont.append(float(df_reel.iloc[-1]["reel"]))
        x_pont += df_fore["mois_label"].tolist()
        y_pont += df_fore["forecast_p50"].tolist()

        fig.add_trace(go.Scatter(
            x=x_pont, y=y_pont,
            name="Forecast P50",
            mode="lines+markers",
            line=dict(color=C["amber"], width=2, dash="dashdot"),
            marker=dict(size=5, color=C["amber"],
                        line=dict(color=C["surface"], width=1.5)),
            hovertemplate="Forecast %{x}: <b>%{customdata}</b><extra></extra>",
            customdata=[fmt_ke(v) for v in y_pont],
        ))

    if len(df_reel):
        mr_label = df_reel.iloc[-1]["mois_label"]
        fig.add_vline(
            x=mr_label,
            line=dict(color=C["border_hover"], dash="dash", width=1),
        )

    _apply_axes(fig, yaxis=dict(tickformat=",.0f", ticksuffix=" K"))
    return fig


# ════════════════════════════════════════════════════════════════════════════
# 5. BARRES HORIZONTALES ÉCARTS
# ════════════════════════════════════════════════════════════════════════════

def ecarts_bar_chart(df_ecarts: pd.DataFrame, n: int = 10,
                     height: int = 360, titre: str = "Top dérives YTD") -> go.Figure:
    """Barres horizontales des N écarts les plus importants."""
    df = df_ecarts.head(n).copy()
    df["label"] = df["compte_libelle"].str[:32] + " (" + df["site_code"] + ")"
    df = df.sort_values("ecart_impact")

    couleurs = [C["green"] if v > 0 else C["red"] for v in df["ecart_impact"]]

    fig = _fig(title_text=titre, height=max(height, len(df) * 34 + 80),
               showlegend=False)
    fig.add_trace(go.Bar(
        x=df["ecart"] / 1000,
        y=df["label"],
        orientation="h",
        marker=dict(
            color=couleurs,
            line=dict(width=0),
            cornerradius=4,
        ),
        text=[fmt_ke(v) for v in df["ecart"]],
        textposition="outside",
        textfont=dict(size=10, color=C["text_muted"], family="JetBrains Mono, monospace"),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Écart : %{x:.1f} K€<br>"
            "Budget : %{customdata[0]}<br>"
            "Réel   : %{customdata[1]}<extra></extra>"
        ),
        customdata=list(zip(
            [fmt_ke(v) for v in df["budget"]],
            [fmt_ke(v) for v in df["reel"]],
        )),
    ))
    _apply_axes(fig,
        xaxis=dict(ticksuffix=" K", zeroline=True,
                   zerolinecolor="rgba(255,255,255,0.06)", zerolinewidth=1),
    )
    return fig


# ════════════════════════════════════════════════════════════════════════════
# 6. DONUT CONTRIBUTION RÉSEAU
# ════════════════════════════════════════════════════════════════════════════

def donut_contribution(df_contrib: pd.DataFrame, titre: str = "Part CA réseau",
                       height: int = 260) -> go.Figure:
    """Anneau de contribution par site."""
    df = df_contrib[df_contrib["valeur"] > 0].copy()

    blues = ["#5B8BFF","#3D6FEF","#2A57D1","#7AA5FF","#9DBFFF","#1A3CA8","#C2D8FF"]
    colors = blues[:len(df)]

    fig = _fig(title_text=titre, height=height, showlegend=False)
    fig.add_trace(go.Pie(
        labels   = df["site_libelle"],
        values   = df["valeur"],
        hole     = 0.58,
        marker   = dict(colors=colors, line=dict(color=C["surface"], width=2)),
        textinfo = "label+percent",
        textfont = dict(size=10, color=C["text"], family="Inter, sans-serif"),
        hovertemplate = "<b>%{label}</b><br>%{customdata}<br>%{percent}<extra></extra>",
        customdata     = [fmt_ke(v) for v in df["valeur"]],
    ))
    # Texte central
    ca_total = df["valeur"].sum()
    fig.add_annotation(
        text   = f"<b>{fmt_ke(ca_total)}</b>",
        x=0.5, y=0.5,
        showarrow = False,
        font      = dict(size=13, color=C["text"], family="JetBrains Mono, monospace"),
    )
    return fig
