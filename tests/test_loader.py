"""
tests/test_loader.py
Tests de la couche d'accès aux données (loader.py).

Couvre :
  - Chargement et schéma
  - Convention de signe comptable
  - Cohérence SIG (MC < CA, VA < MC…)
  - Détection automatique du mois réel
  - Enrichissement (écart, tx_realisation, est_favorable)
  - Helpers publics
"""
import pytest
import numpy as np
import pandas as pd
from pathlib import Path


# ─── Chargement ─────────────────────────────────────────────────────────────

class TestChargement:

    def test_fichier_existe(self):
        from loader import load_data
        p = Path("data/sample_budget_v2.xlsx")
        assert p.exists(), f"Fichier introuvable : {p.resolve()}"

    def test_fichier_inexistant_leve_erreur(self):
        from loader import load_data
        with pytest.raises(FileNotFoundError):
            load_data("data/inexistant.xlsx")

    def test_charge_sans_erreur(self, data):
        assert data is not None

    def test_dimensions_df(self, data):
        # 7 sites × 12 mois × 96 comptes = 8 064 lignes
        assert len(data.df) == 7 * 12 * 96, (
            f"Attendu 8064 lignes, obtenu {len(data.df)}"
        )

    def test_annee(self, data):
        assert data.annee == 2025

    def test_mois_reel_detecte(self, data):
        # Mois réel doit être entre 1 et 12
        assert 1 <= data.mois_reel <= 12

    def test_mois_reel_valeur(self, data):
        # Le générateur produit 12 mois de réel (année complète)
        assert data.mois_reel == 12

    def test_nb_sites(self, data):
        assert len(data.sites) == 7

    def test_codes_sites(self, data):
        attendus = {"LYO_C", "LYO_E", "VLF", "MCN", "BGR", "CLM", "ANC"}
        assert set(data.sites) == attendus

    def test_nb_comptes(self, data):
        assert data.df["compte_code"].nunique() == 96

    def test_ref_sites_colonnes(self, data):
        cols = {"site_code", "site_libelle", "departement",
                "type_site", "date_ouverture", "responsable"}
        assert cols.issubset(set(data.df_sites.columns))

    def test_ref_comptes_colonnes(self, data):
        cols = {"compte_code", "compte_libelle", "classe_cdg",
                "sig_etape", "sens", "ordre_affichage"}
        assert cols.issubset(set(data.df_comptes.columns))


# ─── Convention de signe ────────────────────────────────────────────────────

class TestConventionSigne:

    def test_sens_valeurs_autorisees(self, data):
        """La colonne 'sens' ne contient que +1 ou -1."""
        vals = set(data.df["sens"].unique())
        assert vals == {-1, 1}, f"Valeurs inattendues dans 'sens' : {vals}"

    def test_ventes_pures_sens_positif(self, data):
        """Les comptes 707xxx (ventes de marchandises pures) ont sens = +1.

        Note : la classe 'Produits' contient aussi les 709xxx (RRR accordés)
        qui ont sens = -1 — comportement correct PCG, ils réduisent le CA net.
        On teste donc uniquement la série 707xxx.
        """
        df_707 = data.df[data.df["compte_code"].str.startswith("707")]
        assert len(df_707) > 0, "Aucun compte 707xxx dans les données"
        assert (df_707["sens"] == 1).all(), "Compte 707xxx avec sens ≠ +1 détecté"

    def test_charges_personnel_sens_negatif(self, data):
        """Les charges de personnel ont sens = -1."""
        df_pers = data.df[data.df["classe_cdg"] == "Charges personnel"]
        assert (df_pers["sens"] == -1).all()

    def test_correctif_rrr_accordes_signe_negatif(self, data):
        """709xxx (RRR accordés) sont des correctifs produits → montant négatif."""
        df_rrr = data.df[data.df["compte_code"].str.startswith("709")]
        budgets_pos = (df_rrr["montant_budget"] > 0).sum()
        assert budgets_pos == 0, (
            f"{budgets_pos} lignes 709xxx avec montant_budget > 0 (devrait être ≤ 0)"
        )

    def test_correctif_rrr_obtenus_signe_positif(self, data):
        """609xxx (RRR obtenus fournisseurs) → montant positif car réduit les achats."""
        df_rrr = data.df[data.df["compte_code"].str.startswith("609")]
        budgets_neg = (df_rrr["montant_budget"] < 0).sum()
        assert budgets_neg == 0, (
            f"{budgets_neg} lignes 609xxx avec montant_budget < 0 (devrait être ≥ 0)"
        )

    def test_resultat_egal_somme_signee(self, data):
        """Résultat = Σ toutes les lignes (convention signe comptable)."""
        resultat_calcule = data.df.groupby("site_code")["montant_budget"].sum()
        sig_rn = data.sig_annuel["RN"]
        for site in data.sites:
            assert abs(resultat_calcule[site] - sig_rn[site]) < 1.0, (
                f"{site} : résultat calculé {resultat_calcule[site]:.0f}€ "
                f"≠ SIG RN {sig_rn[site]:.0f}€"
            )


# ─── Cohérence SIG ──────────────────────────────────────────────────────────

class TestCoherenceSIG:

    def test_sig_annuel_index(self, data):
        assert set(data.sig_annuel.index) == set(data.sites)

    def test_sig_annuel_colonnes(self, data):
        cols = {"CA_net", "MC", "VA", "EBE", "REX", "RCAI", "RN",
                "Tx_MC_%", "Tx_VA_%", "Tx_EBE_%", "Tx_REX_%"}
        assert cols.issubset(set(data.sig_annuel.columns))

    def test_mc_inferieur_ca(self, data):
        """MC ≤ CA pour tous les sites (on soustrait le CAMV)."""
        for site in data.sites:
            ca = data.sig_annuel.loc[site, "CA_net"]
            mc = data.sig_annuel.loc[site, "MC"]
            assert mc <= ca + 0.01, (
                f"{site} : MC ({mc:.0f}) > CA ({ca:.0f}) — incohérence SIG"
            )

    def test_va_inferieure_mc(self, data):
        """VA ≤ MC pour tous les sites (on soustrait les services extérieurs)."""
        for site in data.sites:
            mc = data.sig_annuel.loc[site, "MC"]
            va = data.sig_annuel.loc[site, "VA"]
            assert va <= mc + 0.01, (
                f"{site} : VA ({va:.0f}) > MC ({mc:.0f}) — les services ext. ne peuvent pas être positifs en net"
            )

    def test_ebe_inferieur_va(self, data):
        """EBE ≤ VA pour tous les sites (on soustrait le personnel et impôts)."""
        for site in data.sites:
            va  = data.sig_annuel.loc[site, "VA"]
            ebe = data.sig_annuel.loc[site, "EBE"]
            assert ebe <= va + 0.01, (
                f"{site} : EBE ({ebe:.0f}) > VA ({va:.0f})"
            )

    def test_rex_inferieur_ebe(self, data):
        """REX ≤ EBE (on soustrait les dotations)."""
        for site in data.sites:
            ebe = data.sig_annuel.loc[site, "EBE"]
            rex = data.sig_annuel.loc[site, "REX"]
            assert rex <= ebe + 0.01, (
                f"{site} : REX ({rex:.0f}) > EBE ({ebe:.0f})"
            )

    def test_ca_positif_tous_sites(self, data):
        """Le CA net budget est positif pour tous les sites."""
        for site in data.sites:
            ca = data.sig_annuel.loc[site, "CA_net"]
            assert ca > 0, f"{site} : CA budget nul ou négatif ({ca:.0f}€)"

    def test_taux_mc_positif(self, data):
        """Le taux de marge commerciale est positif."""
        for site in data.sites:
            tx = data.sig_annuel.loc[site, "Tx_MC_%"]
            assert tx > 0, f"{site} : Tx_MC = {tx:.1f}% ≤ 0"

    def test_taux_mc_sectoriel(self, data):
        """Taux de marge entre 25% et 55% — plage sectorielle négoce B2B."""
        for site in data.sites:
            tx = data.sig_annuel.loc[site, "Tx_MC_%"]
            assert 25 <= tx <= 55, (
                f"{site} : Tx_MC = {tx:.1f}% hors plage sectorielle [25, 55]%"
            )

    def test_sig_ytd_index(self, data):
        assert set(data.sig_ytd.index) == set(data.sites)

    def test_sig_ytd_colonnes_bgt_rel(self, data):
        """sig_ytd doit avoir les colonnes _bgt et _rel pour chaque KPI."""
        for kpi in ("CA_net", "EBE", "REX"):
            assert f"{kpi}_bgt" in data.sig_ytd.columns
            assert f"{kpi}_rel" in data.sig_ytd.columns

    def test_sig_mensuel_format(self, data):
        """sig_mensuel doit contenir 7 KPIs × 7 sites × 12 mois = 588 lignes."""
        assert len(data.sig_mensuel) == 7 * 7 * 12, (
            f"Attendu 588 lignes, obtenu {len(data.sig_mensuel)}"
        )

    def test_sig_mensuel_mois_reel_a_du_reel(self, data, mois_reel):
        """Les mois ≤ mois_reel ont des données réelles non nulles."""
        df_m = data.sig_mensuel[
            (data.sig_mensuel["mois"] <= mois_reel) &
            (data.sig_mensuel["kpi"] == "CA_net")
        ]
        assert df_m["reel"].notna().all(), (
            "Mois réalisés avec reel = NaN dans sig_mensuel"
        )

    def test_sig_mensuel_mois_futurs_sans_reel(self, data, mois_reel):
        """Les mois > mois_reel ont reel = NaN."""
        df_m = data.sig_mensuel[
            (data.sig_mensuel["mois"] > mois_reel) &
            (data.sig_mensuel["kpi"] == "CA_net")
        ]
        assert df_m["reel"].isna().all(), (
            "Mois futurs avec reel ≠ NaN dans sig_mensuel"
        )


# ─── Enrichissement ─────────────────────────────────────────────────────────

class TestEnrichissement:

    def test_colonnes_enrichies_presentes(self, data):
        attendues = {"ecart_absolu", "ecart_pct", "tx_realisation",
                     "est_realise", "est_favorable", "ordre_classe"}
        assert attendues.issubset(set(data.df.columns))

    def test_ecart_absolu_calcul(self, data):
        """ecart_absolu = montant_reel - montant_budget pour les mois réalisés."""
        df_r = data.df[data.df["est_realise"]].head(200)
        ecart_calcule = df_r["montant_reel"] - df_r["montant_budget"]
        pd.testing.assert_series_equal(
            df_r["ecart_absolu"].reset_index(drop=True),
            ecart_calcule.reset_index(drop=True),
            check_names=False,
            atol=0.01,
        )

    def test_ecart_absolu_nan_pour_futurs(self, data, mois_reel):
        """ecart_absolu = NaN pour les mois non réalisés."""
        df_fut = data.df[data.df["mois"] > mois_reel]
        assert df_fut["ecart_absolu"].isna().all()

    def test_est_realise_coherent(self, data, mois_reel):
        """est_realise=True ↔ mois ≤ mois_reel ET montant_reel notna."""
        df = data.df.copy()
        attendu = (df["mois"] <= mois_reel) & df["montant_reel"].notna()
        assert (df["est_realise"] == attendu).all()

    def test_est_favorable_produit_favorable(self, data):
        """Sur un compte à sens=+1, réel > budget → est_favorable=True.

        Note : on filtre explicitement sur sens=+1 pour exclure les 709xxx
        (RRR accordés, sens=-1) : sur ces comptes, réel > budget = plus de
        remises accordées = défavorable — est_favorable=False est correct.
        """
        df_prod = data.df[
            (data.df["classe_cdg"] == "Produits") &
            (data.df["sens"] == 1) &
            data.df["est_realise"] &
            (data.df["montant_reel"] > data.df["montant_budget"])
        ]
        if len(df_prod) > 0:
            assert df_prod["est_favorable"].all(), (
                "Compte Produits (sens=+1) avec réel>budget mais est_favorable≠True"
            )

    def test_est_favorable_charge_defavorable(self, data):
        """Une charge avec |réel| > |budget| doit avoir est_favorable=False."""
        df_ch = data.df[
            (data.df["classe_cdg"] == "Charges personnel") &
            data.df["est_realise"] &
            (data.df["montant_reel"] < data.df["montant_budget"])  # plus négatif = plus de charges
        ]
        if len(df_ch) > 0:
            # Pandas 3.x : ~ sur bool peut lever une erreur, on utilise == False
            assert (df_ch["est_favorable"] == False).all()

    def test_ordre_classe_toutes_classes_mappees(self, data):
        """Toutes les classes doivent avoir un ordre_classe valide (< 99)."""
        classes_sans_ordre = data.df[data.df["ordre_classe"] == 99]["classe_cdg"].unique()
        assert len(classes_sans_ordre) == 0, (
            f"Classes sans ordre_affichage : {classes_sans_ordre}"
        )

    def test_df_sites_enrichi_avec_kpis(self, data):
        """df_sites doit contenir les colonnes de KPIs budgétaires."""
        kpi_cols = {"ca_budget", "ebe_budget", "rex_budget", "tx_ebe_budget"}
        assert kpi_cols.issubset(set(data.df_sites.columns))


# ─── Helpers publics ────────────────────────────────────────────────────────

class TestHelpers:

    def test_get_site_data_filtre(self, data):
        from loader import get_site_data
        df = get_site_data(data, "LYO_C")
        assert set(df["site_code"].unique()) == {"LYO_C"}
        assert len(df["mois"].unique()) == 12

    def test_get_site_data_plage_mois(self, data):
        from loader import get_site_data
        df = get_site_data(data, "LYO_C", mois_min=1, mois_max=4)
        assert df["mois"].max() == 4
        assert df["mois"].min() == 1

    def test_get_ytd_by_classe_toutes_classes(self, data, mois_reel):
        from loader import get_ytd_by_classe
        df = get_ytd_by_classe(data)
        # Doit contenir toutes les classes présentes dans les données
        classes_data = set(data.df["classe_cdg"].unique())
        classes_ytd  = set(df["classe_cdg"].unique())
        assert classes_data == classes_ytd

    def test_get_ytd_by_classe_filtre_site(self, data):
        from loader import get_ytd_by_classe
        df = get_ytd_by_classe(data, site_code="VLF")
        assert len(df) > 0
        assert "budget" in df.columns and "reel" in df.columns

    def test_get_top_ecarts_defavorables(self, data):
        from loader import get_top_ecarts
        top = get_top_ecarts(data, n=5, sens_ecart="defavorable")
        assert len(top) <= 5
        # Tous les écarts doivent être défavorables (est_favorable=False)
        assert (~top["est_favorable"]).all()

    def test_get_top_ecarts_favorables(self, data):
        from loader import get_top_ecarts
        top = get_top_ecarts(data, n=5, sens_ecart="favorable")
        assert len(top) <= 5
        assert top["est_favorable"].all()

    def test_get_heatmap_data_dimensions(self, data):
        from loader import get_heatmap_data
        pivot = get_heatmap_data(data, kpi="EBE", base="ecart_pct")
        assert set(pivot.index) == set(data.sites)
        assert set(pivot.columns) == set(range(1, 13))

    def test_get_waterfall_data_keys(self, data, mois_reel):
        from loader import get_waterfall_data
        wf = get_waterfall_data(data, "LYO_C", mois_reel)
        assert {"drivers", "total_bgt", "total_rel", "ecart_total"} == set(wf.keys())

    def test_get_waterfall_data_coherence(self, data, mois_reel):
        from loader import get_waterfall_data
        wf = get_waterfall_data(data, "LYO_C", mois_reel)
        assert abs(wf["ecart_total"] - (wf["total_rel"] - wf["total_bgt"])) < 0.01
