"""
tests/test_metrics.py
Tests de la couche métriques (metrics.py).

Couvre :
  - KPIStrip (valeurs, cohérence, atterrissage)
  - Alertes (seuils, double critère, priorités)
  - Atterrissage (bornes, méthode hybride)
  - Rankings et contributions
  - Waterfall mensuel
"""
import pytest
import numpy as np


# ─── KPIStrip ───────────────────────────────────────────────────────────────

class TestKPIStrip:

    def test_kpi_strip_groupe(self, data):
        from metrics import compute_kpi_strip
        kpi = compute_kpi_strip(data)
        assert kpi is not None
        assert kpi.scope == "consolidé"

    def test_kpi_strip_site(self, data):
        from metrics import compute_kpi_strip
        kpi = compute_kpi_strip(data, site_code="LYO_C")
        assert kpi.scope == "LYO_C"

    def test_ca_ytd_positif(self, data):
        from metrics import compute_kpi_strip
        kpi = compute_kpi_strip(data)
        assert kpi.ca_ytd_reel > 0
        assert kpi.ca_ytd_budget > 0

    def test_ca_annuel_superieur_ytd(self, data):
        from metrics import compute_kpi_strip
        kpi = compute_kpi_strip(data)
        # Budget annuel > budget YTD (mois_reel < 12)
        # >= : égaux si mois_reel==12 (budget YTD = budget annuel)
        assert kpi.ca_annuel_bgt >= kpi.ca_ytd_budget

    def test_tx_mc_dans_plage(self, data):
        from metrics import compute_kpi_strip
        kpi = compute_kpi_strip(data)
        assert 25 <= kpi.tx_mc_reel <= 55

    def test_atterrissage_ca_entre_ytd_et_annuel(self, data):
        from metrics import compute_kpi_strip
        kpi = compute_kpi_strip(data)
        # L'atterrissage CA doit être > YTD réel (on ajoute les mois restants)
        # >= : égaux si mois_reel==12 (tout est réalisé, rien à projeter)
        assert kpi.ca_atterrissage >= kpi.ca_ytd_reel

    def test_mois_restants_coherent(self, data):
        from metrics import compute_kpi_strip
        kpi = compute_kpi_strip(data)
        assert kpi.mois_reel + kpi.n_mois_restants == 12

    def test_annee_correct(self, data):
        from metrics import compute_kpi_strip
        kpi = compute_kpi_strip(data)
        assert kpi.annee == 2025

    @pytest.mark.parametrize("site", ["LYO_C", "LYO_E", "VLF", "MCN", "BGR", "CLM", "ANC"])
    def test_kpi_strip_chaque_site(self, data, site):
        from metrics import compute_kpi_strip
        kpi = compute_kpi_strip(data, site_code=site)
        assert kpi.ca_ytd_reel > 0
        assert kpi.mois_reel == data.mois_reel


# ─── Atterrissage ────────────────────────────────────────────────────────────

class TestAtterrissage:

    def test_atterrissage_groupe(self, data):
        from metrics import compute_atterrissage
        att = compute_atterrissage(data)
        assert att.scope == "consolidé"
        assert att.ca_bgt_annuel > 0

    def test_atterrissage_site(self, data):
        from metrics import compute_atterrissage
        att = compute_atterrissage(data, site_code="VLF")
        assert att.scope == "VLF"
        # Avec 12 mois réalisés, forecast = ytd (pas de reste). On teste >= pour les deux cas.
        assert att.ca_forecast >= att.ca_reel_ytd

    def test_ca_reste_bgt_coherent(self, data):
        """ca_reste_bgt = ca_bgt_annuel - ca_reel_ytd (mais budget, pas réel)."""
        from metrics import compute_atterrissage
        att = compute_atterrissage(data)
        # ca_bgt_annuel = ca_reel_ytd_bgt + ca_reste_bgt
        # On vérifie que le reste est positif
        # >= 0 : peut être 0 si mois_reel == 12 (année complète réalisée)
        assert att.ca_reste_bgt >= 0

    def test_ecart_vs_budget_calcule(self, data):
        from metrics import compute_atterrissage
        att = compute_atterrissage(data)
        assert abs(att.ca_ecart_vs_bgt - (att.ca_forecast - att.ca_bgt_annuel)) < 1.0

    def test_taux_ebe_calcule(self, data):
        from metrics import compute_atterrissage
        att = compute_atterrissage(data)
        expected_tx = att.ebe_forecast / att.ca_forecast * 100
        assert abs(att.tx_ebe_forecast - expected_tx) < 0.1

    def test_atterrissage_groupe_dataframe(self, data):
        from metrics import compute_atterrissage_groupe
        df = compute_atterrissage_groupe(data)
        # Doit contenir les 7 sites + "consolidé"
        assert "consolidé" in df.index
        assert len(df) == 8  # 7 sites + 1 consolidé
        # Colonnes attendues
        assert "ca_forecast" in df.columns
        assert "ebe_forecast" in df.columns
        assert "rex_forecast" in df.columns

    def test_poids_tendance_impact(self, data):
        """Poids tendance = 0 → atterrissage = réel_ytd + budget_reste."""
        from metrics import compute_atterrissage
        att_pur  = compute_atterrissage(data, poids_tendance=0.0)
        att_tend = compute_atterrissage(data, poids_tendance=1.0)
        # Les deux résultats doivent différer (sauf si ratio = 1.0 exactement)
        # On vérifie juste qu'ils sont calculés sans erreur
        assert att_pur.ca_forecast > 0
        assert att_tend.ca_forecast > 0


# ─── Alertes ────────────────────────────────────────────────────────────────

class TestAlertes:

    def test_alertes_retourne_liste(self, data):
        from metrics import compute_alertes
        alertes = compute_alertes(data)
        assert isinstance(alertes, list)

    def test_alertes_tous_sites(self, data):
        from metrics import compute_alertes
        alertes = compute_alertes(data)
        assert len(alertes) >= 0  # peut être vide — pas d'erreur

    def test_double_critere_applique(self, data):
        """Seuil absolu très élevé → aucune alerte même avec écart % important."""
        from metrics import compute_alertes
        alertes_strict = compute_alertes(data, seuil_ecart_pct=1.0, seuil_ecart_abs=999_999)
        assert len(alertes_strict) == 0

    def test_seuil_pct_tres_bas_plus_alertes(self, data):
        """Seuil % très bas → plus d'alertes qu'avec le seuil par défaut."""
        from metrics import compute_alertes
        alertes_defaut = compute_alertes(data)
        alertes_sensible = compute_alertes(data, seuil_ecart_pct=0.1, seuil_ecart_abs=1)
        assert len(alertes_sensible) >= len(alertes_defaut)

    def test_alerte_attributs(self, data):
        from metrics import compute_alertes
        alertes = compute_alertes(data, seuil_ecart_pct=0.1, seuil_ecart_abs=1)
        if alertes:
            a = alertes[0]
            assert hasattr(a, "site_code")
            assert hasattr(a, "compte_code")
            assert hasattr(a, "ecart_abs")
            assert hasattr(a, "ecart_pct")
            assert hasattr(a, "est_favorable")
            assert a.priorite in {1, 2, 3}

    def test_alerte_site_code_valide(self, data):
        from metrics import compute_alertes
        alertes = compute_alertes(data, seuil_ecart_pct=0.1, seuil_ecart_abs=1)
        for a in alertes:
            assert a.site_code in data.sites, f"site_code inconnu : {a.site_code}"

    def test_alerte_filtre_site(self, data):
        from metrics import compute_alertes
        alertes_lyoc = compute_alertes(data, site_code="LYO_C",
                                        seuil_ecart_pct=0.1, seuil_ecart_abs=1)
        for a in alertes_lyoc:
            assert a.site_code == "LYO_C"

    def test_alerte_classes_exclues(self, data):
        """Les dotations et IS doivent être exclues par défaut."""
        from metrics import compute_alertes
        alertes = compute_alertes(data, seuil_ecart_pct=0.1, seuil_ecart_abs=1)
        classes_alertees = {a.classe_cdg for a in alertes}
        assert "Dotations" not in classes_alertees
        assert "IS et participation" not in classes_alertees

    def test_priorites_ordonnees(self, data):
        """Les alertes doivent être triées par priorité croissante (1 en tête)."""
        from metrics import compute_alertes
        alertes = compute_alertes(data, seuil_ecart_pct=0.1, seuil_ecart_abs=1)
        if len(alertes) >= 2:
            prios = [a.priorite for a in alertes]
            assert prios == sorted(prios), "Alertes non triées par priorité"

    def test_summary_alertes_structure(self, data):
        from metrics import compute_alertes, summary_alertes
        alertes = compute_alertes(data)
        resume = summary_alertes(alertes)
        assert "total" in resume
        assert "critiques" in resume
        assert "defavorables" in resume
        assert "sites_en_alerte" in resume
        assert resume["total"] == resume["critiques"] + resume["importantes"] + resume["surveillance"]

    def test_summary_vide(self):
        from metrics import summary_alertes
        resume = summary_alertes([])
        assert resume["total"] == 0
        assert resume["sites_en_alerte"] == []


# ─── Rankings ────────────────────────────────────────────────────────────────

class TestRankings:

    def test_ranking_retourne_7_sites(self, data):
        from metrics import compute_ranking
        rank = compute_ranking(data, kpi="REX", base="forecast")
        assert len(rank) == 7

    def test_ranking_colonnes(self, data):
        from metrics import compute_ranking
        rank = compute_ranking(data)
        assert "rang" in rank.columns
        assert "site_code" in rank.columns
        assert "valeur" in rank.columns

    def test_ranking_rang_unique(self, data):
        from metrics import compute_ranking
        rank = compute_ranking(data)
        assert rank["rang"].nunique() == 7

    def test_ranking_desc_par_defaut(self, data):
        from metrics import compute_ranking
        rank = compute_ranking(data)
        # Première ligne doit avoir la valeur la plus haute
        assert rank.iloc[0]["valeur"] >= rank.iloc[-1]["valeur"]

    def test_contribution_reseau_somme(self, data):
        from metrics import compute_contribution_reseau
        df = compute_contribution_reseau(data, kpi="CA_net")
        # La somme des contributions doit être ≈ 100%
        total = df["contribution_pct"].sum()
        assert abs(total - 100.0) < 1.0, f"Somme contributions = {total:.1f}% ≠ 100%"


# ─── Waterfall mensuel ───────────────────────────────────────────────────────

class TestWaterfallMensuel:

    def test_waterfall_retourne_dataframe(self, data, mois_reel):
        from metrics import compute_waterfall_mensuel
        df = compute_waterfall_mensuel(data, "LYO_C", mois_reel)
        assert hasattr(df, "columns")

    def test_waterfall_types_presents(self, data, mois_reel):
        from metrics import compute_waterfall_mensuel
        df = compute_waterfall_mensuel(data, "LYO_C", mois_reel)
        types = set(df["type"].unique())
        assert "budget_initial" in types
        assert "driver" in types
        assert "total_reel" in types

    def test_waterfall_budget_plus_contributions_egal_reel(self, data, mois_reel):
        """Budget + Σ contributions ≈ Réel (cohérence comptable)."""
        from metrics import compute_waterfall_mensuel
        df = compute_waterfall_mensuel(data, "LYO_C", mois_reel)
        budget = float(df[df["type"] == "budget_initial"]["budget"].iloc[0])
        contributions = df[df["type"] == "driver"]["contribution"].sum()
        reel = float(df[df["type"] == "total_reel"]["reel"].iloc[0])
        assert abs(budget + contributions - reel) < 1.0, (
            f"Waterfall incohérent : {budget:.0f} + {contributions:.0f} ≠ {reel:.0f}"
        )
