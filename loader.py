"""
core/loader.py
══════════════════════════════════════════════════════════════════════════════
FloMind Budget Dashboard — Couche d'accès et de structuration des données

RÔLE DANS L'ARCHITECTURE
─────────────────────────
Ce module est la **seule** porte d'entrée vers les données brutes.
Aucune vue Streamlit, aucun module de calcul ne lit directement l'Excel.
Ce principe garantit :
  • La cohérence : une seule logique de transformation, appliquée partout.
  • La testabilité : les vues s'appuient sur des DataFrames documentés.
  • La portabilité : changer la source de données (BDD, API) ne nécessite
    que de modifier ce module.

PIPELINE DE TRAITEMENT (exécuté dans load_data())
───────────────────────────────────────────────────
  1. Lecture des 3 onglets Excel (data, ref_sites, ref_comptes)
  2. Cast des types (conversions silencieuses + avertissements)
  3. Validation du schéma (colonnes requises, valeurs légales)
  4. Détection automatique du mois courant (dernier mois avec réel)
  5. Enrichissement du df principal (colonnes dérivées : écart, %, bool)
  6. Calcul des SIG à 3 granularités (annuel, YTD, mensuel)
  7. Enrichissement du référentiel sites (KPIs budgétaires clés)
  8. Construction de la liste ordonnée des sites (par CA décroissant)

CONVENTION DE SIGNE COMPTABLE
──────────────────────────────
  Toutes les valeurs stockées dans df respectent la convention comptable :
    • Produits (CA, reprises, produits financiers…)  → montants POSITIFS
    • Charges (achats, personnel, dotations…)         → montants NÉGATIFS
    • Correctifs produits (RRR accordés 709x)         → montants NÉGATIFS
    • Correctifs charges  (RRR obtenus  609x)         → montants POSITIFS

  Cette convention permet de calculer tout solde par simple somme :
    Résultat = Σ montants  (sans logique conditionnelle)
    EBE      = Σ montants des classes [Produits, Achats, Serv.61, Serv.62,
                                        Autres produits, Impôts, Personnel]

STRUCTURE DU FICHIER EXCEL ATTENDU
────────────────────────────────────
  Onglet "data"       : table atomique grain (site × mois × compte)
  Onglet "ref_sites"  : référentiel des sites (7 lignes, 6 colonnes)
  Onglet "ref_comptes": plan comptable PCG 2025 (96 lignes, 7 colonnes)

USAGE TYPIQUE DANS UNE VUE STREAMLIT
──────────────────────────────────────
  import streamlit as st
  from core.loader import load_data, get_top_ecarts

  @st.cache_data
  def get_data():
      return load_data("data/sample_budget_v2.xlsx")

  data = get_data()

  # Accès direct aux DataFrames pré-calculés
  df_site   = data.df[data.df["site_code"] == "LYO_C"]
  sig_annuel = data.sig_annuel          # SIG budget annuel par site
  sig_ytd   = data.sig_ytd             # YTD réel vs budget par site

  # Helpers
  top10 = get_top_ecarts(data, site_code="BGR", n=10)

DÉPENDANCES
────────────
  numpy  >= 1.24
  pandas >= 2.0

AUTEUR    : FloMind Consulting
CRÉÉ LE   : 2025
══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


# ══════════════════════════════════════════════════════════════════════════════
# SCHÉMAS DE VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

# Colonnes obligatoires par onglet, avec leur type cible après cast.
# Clé   = nom de la colonne tel qu'il apparaît dans l'Excel
# Valeur = dtype cible ("object" = chaîne, "int64" = entier, "float64" = décimal)
#
# Note : "float64" pour montant_reel permet de stocker NaN (pas de valeur entière
# qui supporte nativement NaN en pandas sans Int64 nullable).

_COLS_DATA: Dict[str, str] = {
    "site_code"      : "object",   # Code site (ex. "LYO_C")
    "site_libelle"   : "object",   # Libellé long (ex. "Lyon Centre")
    "annee"          : "int64",    # Exercice fiscal (ex. 2025)
    "mois"           : "int64",    # Mois 1–12
    "mois_label"     : "object",   # Label court (ex. "Jan", "Fév")
    "compte_code"    : "object",   # Code PCG (ex. "641100")
    "compte_libelle" : "object",   # Libellé du compte
    "classe_cdg"     : "object",   # Classe analytique (ex. "Charges personnel")
    "sous_classe"    : "object",   # Sous-groupe (ex. "Salaires")
    "sig_etape"      : "object",   # Étape SIG (ex. "EBE", "REX")
    "sens"           : "int64",    # +1 = produit / -1 = charge
    "ordre_affichage": "int64",    # Ordre dans le P&L (pour les tris)
    "montant_budget" : "float64",  # Budget mensuel (signé)
    "montant_reel"   : "float64",  # Réel mensuel (signé, NaN si non réalisé)
}

_COLS_SITES: Dict[str, str] = {
    "site_code"     : "object",    # Clé primaire (ex. "LYO_C")
    "site_libelle"  : "object",    # Nom complet (ex. "Lyon Centre")
    "departement"   : "object",    # Département + code (ex. "Rhône (69)")
    "type_site"     : "object",    # "Principal" ou "Secondaire"
    "date_ouverture": "object",    # Date ISO (ex. "2018-03-01")
    "responsable"   : "object",    # Nom du directeur de site
}

_COLS_COMPTES: Dict[str, str] = {
    "compte_code"    : "object",   # Numéro PCG (ex. "641100")
    "compte_libelle" : "object",   # Libellé officiel PCG
    "classe_cdg"     : "object",   # Regroupement analytique CDG
    "sous_classe"    : "object",   # Sous-regroupement
    "sig_etape"      : "object",   # Étape SIG à laquelle ce compte contribue
    "sens"           : "int64",    # +1 produit / -1 charge (convention signe)
    "ordre_affichage": "int64",    # Ordre d'affichage dans le P&L
}


# ══════════════════════════════════════════════════════════════════════════════
# MAPPING SIG
# ══════════════════════════════════════════════════════════════════════════════

# Définition des classes analytiques participant à chaque solde intermédiaire.
# La logique de calcul est : SIG = Σ(montants des classes listées)
# Les montants étant signés, l'addition directe donne le bon résultat.
#
# Exemple : EBE = Produits(+) + Achats(-) + Serv61(-) + Serv62(-) +
#                 Autres_produits(+) + Impôts(-) + Personnel(-)
# Ce qui équivaut à : EBE = MC - Serv_ext + Subv - Impôts - Personnel

_SIG_CLASSES: Dict[str, Optional[List[str]]] = {
    # Marge Commerciale = Ventes - Coût d'achat des marchandises vendues
    "MC": [
        "Produits",
        "Achats",
    ],
    # Valeur Ajoutée = MC - Consommations de l'exercice provenant des tiers
    "VA": [
        "Produits",
        "Achats",
        "Services ext. 61",   # Locations, entretien, assurances
        "Services ext. 62",   # Honoraires, transport, déplacements, IT
    ],
    # Excédent Brut d'Exploitation = VA + Subv - Impôts/taxes - Personnel
    "EBE": [
        "Produits", "Achats",
        "Services ext. 61", "Services ext. 62",
        "Autres produits",   # Subventions, refacturations
        "Impôts et taxes",   # CFE, TICPE, taxes RH (déjà négatifs)
        "Charges personnel", # Salaires + charges sociales (déjà négatifs)
    ],
    # Résultat d'Exploitation = EBE + Reprises - Dotations - Autres charges
    "REX": [
        "Produits", "Achats",
        "Services ext. 61", "Services ext. 62",
        "Autres produits",
        "Impôts et taxes", "Charges personnel",
        "Autres charges",    # PDC, pénalités (déjà négatifs)
        "Dotations",         # Amortissements, provisions (déjà négatifs)
        "Reprises",          # Reprises sur provisions (positifs)
    ],
    # Résultat Courant Avant Impôts = REX + Produits fin - Charges fin
    "RCAI": [
        "Produits", "Achats",
        "Services ext. 61", "Services ext. 62",
        "Autres produits",
        "Impôts et taxes", "Charges personnel",
        "Autres charges", "Dotations", "Reprises",
        "Produits financiers",    # Escomptes obtenus, placements
        "Charges financières",    # Intérêts emprunts, agios
    ],
    # Résultat Net = RCAI + Exceptionnel - IS - Participation
    # None signifie : toutes les classes (somme totale du P&L)
    "RN": None,
}

# Ordre canonique d'affichage des classes dans le P&L vertical.
# Utilisé pour garantir la cohérence visuelle entre tous les écrans.
CLASSE_ORDER: List[str] = [
    "Produits",               # Chiffre d'affaires net (VTE - RRR + ports)
    "Achats",                 # CAMV net (achats - RRR + frais appro)
    "Services ext. 61",       # Locations, entretien, assurances
    "Services ext. 62",       # Honoraires, transport, pub, IT
    "Autres produits",        # Subventions, ristournes, refacturations
    "Impôts et taxes",        # CFE, TICPE, taxes RH
    "Charges personnel",      # Masse salariale + charges sociales
    "Autres charges",         # PDC, pénalités commerciales
    "Dotations",              # Amortissements + provisions
    "Reprises",               # Reprises sur amortissements/provisions
    "Produits financiers",    # Escomptes, placements
    "Charges financières",    # Intérêts emprunts, agios
    "Produits exceptionnels", # Cessions, produits hors exploitation
    "Charges exceptionnelles",# Amendes, VCN cessions
    "IS et participation",    # Impôt sur les bénéfices, participation
]


# ══════════════════════════════════════════════════════════════════════════════
# DATACLASS DE SORTIE
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class DashboardData:
    """
    Conteneur principal des données structurées, exposé aux vues Streamlit.

    Ce dataclass est le contrat d'interface entre le loader (couche data)
    et les vues (couche présentation). Tout ce dont une vue a besoin
    se trouve ici — aucune transformation additionnelle n'est nécessaire.

    Attributs
    ---------
    df : pd.DataFrame
        Table atomique principale — **8 064 lignes × 20 colonnes**.
        Grain : (site_code, mois, compte_code) → unique.
        Colonnes clés :
          • montant_budget  : montant budget mensuel (signé)
          • montant_reel    : montant réel mensuel (NaN si non réalisé)
          • ecart_absolu    : réel - budget (NaN si réel absent)
          • ecart_pct       : écart / |budget| × 100
          • tx_realisation  : réel / |budget| × 100
          • est_realise     : bool — True si réel disponible
          • est_favorable   : bool — True si l'écart est favorable
          • ordre_classe    : int — position dans le P&L vertical

    df_sites : pd.DataFrame
        Référentiel des 7 sites enrichi avec leurs KPIs budgétaires :
          • Colonnes originales : site_code, site_libelle, departement,
                                  type_site, date_ouverture, responsable
          • Colonnes ajoutées  : ca_budget, mc_budget, tx_mc_budget,
                                  ebe_budget, tx_ebe_budget, rex_budget,
                                  tx_rex_budget

    df_comptes : pd.DataFrame
        Plan comptable PCG 2025 — 96 comptes, 7 colonnes.
        Colonnes : compte_code, compte_libelle, classe_cdg, sous_classe,
                   sig_etape, sens, ordre_affichage

    sig_annuel : pd.DataFrame
        SIG budget annuel (12 mois complets) par site.
        Index   : site_code
        Colonnes: CA_net, MC, Tx_MC_%, VA, Tx_VA_%, EBE, Tx_EBE_%,
                  REX, Tx_REX_%, RCAI, Tx_RCAI_%, RN, Tx_RN_%
        Usage   : KPI strip, comparaisons réseau, heatmap.

    sig_ytd : pd.DataFrame
        SIG YTD (Jan → mois_reel) — réel ET budget, avec écarts.
        Index   : site_code
        Colonnes: {KPI}_bgt, {KPI}_rel, {KPI}_ecart, {KPI}_ecart_pct
                  pour KPI ∈ {CA_net, MC, VA, EBE, REX, RCAI, RN}
        Usage   : écran 1 (tour de contrôle), header KPI strip.

    sig_mensuel : pd.DataFrame
        SIG mensuel par site — format long, budget + réel.
        Colonnes : site_code, mois, kpi, budget, reel, ecart
        7 KPIs × 7 sites × 12 mois = 588 lignes
        Usage   : graphiques de courbes (écran 2), forecast (écran 4).

    mois_reel : int
        Dernier mois pour lequel des données réelles sont disponibles.
        Détecté automatiquement (≥50% des lignes du mois ont un réel).
        Vaut 0 si aucun réel n'est disponible, 12 si l'année est complète.

    annee : int
        Exercice fiscal des données (ex. 2025).

    sites : list[str]
        Liste ordonnée des codes sites, du plus grand CA au plus petit.
        Ex. : ["LYO_C", "LYO_E", "CLM", "VLF", "MCN", "BGR", "ANC"]
        Usage : ordre par défaut dans tous les sélecteurs Streamlit.
    """

    # Tables de référence et données atomiques
    df          : pd.DataFrame
    df_sites    : pd.DataFrame
    df_comptes  : pd.DataFrame

    # Agrégats pré-calculés (évitent les recalculs dans les vues)
    sig_annuel  : pd.DataFrame
    sig_ytd     : pd.DataFrame
    sig_mensuel : pd.DataFrame

    # Métadonnées
    mois_reel   : int
    annee       : int
    sites       : List[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════════
# FONCTIONS INTERNES (privées — préfixe _)
# ══════════════════════════════════════════════════════════════════════════════

def _validate_schema(
    df       : pd.DataFrame,
    df_sites : pd.DataFrame,
    df_compt : pd.DataFrame,
) -> None:
    """
    Vérifie que les 3 DataFrames lus depuis Excel ont les colonnes attendues
    et que les valeurs clés sont dans les plages légales.

    Paramètres
    ----------
    df       : DataFrame de l'onglet "data"
    df_sites : DataFrame de l'onglet "ref_sites"
    df_compt : DataFrame de l'onglet "ref_comptes"

    Lève
    ----
    ValueError
        Si des colonnes obligatoires sont manquantes, ou si des valeurs
        hors plage sont détectées (sens ≠ {-1, 1}, mois hors [1, 12]).

    Notes
    -----
    Cette validation est intentionnellement stricte : mieux vaut
    une erreur explicite au chargement qu'un résultat silencieusement faux
    dans les SIG (symptôme classique des erreurs de signe en CDG).
    """
    # Vérification des colonnes par onglet
    for nom_onglet, df_check, schema_attendu in [
        ("data",        df,      _COLS_DATA),
        ("ref_sites",   df_sites, _COLS_SITES),
        ("ref_comptes", df_compt, _COLS_COMPTES),
    ]:
        colonnes_manquantes = set(schema_attendu) - set(df_check.columns)
        if colonnes_manquantes:
            raise ValueError(
                f"Onglet '{nom_onglet}' : colonnes manquantes → "
                f"{sorted(colonnes_manquantes)}\n"
                f"Colonnes présentes : {sorted(df_check.columns.tolist())}"
            )

    # La colonne "sens" ne peut contenir que +1 ou -1
    # Toute autre valeur trahit un problème dans le plan comptable
    valeurs_sens_invalides = set(df["sens"].unique()) - {-1, 1}
    if valeurs_sens_invalides:
        raise ValueError(
            f"Colonne 'sens' : valeurs inattendues → {valeurs_sens_invalides}\n"
            "Valeurs autorisées : -1 (charge) ou +1 (produit)."
        )

    # Les mois doivent être compris entre 1 et 12
    mois_hors_plage = df["mois"][~df["mois"].between(1, 12)]
    if len(mois_hors_plage) > 0:
        vals = sorted(mois_hors_plage.unique().tolist())
        raise ValueError(
            f"Colonne 'mois' : {len(mois_hors_plage)} valeurs hors [1, 12] → {vals}"
        )


def _coerce_types(df: pd.DataFrame, schema: Dict[str, str]) -> pd.DataFrame:
    """
    Convertit silencieusement les colonnes dans leur type cible.
    Émet un avertissement (warnings.warn) si une conversion échoue,
    sans interrompre le chargement.

    Paramètres
    ----------
    df     : DataFrame à convertir
    schema : dict {nom_colonne: dtype_cible}

    Retourne
    --------
    pd.DataFrame
        Le même DataFrame avec les types corrigés.

    Notes
    -----
    - "float64" : via pd.to_numeric(errors="coerce") — les valeurs non
      convertibles deviennent NaN (utile pour montant_reel qui peut être vide).
    - "int64"   : idem, puis cast. Si NaN résultants, cast vers Int64 nullable.
    - "object"  : simple str + strip des espaces.

    L'approche "coerce silencieux" est intentionnelle : les exports Excel
    contiennent souvent des cellules mixtes (nombre + texte) qu'une erreur
    stricte bloquerait inutilement.
    """
    for col, dtype in schema.items():
        if col not in df.columns:
            continue
        try:
            if dtype == "float64":
                # errors="coerce" : les non-numériques deviennent NaN
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
            elif dtype == "int64":
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
            else:
                # "object" = chaîne de caractères, strip des espaces parasites
                df[col] = df[col].astype(str).str.strip()
        except Exception as exc:
            warnings.warn(
                f"Colonne '{col}' : impossible de convertir vers {dtype} → {exc}",
                UserWarning,
                stacklevel=2,
            )
    return df


def _enrich(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ajoute les colonnes analytiques dérivées au DataFrame atomique.

    Colonnes ajoutées
    -----------------
    ecart_absolu : float
        réel - budget.
        NaN si montant_reel est NaN (mois non réalisé).
        Un écart positif sur un produit = favorable.
        Un écart négatif sur une charge  = favorable (moins de charges).

    ecart_pct : float
        (réel - budget) / |budget| × 100.
        En pourcentage relatif de l'écart par rapport au budget en valeur absolue.
        NaN si budget = 0 ou si réel est absent.
        |budget| évite l'inversion de signe sur les charges.

    tx_realisation : float
        réel / |budget| × 100.
        Taux de consommation du budget (100% = exactement au budget).
        NaN si budget = 0 ou si réel est absent.

    est_realise : bool
        True si montant_reel n'est pas NaN (le mois a été clôturé).
        False pour tous les mois futurs (mai à décembre dans le cas 4+8).

    est_favorable : bool ou NaN
        True si l'écart joue en faveur du résultat.
        Logique : (écart_absolu × sens) > 0
          → Pour un produit (sens=+1) : réel > budget → favorable ✓
          → Pour une charge  (sens=-1) : réel < budget (moins négatif) → favorable ✓
        NaN si le mois n'est pas réalisé (est_realise = False).

    ordre_classe : int
        Position de la classe_cdg dans le P&L (selon CLASSE_ORDER).
        Utilisé pour trier cohéremment dans toutes les vues.
        99 si la classe n'est pas dans CLASSE_ORDER (failsafe).

    Paramètres
    ----------
    df : pd.DataFrame
        DataFrame atomique brut, post-validation.

    Retourne
    --------
    pd.DataFrame
        Copie enrichie avec 6 colonnes supplémentaires.

    Notes
    -----
    On travaille sur une copie (df.copy()) pour ne pas modifier l'original
    et garantir l'absence d'effets de bord si _enrich() est appelé plusieurs fois.
    """
    df = df.copy()

    # ── Écart absolu ──────────────────────────────────────────────────────────
    # Simple différence ; NaN se propage automatiquement si montant_reel = NaN
    df["ecart_absolu"] = df["montant_reel"] - df["montant_budget"]

    # ── Division par |budget| pour éviter l'inversion de signe sur les charges ─
    # Exemple : budget=-100€ (charge), réel=-90€ → écart=+10€ (favorable)
    # écart_pct = +10 / |-100| × 100 = +10% (correct, positif = favorable)
    # Sans valeur absolue : +10 / -100 × 100 = -10% (trompeur !)
    budget_abs = df["montant_budget"].replace(0, np.nan).abs()
    df["ecart_pct"]      = df["ecart_absolu"] / budget_abs * 100
    df["tx_realisation"] = df["montant_reel"]  / budget_abs * 100

    # ── Flags booléens ────────────────────────────────────────────────────────
    df["est_realise"] = df["montant_reel"].notna()

    # est_favorable : ecart > 0 ↔ réel > budget → améliore toujours le résultat net
    # Valable pour tous les sens (charges à montants négatifs inclus) :
    #   • Produits +  : réel > budget → plus de CA → favorable ✓
    #   • Charges -   : réel > budget → montant moins négatif → moins de charges → favorable ✓
    # NaN pour les mois futurs (indéterminé)
    df["est_favorable"] = np.where(
        df["est_realise"],
        df["ecart_absolu"] > 0,
        np.nan,
    )

    # ── Ordre de classe pour tris cohérents dans toutes les vues ─────────────
    ordre_map = {classe: idx for idx, classe in enumerate(CLASSE_ORDER)}
    df["ordre_classe"] = (
        df["classe_cdg"].map(ordre_map).fillna(99).astype(int)
    )

    return df


def _safe_pct(numerateur: pd.Series, denominateur: pd.Series) -> pd.Series:
    """
    Calcule un pourcentage de manière sûre, en gérant les dénominateurs nuls.

    Paramètres
    ----------
    numerateur   : Series numérateur
    denominateur : Series dénominateur

    Retourne
    --------
    pd.Series
        (numerateur / denominateur × 100) arrondi à 1 décimale.
        0.0 là où le dénominateur est nul ou NaN.

    Notes
    -----
    Remplace 0 → NaN avant la division pour éviter les ZeroDivisionError,
    puis fillna(0) pour avoir un affichage propre dans les tableaux.
    Cette fonction est utilisée exclusivement dans _compute_sig_from_wide().
    """
    return (
        numerateur / denominateur.replace(0, np.nan) * 100
    ).round(1).fillna(0)


def _compute_sig_from_wide(grp: pd.DataFrame) -> pd.DataFrame:
    """
    Calcule les 7 soldes intermédiaires de gestion (SIG) à partir d'un
    DataFrame "wide" (index = site_code, colonnes = classes analytiques,
    valeurs = sommes de montants).

    PRINCIPE FONDAMENTAL
    ────────────────────
    Tous les montants étant déjà signés (convention comptable), chaque SIG
    est calculé par simple addition des classes qui le composent.
    Il n'y a PAS de soustraction dans cette fonction.

    Exemple EBE pour un site donné :
      Produits    = +380 K€  (CA net)
      Achats      = -228 K€  (CAMV)
      Serv. 61    =  -57 K€  (loyers, entretien, assurances)
      Serv. 62    =  -57 K€  (honoraires, transport, IT)
      Autres prod =   +5 K€  (subventions)
      Impôts      =   -9 K€  (CFE, TICPE)
      Personnel   = -200 K€  (salaires + charges)
      ─────────────────────────
      EBE         =  +34 K€  (simple somme)

    Paramètres
    ----------
    grp : pd.DataFrame
        DataFrame avec :
          • Index  = site_code (str)
          • Colonnes = noms de classes analytiques (str)
          • Valeurs = sommes de montants signés (float)
        Produit typiquement par :
          df.groupby(["site_code","classe_cdg"])[col].sum().unstack(fill_value=0)

    Retourne
    --------
    pd.DataFrame
        Index = site_code
        Colonnes :
          CA_net, MC, Tx_MC_%,
          VA, Tx_VA_%,
          EBE, Tx_EBE_%,
          REX, Tx_REX_%,
          RCAI, Tx_RCAI_%,
          RN, Tx_RN_%
        Les montants sont en euros (non arrondis ici — arrondi à l'affichage).
        Les Tx_*_% sont en pourcentage du CA_net, arrondis à 1 décimale.

    Notes
    -----
    La fonction helper interne s(cl) retourne 0 si la classe n'existe pas
    dans grp, ce qui assure la robustesse lorsque certaines classes sont
    absentes (ex. pas de produits exceptionnels pour un site).

    Les taux sont calculés sur CA_net (Produits) pour permettre la
    comparaison avec les benchmarks sectoriels (Banque de France).
    """

    def s(cl: str) -> pd.Series:
        """Retourne la colonne de la classe 'cl', ou 0 si absente."""
        return grp[cl] if cl in grp.columns else pd.Series(0.0, index=grp.index)

    # ── Composantes du compte de résultat ──────────────────────────────────
    prd  = s("Produits")            # CA net (ventes - RRR + ports/emball)
    ach  = s("Achats")              # CAMV net (achats - RRR fournisseurs)
    s61  = s("Services ext. 61")    # Locations, entretien, assurances
    s62  = s("Services ext. 62")    # Honoraires, transport, pub, IT
    apd  = s("Autres produits")     # Subventions + refacturations
    itx  = s("Impôts et taxes")     # CFE, TICPE, taxes RH
    prs  = s("Charges personnel")   # Salaires + charges sociales
    ach_ = s("Autres charges")      # PDC, pénalités commerciales
    dot  = s("Dotations")           # Amortissements + provisions
    rep  = s("Reprises")            # Reprises sur amortissements/provisions
    pfn  = s("Produits financiers") # Escomptes obtenus, placements
    cfn  = s("Charges financières") # Intérêts, agios, CCA
    pex  = s("Produits exceptionnels")
    cex  = s("Charges exceptionnelles")
    isp  = s("IS et participation") # IS + participation salariés

    # ── Calcul des SIG (chaque ligne = simple addition des composantes) ─────
    ca   = prd                      # CA_net = Σ Produits (nets des RRR)
    mc   = prd + ach                # Marge Commerciale
    va   = mc  + s61 + s62         # Valeur Ajoutée
    ebe  = va  + apd + itx + prs   # Excédent Brut d'Exploitation
    rex  = ebe + ach_ + dot + rep  # Résultat d'Exploitation
    rcai = rex + pfn  + cfn        # Résultat Courant Avant Impôts
    rexc = pex + cex               # Résultat Exceptionnel
    rn   = rcai + rexc + isp       # Résultat Net

    return pd.DataFrame({
        "CA_net"    : ca,
        "MC"        : mc,    "Tx_MC_%"   : _safe_pct(mc,   ca),
        "VA"        : va,    "Tx_VA_%"   : _safe_pct(va,   ca),
        "EBE"       : ebe,   "Tx_EBE_%"  : _safe_pct(ebe,  ca),
        "REX"       : rex,   "Tx_REX_%"  : _safe_pct(rex,  ca),
        "RCAI"      : rcai,  "Tx_RCAI_%" : _safe_pct(rcai, ca),
        "RN"        : rn,    "Tx_RN_%"   : _safe_pct(rn,   ca),
    })


def _build_sig_annuel(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcule les SIG budget annuels (12 mois) pour chaque site.

    Paramètres
    ----------
    df : pd.DataFrame
        DataFrame atomique enrichi (output de _enrich()).

    Retourne
    --------
    pd.DataFrame
        Index = site_code | Colonnes = CA_net, MC, Tx_MC_%, VA, … RN, Tx_RN_%
        Montants en euros, taux en %.

    Notes
    -----
    Agrège tous les mois (1–12) sur la colonne montant_budget.
    Utile comme référence "objectif annuel" dans les comparaisons YTD.
    """
    grp = (
        df.groupby(["site_code", "classe_cdg"])["montant_budget"]
        .sum()
        .unstack(fill_value=0.0)
    )
    return _compute_sig_from_wide(grp)


def _build_sig_ytd(df: pd.DataFrame, mois_reel: int) -> pd.DataFrame:
    """
    Calcule les SIG YTD (Jan → mois_reel) en budget ET en réel, avec écarts.

    Paramètres
    ----------
    df        : DataFrame atomique enrichi
    mois_reel : dernier mois avec données réelles disponibles

    Retourne
    --------
    pd.DataFrame
        Index = site_code
        Colonnes pour chaque KPI ∈ {CA_net, MC, VA, EBE, REX, RCAI, RN} :
          {KPI}_bgt       : valeur YTD budget (montant_budget)
          {KPI}_rel       : valeur YTD réel   (montant_reel)
          {KPI}_ecart     : réel - budget (€)
          {KPI}_ecart_pct : (réel - budget) / |budget| × 100 (%)

    Notes
    -----
    Le suffixe _bgt / _rel facilite les accès via .loc dans les vues,
    sans avoir à filtrer col par col.
    Les écarts négatifs sur les produits = défavorables.
    Les écarts positifs sur les charges = défavorables (plus de charges).
    La lecture directe de l'écart suffit : positif = plus de CA (bon),
    négatif = moins de CA (mauvais), sans besoin de corriger par le sens.
    """
    df_ytd = df[df["mois"] <= mois_reel].copy()

    # SIG budget YTD
    grp_bgt = (
        df_ytd.groupby(["site_code", "classe_cdg"])["montant_budget"]
        .sum()
        .unstack(fill_value=0.0)
    )
    sig_bgt = _compute_sig_from_wide(grp_bgt).add_suffix("_bgt")

    # SIG réel YTD — seulement les lignes ayant un montant_reel
    df_rel  = df_ytd[df_ytd["montant_reel"].notna()]
    grp_rel = (
        df_rel.groupby(["site_code", "classe_cdg"])["montant_reel"]
        .sum()
        .unstack(fill_value=0.0)
    )
    sig_rel = _compute_sig_from_wide(grp_rel).add_suffix("_rel")

    result = sig_bgt.join(sig_rel)

    # Calcul des écarts pour les 7 KPIs principaux
    for kpi in ("CA_net", "MC", "VA", "EBE", "REX", "RCAI", "RN"):
        col_b = f"{kpi}_bgt"
        col_r = f"{kpi}_rel"
        if col_b in result.columns and col_r in result.columns:
            ecart          = result[col_r] - result[col_b]
            result[f"{kpi}_ecart"]     = ecart.round(0)
            result[f"{kpi}_ecart_pct"] = _safe_pct(ecart, result[col_b].abs())

    return result


def _build_sig_mensuel(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcule les SIG mois par mois en format long (budget + réel).

    Paramètres
    ----------
    df : DataFrame atomique enrichi

    Retourne
    --------
    pd.DataFrame — 588 lignes (7 sites × 12 mois × 7 KPIs)
        Colonnes : site_code, mois, kpi, budget, reel, ecart

    Notes
    -----
    Le format "long" (un KPI par ligne) est préféré au format "wide"
    pour l'intégration native avec Plotly Express (px.line, px.bar)
    qui consomme ce format directement.

    Le calcul est fait mois par mois avec un groupby en deux passes
    (budget + réel) pour garantir que chaque mois est indépendant.
    Mois futurs : reel = NaN, ecart = NaN — signale explicitement l'absence de données.
    """
    records = []

    for (site, mois), groupe in df.groupby(["site_code", "mois"]):
        # ── SIG budget du mois ───────────────────────────────────────────────
        grp_b = (
            groupe.groupby("classe_cdg")["montant_budget"]
            .sum()
            .to_frame().T
        )
        grp_b.index = [site]
        sig_b = _compute_sig_from_wide(grp_b)

        # ── SIG réel du mois (si disponible) ─────────────────────────────────
        g_rel    = groupe[groupe["montant_reel"].notna()]
        has_reel = len(g_rel) > 0

        if has_reel:
            grp_r = (
                g_rel.groupby("classe_cdg")["montant_reel"]
                .sum()
                .to_frame().T
            )
            grp_r.index = [site]
            sig_r = _compute_sig_from_wide(grp_r)

        # ── Construction des enregistrements long-format ──────────────────────
        for kpi in ("CA_net", "MC", "VA", "EBE", "REX", "RCAI", "RN"):
            bgt_val = float(sig_b.loc[site, kpi])
            rel_val = float(sig_r.loc[site, kpi]) if has_reel else np.nan
            records.append({
                "site_code" : site,
                "mois"      : mois,
                "kpi"       : kpi,
                "budget"    : bgt_val,
                "reel"      : rel_val,
                "ecart"     : rel_val - bgt_val if has_reel else np.nan,
            })

    return pd.DataFrame(records)


def _detect_mois_reel(df: pd.DataFrame) -> int:
    """
    Détecte automatiquement le dernier mois pour lequel des données réelles
    sont disponibles, sans qu'il soit nécessaire de le configurer manuellement.

    Algorithme
    ----------
    Pour chaque mois de 1 à 12 :
      1. Filtrer les lignes de ce mois
      2. Calculer le taux de remplissage : nb lignes avec réel / nb total lignes
      3. Si ce taux >= SEUIL (0.50) → le mois est considéré comme "réalisé"
    Retourner le max des mois réalisés.

    Paramètres
    ----------
    df : DataFrame atomique brut (avant enrichissement)

    Retourne
    --------
    int
        Mois 1–12 du dernier réalisé, ou 0 si aucun réel n'est disponible.

    Notes
    -----
    Seuil de 50% (et non 100%) pour gérer les cas où certains comptes
    sont remplis avec quelques jours de décalage en fin de mois :
    un mois "presque complet" est préférable à un mois "non détecté".

    Ce mécanisme rend le dashboard auto-adaptatif : en déployant un nouveau
    fichier Excel chaque mois, la détection est automatique.
    """
    SEUIL = 0.50
    mois_realises = []

    for mois in range(1, 13):
        df_mois = df[df["mois"] == mois]
        if len(df_mois) == 0:
            continue
        taux_remplissage = df_mois["montant_reel"].notna().mean()
        if taux_remplissage >= SEUIL:
            mois_realises.append(mois)

    return max(mois_realises) if mois_realises else 0


# ══════════════════════════════════════════════════════════════════════════════
# API PUBLIQUE — FONCTION PRINCIPALE
# ══════════════════════════════════════════════════════════════════════════════

def load_data(
    path           : str | Path = "data/sample_budget_v2.xlsx",
    sheet_data     : str = "data",
    sheet_sites    : str = "ref_sites",
    sheet_comptes  : str = "ref_comptes",
) -> DashboardData:
    """
    Charge, valide, enrichit et structure les données du dashboard.
    C'est la **seule** fonction que les vues Streamlit doivent appeler.

    Paramètres
    ----------
    path : str ou Path
        Chemin vers le fichier Excel de données.
        Défaut : "data/sample_budget_v2.xlsx" (relatif au répertoire courant).

    sheet_data : str
        Nom de l'onglet contenant les données atomiques (grain site×mois×compte).
        Défaut : "data"

    sheet_sites : str
        Nom de l'onglet contenant le référentiel sites.
        Défaut : "ref_sites"

    sheet_comptes : str
        Nom de l'onglet contenant le plan comptable.
        Défaut : "ref_comptes"

    Retourne
    --------
    DashboardData
        Conteneur complet prêt à l'emploi. Voir DashboardData pour
        la description détaillée de chaque attribut.

    Lève
    ----
    FileNotFoundError
        Si le fichier Excel n'existe pas au chemin spécifié.
        Message d'aide pour relancer le générateur.

    ValueError
        Si le schéma des onglets ne correspond pas au format attendu
        (colonnes manquantes, valeurs hors plage).

    Exemple
    -------
    >>> from core.loader import load_data
    >>> data = load_data("data/sample_budget_v2.xlsx")
    >>> print(f"Sites : {data.sites}")
    Sites : ['LYO_C', 'LYO_E', 'CLM', 'VLF', 'MCN', 'BGR', 'ANC']
    >>> print(data.sig_annuel[["CA_net", "Tx_EBE_%"]])

    Notes
    -----
    Intégration Streamlit recommandée :
        @st.cache_data
        def get_data():
            return load_data()

    Le décorateur @st.cache_data met en cache le résultat :
    le fichier Excel n'est lu qu'une fois par session, même si la vue
    est rechargée (navigation entre écrans).
    """
    path = Path(path)

    # ── 1. Vérification existence ─────────────────────────────────────────────
    if not path.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {path.resolve()}\n"
            f"→ Exécutez d'abord : python generators/generate_sample_v3.py"
        )

    # ── 2. Lecture des 3 onglets ──────────────────────────────────────────────
    df       = pd.read_excel(path, sheet_name=sheet_data)
    df_sites = pd.read_excel(path, sheet_name=sheet_sites)
    df_compt = pd.read_excel(path, sheet_name=sheet_comptes)

    # ── 3. Cast des types ─────────────────────────────────────────────────────
    df       = _coerce_types(df, _COLS_DATA)
    df_sites = _coerce_types(df_sites, _COLS_SITES)
    df_compt = _coerce_types(df_compt, _COLS_COMPTES)

    # ── 4. Validation du schéma ───────────────────────────────────────────────
    _validate_schema(df, df_sites, df_compt)

    # ── 5. Métadonnées ────────────────────────────────────────────────────────
    mois_reel = _detect_mois_reel(df)
    annee     = int(df["annee"].iloc[0])

    # ── 6. Enrichissement du DataFrame principal ──────────────────────────────
    df = _enrich(df)

    # ── 7. Calcul des SIG (3 granularités) ───────────────────────────────────
    sig_annuel  = _build_sig_annuel(df)
    sig_ytd     = _build_sig_ytd(df, mois_reel)
    sig_mensuel = _build_sig_mensuel(df)

    # ── 8. Enrichissement du référentiel sites avec les KPIs annuels ──────────
    # Les KPIs sont utiles dans la navigation (sidebar, sélecteur de site)
    kpis_site = sig_annuel[[
        "CA_net", "MC", "Tx_MC_%", "EBE", "Tx_EBE_%", "REX", "Tx_REX_%"
    ]].rename(columns={
        "CA_net" : "ca_budget",   "MC"       : "mc_budget",
        "Tx_MC_%": "tx_mc_budget","EBE"      : "ebe_budget",
        "Tx_EBE_%": "tx_ebe_budget","REX"    : "rex_budget",
        "Tx_REX_%": "tx_rex_budget",
    })
    df_sites = df_sites.set_index("site_code").join(kpis_site).reset_index()

    # ── 9. Ordre des sites par CA décroissant ─────────────────────────────────
    # L'ordre par CA est la convention par défaut dans tous les sélecteurs
    sites = (
        df_sites
        .sort_values("ca_budget", ascending=False)["site_code"]
        .tolist()
    )

    return DashboardData(
        df          = df,
        df_sites    = df_sites,
        df_comptes  = df_compt,
        sig_annuel  = sig_annuel,
        sig_ytd     = sig_ytd,
        sig_mensuel = sig_mensuel,
        mois_reel   = mois_reel,
        annee       = annee,
        sites       = sites,
    )


# ══════════════════════════════════════════════════════════════════════════════
# API PUBLIQUE — HELPERS POUR LES VUES
# ══════════════════════════════════════════════════════════════════════════════

def get_site_data(
    data      : DashboardData,
    site_code : str,
    mois_min  : int = 1,
    mois_max  : int = 12,
) -> pd.DataFrame:
    """
    Filtre le DataFrame principal sur un site et une plage de mois.

    Paramètres
    ----------
    data      : DashboardData
    site_code : code du site (ex. "LYO_C")
    mois_min  : premier mois inclus (défaut : 1 = janvier)
    mois_max  : dernier mois inclus (défaut : 12 = décembre)

    Retourne
    --------
    pd.DataFrame
        Copie filtrée de data.df avec toutes les colonnes enrichies.

    Exemple
    -------
    >>> df_lyoc = get_site_data(data, "LYO_C")           # toute l'année
    >>> df_ytd  = get_site_data(data, "LYO_C", mois_max=data.mois_reel)  # YTD
    """
    return data.df[
        (data.df["site_code"] == site_code) &
        (data.df["mois"].between(mois_min, mois_max))
    ].copy()


def get_ytd_by_classe(
    data      : DashboardData,
    site_code : Optional[str] = None,
) -> pd.DataFrame:
    """
    Agrège les montants YTD par classe CDG, budget vs réel.

    Paramètres
    ----------
    data      : DashboardData
    site_code : code site → filtre sur un site spécifique.
                None (défaut) → consolidation tous sites.

    Retourne
    --------
    pd.DataFrame — trié par ordre_classe (ordre P&L)
        Colonnes : classe_cdg, ordre_classe, budget, reel,
                   ecart, ecart_pct

    Notes
    -----
    Utile pour l'écran 3 (analyse des écarts) et l'écran 1
    (décomposition par classe dans le waterfall consolidé).
    """
    df_ = data.df[data.df["mois"] <= data.mois_reel].copy()
    if site_code:
        df_ = df_[df_["site_code"] == site_code]

    agg = (
        df_
        .groupby(["classe_cdg", "ordre_classe"])
        .agg(
            budget=("montant_budget", "sum"),
            reel  =("montant_reel",   "sum"),
        )
        .reset_index()
        .sort_values("ordre_classe")
    )

    # Écart et % (avec protection division par zéro)
    agg["ecart"] = agg["reel"] - agg["budget"]
    budget_abs   = agg["budget"].replace(0, np.nan).abs()
    agg["ecart_pct"] = (agg["ecart"] / budget_abs * 100).round(1).fillna(0)

    return agg


def get_top_ecarts(
    data        : DashboardData,
    site_code   : Optional[str] = None,
    n           : int = 10,
    sens_ecart  : str = "defavorable",
) -> pd.DataFrame:
    """
    Retourne les N plus grands écarts compte par compte sur le YTD.

    Paramètres
    ----------
    data        : DashboardData
    site_code   : filtre sur un site (None = tous sites)
    n           : nombre d'écarts à retourner (défaut : 10)
    sens_ecart  : "defavorable" | "favorable" | "all"
                  "defavorable" → les pires écarts (impact négatif sur résultat)
                  "favorable"   → les meilleures surprises
                  "all"         → les n plus grands en valeur absolue

    Retourne
    --------
    pd.DataFrame
        Colonnes : site_code, compte_code, compte_libelle, classe_cdg,
                   sous_classe, budget, reel, ecart, ecart_impact,
                   ecart_pct, est_favorable
        Trié par impact décroissant (abs(ecart_impact)).

    Notes
    -----
    ecart_impact = ecart_absolu × sens :
      • Positif = favorable (plus de CA, moins de charges)
      • Négatif = défavorable

    Exemple
    -------
    >>> top5 = get_top_ecarts(data, site_code="BGR", n=5)
    >>> # → Affiche les 5 postes de dérive les plus importants pour BGR
    """
    df_ = data.df[
        (data.df["mois"] <= data.mois_reel) &
        (data.df["montant_reel"].notna())
    ].copy()

    if site_code:
        df_ = df_[df_["site_code"] == site_code]

    # Agrégation YTD par compte
    agg = (
        df_.groupby([
            "site_code", "compte_code", "compte_libelle",
            "classe_cdg", "sous_classe", "sens",
        ])
        .agg(budget=("montant_budget", "sum"), reel=("montant_reel", "sum"))
        .reset_index()
    )

    agg["ecart"]        = agg["reel"] - agg["budget"]
    agg["ecart_impact"] = agg["ecart"] * agg["sens"]  # + favorable, - défavorable
    agg["est_favorable"]= agg["ecart_impact"] > 0

    budget_abs = agg["budget"].replace(0, np.nan).abs()
    agg["ecart_pct"] = (agg["ecart"] / budget_abs * 100).round(1).fillna(0)

    if sens_ecart == "defavorable":
        return agg[~agg["est_favorable"]].nsmallest(n, "ecart_impact")
    elif sens_ecart == "favorable":
        return agg[agg["est_favorable"]].nlargest(n, "ecart_impact")
    else:
        return agg.reindex(agg["ecart_impact"].abs().nlargest(n).index)


def get_waterfall_data(
    data      : DashboardData,
    site_code : str,
    mois      : int,
) -> Dict:
    """
    Prépare les données pour le waterfall chart Budget → drivers → Réel.

    Le waterfall décompose l'écart total résultat d'un mois en contributions
    par classe CDG. C'est le principal outil de diagnostic rapide pour le DG.

    Paramètres
    ----------
    data      : DashboardData
    site_code : code du site à analyser
    mois      : mois à analyser (doit être ≤ mois_reel)

    Retourne
    --------
    dict avec clés :
      "drivers"     : pd.DataFrame — une ligne par classe CDG
                      Colonnes : classe_cdg, ordre_classe, budget, reel, contribution
      "total_bgt"   : float — résultat total budget du mois
      "total_rel"   : float — résultat total réel du mois
      "ecart_total" : float — différence (réel - budget)

    Notes
    -----
    Si mois > mois_reel, le réel est NaN et la fonction retourne un dict
    avec ecart_total = 0. Les vues doivent gérer ce cas.

    Exemple
    -------
    >>> wf = get_waterfall_data(data, "LYO_E", mois=3)
    >>> # → Révèle que l'écart négatif vient principalement des Achats
    """
    df_ = data.df[
        (data.df["site_code"] == site_code) &
        (data.df["mois"] == mois) &
        (data.df["montant_reel"].notna())
    ].copy()

    drivers = (
        df_
        .groupby(["classe_cdg", "ordre_classe"])
        .agg(budget=("montant_budget", "sum"), reel=("montant_reel", "sum"))
        .reset_index()
        .sort_values("ordre_classe")
    )
    drivers["contribution"] = drivers["reel"] - drivers["budget"]

    total_bgt = float(drivers["budget"].sum())
    total_rel = float(drivers["reel"].sum())

    return {
        "drivers"    : drivers,
        "total_bgt"  : total_bgt,
        "total_rel"  : total_rel,
        "ecart_total": total_rel - total_bgt,
    }


def get_heatmap_data(
    data : DashboardData,
    kpi  : str = "EBE",
    base : str = "ecart_pct",
) -> pd.DataFrame:
    """
    Construit la matrice sites × mois pour la heatmap du tour de contrôle.

    Paramètres
    ----------
    data : DashboardData
    kpi  : KPI à représenter — "CA_net" | "MC" | "EBE" | "REX" | "RCAI" | "RN"
    base : métrique à afficher dans les cellules :
           "ecart_pct"     → écart % réel vs budget (valeur signée)
           "valeur_reel"   → montant réel absolu en €
           "tx_realisation"→ taux de réalisation %

    Retourne
    --------
    pd.DataFrame
        Index   = site_code (dans l'ordre data.sites)
        Colonnes= mois 1–12
        Valeurs = métrique choisie (NaN pour les mois non réalisés)

    Notes
    -----
    La heatmap est l'outil de surveillance multi-sites par excellence.
    Elle permet au DG d'identifier en un coup d'œil les anomalies :
      • Ligne entièrement rouge → site structurellement en difficulté
      • Colonne rouge → problème conjoncturel (mois particulier)
      • Cellule isolée → événement ponctuel à investiguer

    Attention sur l'interprétation des % d'écart EBE :
    quand l'EBE budget est proche de zéro, un petit écart en €
    produit un % d'écart très élevé. Filtrer les cellules où |budget| < seuil.
    """
    sig_m = data.sig_mensuel[data.sig_mensuel["kpi"] == kpi].copy()

    # Calcul des métriques dérivées
    budget_abs_safe = sig_m["budget"].replace(0, np.nan).abs()
    sig_m["ecart_pct"]      = ((sig_m["reel"] - sig_m["budget"]) / budget_abs_safe * 100).round(1)
    sig_m["valeur_reel"]    = sig_m["reel"]
    sig_m["tx_realisation"] = (sig_m["reel"] / budget_abs_safe * 100).round(1)

    pivot = sig_m.pivot(index="site_code", columns="mois", values=base)

    # Réordonner les sites selon l'ordre standard (CA décroissant)
    return pivot.reindex(data.sites)


# ══════════════════════════════════════════════════════════════════════════════
# EXÉCUTION DIRECTE — VALIDATION RAPIDE EN LIGNE DE COMMANDE
# ══════════════════════════════════════════════════════════════════════════════


def filter_to_mois(data: DashboardData, mois_sel: int) -> DashboardData:
    """
    Retourne une copie de DashboardData restreinte à un mois d'analyse différent.

    Permet au sélecteur de période de la sidebar de "rejouer" l'état du
    dashboard à n'importe quel mois réalisé sans recharger le fichier Excel.

    Seuls mois_reel et sig_ytd sont recalculés — df, sig_annuel, sig_mensuel
    restent identiques (ils contiennent toujours les 12 mois complets).

    Paramètres
    ----------
    data     : DashboardData complet (chargé une fois en cache)
    mois_sel : mois cible (1–mois_reel max)

    Retourne
    --------
    DashboardData avec mois_reel=mois_sel et sig_ytd recalculé
    """
    import dataclasses
    mois_sel = max(1, min(mois_sel, data.mois_reel))
    if mois_sel == data.mois_reel:
        return data   # pas de recalcul si déjà le bon mois
    new_sig_ytd = _build_sig_ytd(data.df, mois_sel)
    return dataclasses.replace(data, mois_reel=mois_sel, sig_ytd=new_sig_ytd)

if __name__ == "__main__":
    import sys

    chemin = sys.argv[1] if len(sys.argv) > 1 else "data/sample_budget_v2.xlsx"
    print(f"\nChargement : {chemin}")
    data = load_data(chemin)

    print(f"\n{'═'*70}")
    print(f"✅  {len(data.df):,} lignes | annee={data.annee} | mois_reel={data.mois_reel}")
    print(f"    Sites ({len(data.sites)}) : {data.sites}")
    print(f"    Comptes : {data.df['compte_code'].nunique()}")

    print(f"\n{'─'*70}")
    print("SIG BUDGET ANNUEL (K€)")
    print(
        data.sig_annuel[["CA_net","MC","Tx_MC_%","EBE","Tx_EBE_%","REX","Tx_REX_%"]]
        .div([1e3,1e3,1,1e3,1,1e3,1]).round(1).to_string()
    )

    print(f"\n{'─'*70}")
    print("SIG YTD — ÉCARTS RÉEL vs BUDGET (K€)")
    cols = ["CA_net_bgt","CA_net_rel","CA_net_ecart_pct",
            "EBE_bgt","EBE_rel","EBE_ecart","REX_bgt","REX_rel","REX_ecart"]
    vue = data.sig_ytd[cols].copy()
    for c in cols:
        if "ecart_pct" not in c:
            vue[c] = (vue[c] / 1e3).round(1)
    print(vue.to_string())

    print(f"\n{'─'*70}")
    print("TOP 5 ÉCARTS DÉFAVORABLES (YTD, tous sites)")
    top = get_top_ecarts(data, n=5, sens_ecart="defavorable")
    print(
        top[["site_code","compte_code","compte_libelle","budget","reel","ecart","ecart_pct"]]
        .to_string()
    )
