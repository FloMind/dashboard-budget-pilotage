"""
components/formatters.py
Fonctions de formatage partagées entre toutes les vues.
Convention : montants en € → affichage en K€ ou M€ selon magnitude.
"""
from __future__ import annotations
from typing import Optional


def fmt_ke(val: float, decimals: int = 1, suffix: str = " K€") -> str:
    """Formate un montant en K€. Ex : 45600 → '45.6 K€'."""
    if val is None:
        return "—"
    k = val / 1_000
    fmt = f"{k:,.{decimals}f}".replace(",", " ")
    return f"{fmt}{suffix}"


def fmt_me(val: float, decimals: int = 2, suffix: str = " M€") -> str:
    """Formate un montant en M€. Ex : 4200000 → '4.20 M€'."""
    if val is None:
        return "—"
    m = val / 1_000_000
    fmt = f"{m:,.{decimals}f}".replace(",", " ")
    return f"{fmt}{suffix}"


def fmt_pct(val: float, decimals: int = 1, force_sign: bool = True) -> str:
    """Formate un pourcentage. Ex : 5.3 → '+5.3%', -2.1 → '-2.1%'."""
    if val is None:
        return "—"
    sign = "+" if force_sign and val > 0 else ""
    return f"{sign}{val:.{decimals}f}%"


def fmt_ecart_ke(val: float, decimals: int = 1) -> str:
    """Formate un écart en K€ avec signe. Ex : 1200 → '+1.2 K€'."""
    if val is None:
        return "—"
    sign = "+" if val > 0 else ""
    return f"{sign}{val/1000:,.{decimals}f} K€".replace(",", " ")


def delta_str(val: float, decimals: int = 1) -> str:
    """Retourne la chaîne delta pour st.metric. Ex : 2.3 → '+2.3%'."""
    if val is None:
        return None
    return fmt_pct(val, decimals)


def delta_color(ecart_val: float, est_produit: bool = True) -> str:
    """
    Retourne la couleur delta Streamlit selon le sens de l'écart.
    Pour un produit : écart positif = vert (normal).
    Pour une charge : écart positif = rouge (inverse — plus de charges = mauvais).
    """
    if ecart_val is None or ecart_val == 0:
        return "off"
    if est_produit:
        return "normal"      # vert si positif
    else:
        return "inverse"     # rouge si positif (plus de charges)


def priorite_label(p: int) -> str:
    """Retourne le badge emoji de priorité d'alerte."""
    return {1: "🔴 Critique", 2: "🟠 Important", 3: "🟡 Surveillance"}.get(p, "⚪")


def sens_label(est_favorable: bool) -> str:
    """Retourne le symbole d'impact favorable/défavorable."""
    return "✅" if est_favorable else "🔴"


def mois_label(mois: int) -> str:
    """Retourne le label court d'un mois (1 → 'Jan')."""
    labels = {
        1:"Jan",2:"Fév",3:"Mar",4:"Avr",5:"Mai",6:"Jun",
        7:"Jul",8:"Aoû",9:"Sep",10:"Oct",11:"Nov",12:"Déc",
    }
    return labels.get(mois, str(mois))


def cadence_label_long(mois_reel: int) -> str:
    """Label cadence lisible DG. Ex : 4 → 'Cadence 4+8 (Avr 2025)'."""
    restants = 12 - mois_reel
    mois     = mois_label(mois_reel)
    return f"Cadence {mois_reel}+{restants} — clôturé à {mois}"
