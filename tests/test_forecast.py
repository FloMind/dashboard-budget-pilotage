"""
tests/test_forecast.py
Tests du module rolling forecast (forecast.py).

Couvre :
  - Structure ForecastResult
  - Cohérence des 4 méthodes
  - Bandes P10 ≤ P50 ≤ P90
  - Agrégats annuels
  - forecast_to_dataframe
  - multi_methode_forecast
  - forecast_groupe
"""
import pytest
import numpy as np
import pandas as pd


METHODES = ["budget", "tendance", "wls", "hybride"]
KPIS     = ["CA_net", "EBE", "REX"]
SITES    = ["LYO_C", "LYO_E", "VLF"]  # sous-ensemble pour rapidité


# ─── ForecastResult — structure ─────────────────────────────────────────────

class TestForecastResultStructure:

    def test_rolling_forecast_retourne_result(self, data):
        from forecast import rolling_forecast
        r = rolling_forecast(data, "LYO_C", "CA_net", "hybride", n_sim=100)
        assert r is not None

    def test_series_longueur_12(self, data):
        from forecast import rolling_forecast
        r = rolling_forecast(data, "LYO_C", "CA_net", "hybride", n_sim=100)
        assert len(r.mois)          == 12
        assert len(r.budget)        == 12
        assert len(r.reel)          == 12
        assert len(r.forecast_p50)  == 12
        assert len(r.forecast_p10)  == 12
        assert len(r.forecast_p90)  == 12
        assert len(r.is_forecast)   == 12

    def test_mois_realises_is_forecast_false(self, data, mois_reel):
        from forecast import rolling_forecast
        r = rolling_forecast(data, "LYO_C", "CA_net", "hybride", n_sim=100)
        for i in range(mois_reel):
            assert r.is_forecast[i] is False

    def test_mois_futurs_is_forecast_true(self, data, mois_reel):
        from forecast import rolling_forecast
        r = rolling_forecast(data, "LYO_C", "CA_net", "hybride", n_sim=100)
        for i in range(mois_reel, 12):
            assert r.is_forecast[i] is True

    def test_reel_nan_pour_futurs(self, data, mois_reel):
        from forecast import rolling_forecast
        r = rolling_forecast(data, "LYO_C", "CA_net", "hybride", n_sim=100)
        for i in range(mois_reel, 12):
            assert r.reel[i] is None

    def test_reel_present_pour_realises(self, data, mois_reel):
        from forecast import rolling_forecast
        r = rolling_forecast(data, "LYO_C", "CA_net", "hybride", n_sim=100)
        for i in range(mois_reel):
            assert r.reel[i] is not None

    def test_methode_inconnue_leve_erreur(self, data):
        from forecast import rolling_forecast
        with pytest.raises(ValueError, match="Méthode inconnue"):
            rolling_forecast(data, "LYO_C", "CA_net", "methode_inexistante")

    def test_attributs_site_kpi_methode(self, data):
        from forecast import rolling_forecast
        r = rolling_forecast(data, "BGR", "EBE", "tendance", n_sim=100)
        assert r.site_code == "BGR"
        assert r.kpi       == "EBE"
        assert r.methode   == "tendance"
        assert r.annee     == 2025


# ─── Cohérence des méthodes ──────────────────────────────────────────────────

class TestCoherenceMethodes:

    @pytest.mark.parametrize("methode", METHODES)
    def test_methode_tourne(self, data, methode):
        from forecast import rolling_forecast
        r = rolling_forecast(data, "LYO_C", "CA_net", methode, n_sim=100)
        assert r.total_forecast is not None

    @pytest.mark.parametrize("methode", METHODES)
    def test_total_forecast_positif_pour_ca(self, data, methode):
        """Le forecast CA doit être positif pour tous les sites matures."""
        from forecast import rolling_forecast
        r = rolling_forecast(data, "LYO_C", "CA_net", methode, n_sim=100)
        assert r.total_forecast > 0

    def test_methode_budget_egal_ytd_plus_reste_budget(self, data, mois_reel):
        """Méthode budget : forecast = réel YTD + budget restant."""
        from forecast import rolling_forecast
        r = rolling_forecast(data, "LYO_C", "CA_net", "budget", n_sim=100)
        # total_forecast ≈ total_reel_ytd + Σ budget[mois_reel:]
        budget_total = sum(r.budget)
        budget_ytd   = sum(r.budget[:mois_reel])
        budget_reste = budget_total - budget_ytd
        attendu = r.total_reel_ytd + budget_reste
        assert abs(r.total_forecast - attendu) < 1.0

    def test_total_reel_ytd_coherent(self, data, mois_reel):
        from forecast import rolling_forecast
        r = rolling_forecast(data, "LYO_C", "CA_net", "hybride", n_sim=100)
        # total_reel_ytd = somme des réels réalisés
        ytd_calcule = sum(v for v in r.reel[:mois_reel] if v is not None)
        assert abs(r.total_reel_ytd - ytd_calcule) < 1.0

    def test_ecart_pct_calcule(self, data):
        from forecast import rolling_forecast
        r = rolling_forecast(data, "VLF", "CA_net", "hybride", n_sim=100)
        if abs(r.total_budget) > 1:
            attendu = (r.total_forecast - r.total_budget) / abs(r.total_budget) * 100
            assert abs(r.ecart_pct - attendu) < 0.1


# ─── Bandes de confiance ────────────────────────────────────────────────────

class TestBandesConfiance:

    def test_p10_inferieur_p50_inferieur_p90(self, data, mois_reel):
        """P10 ≤ P50 ≤ P90 pour tous les mois futurs — garanti par construction.

        Depuis le fix bootstrap : forecast_p50 est la MÉDIANE des simulations
        bootstrap (percentile 50), et non plus le forecast déterministe.
        P10/P50/P90 sont tous issus de la même distribution → ordre garanti.
        """
        from forecast import rolling_forecast
        from loader import filter_to_mois
        data8 = filter_to_mois(data, min(data.mois_reel, 8))
        r = rolling_forecast(data8, "LYO_E", "CA_net", "hybride", n_sim=500)
        mr = data8.mois_reel
        for i in range(mr, 12):
            assert r.forecast_p10[i] <= r.forecast_p50[i] + 0.01, (
                f"Mois {i+1} : P10 ({r.forecast_p10[i]:.0f}) > P50 ({r.forecast_p50[i]:.0f})"
            )
            assert r.forecast_p50[i] <= r.forecast_p90[i] + 0.01, (
                f"Mois {i+1} : P50 ({r.forecast_p50[i]:.0f}) > P90 ({r.forecast_p90[i]:.0f})"
            )

    def test_p50_inferieur_p90(self, data, mois_reel):
        """P50 ≤ P90 pour tous les mois futurs."""
        from forecast import rolling_forecast
        r = rolling_forecast(data, "LYO_C", "CA_net", "hybride", n_sim=200)
        for i in range(mois_reel, 12):
            assert r.forecast_p50[i] <= r.forecast_p90[i] + 0.01

    def test_total_p10_inferieur_p50_inferieur_p90(self, data):
        from forecast import rolling_forecast
        from loader import filter_to_mois
        data8 = filter_to_mois(data, min(data.mois_reel, 8))
        r = rolling_forecast(data8, "LYO_E", "CA_net", "hybride", n_sim=500)
        assert r.total_p10 <= r.total_forecast, \
            f"total P10 ({r.total_p10:.0f}) > P50 ({r.total_forecast:.0f})"
        assert r.total_forecast <= r.total_p90, \
            f"total P50 ({r.total_forecast:.0f}) > P90 ({r.total_p90:.0f})"

    def test_bandes_mois_realises_egal_reel(self, data, mois_reel):
        """Pour les mois réalisés, P10=P50=P90=réel (certitude totale)."""
        from forecast import rolling_forecast
        r = rolling_forecast(data, "LYO_C", "CA_net", "hybride", n_sim=100)
        for i in range(mois_reel):
            assert abs(r.forecast_p10[i] - r.forecast_p50[i]) < 0.01
            assert abs(r.forecast_p90[i] - r.forecast_p50[i]) < 0.01

    @pytest.mark.parametrize("site", SITES)
    def test_bandes_positives_pour_ca(self, data, site, mois_reel):
        """Les bandes du CA doivent être positives."""
        from forecast import rolling_forecast
        r = rolling_forecast(data, site, "CA_net", "hybride", n_sim=100)
        assert r.total_p10 > 0
        assert r.total_p90 > 0


# ─── forecast_to_dataframe ───────────────────────────────────────────────────

class TestForecastToDataframe:

    def test_retourne_dataframe(self, data):
        from forecast import rolling_forecast, forecast_to_dataframe
        r  = rolling_forecast(data, "LYO_C", "REX", "hybride", n_sim=100)
        df = forecast_to_dataframe(r)
        assert isinstance(df, pd.DataFrame)

    def test_12_lignes(self, data):
        from forecast import rolling_forecast, forecast_to_dataframe
        r  = rolling_forecast(data, "LYO_C", "REX", "hybride", n_sim=100)
        df = forecast_to_dataframe(r)
        assert len(df) == 12

    def test_colonnes_attendues(self, data):
        from forecast import rolling_forecast, forecast_to_dataframe
        r  = rolling_forecast(data, "LYO_C", "CA_net", "hybride", n_sim=100)
        df = forecast_to_dataframe(r)
        attendues = {"mois", "mois_label", "budget", "reel", "forecast_p50",
                     "forecast_p10", "forecast_p90", "is_forecast",
                     "valeur_active", "ecart_budget", "ecart_budget_pct"}
        assert attendues.issubset(set(df.columns))

    def test_valeur_active_reel_si_realise(self, data, mois_reel):
        from forecast import rolling_forecast, forecast_to_dataframe
        r  = rolling_forecast(data, "LYO_C", "CA_net", "hybride", n_sim=100)
        df = forecast_to_dataframe(r)
        df_r = df[~df["is_forecast"]]
        # valeur_active = reel pour les mois réalisés
        assert (df_r["valeur_active"] == df_r["reel"]).all()

    def test_valeur_active_p50_si_forecast(self, data, mois_reel):
        from forecast import rolling_forecast, forecast_to_dataframe
        r  = rolling_forecast(data, "LYO_C", "CA_net", "hybride", n_sim=100)
        df = forecast_to_dataframe(r)
        df_f = df[df["is_forecast"]]
        if len(df_f) > 0:
            assert (df_f["valeur_active"] == df_f["forecast_p50"]).all()

    def test_ecart_budget_calcule(self, data):
        from forecast import rolling_forecast, forecast_to_dataframe
        r  = rolling_forecast(data, "LYO_C", "CA_net", "budget", n_sim=100)
        df = forecast_to_dataframe(r)
        ecart_attendu = df["valeur_active"] - df["budget"]
        pd.testing.assert_series_equal(
            df["ecart_budget"].reset_index(drop=True),
            ecart_attendu.reset_index(drop=True),
            check_names=False, atol=0.01,
        )


# ─── multi_methode_forecast ─────────────────────────────────────────────────

class TestMultiMethode:

    def test_multi_retourne_dataframe(self, data):
        from forecast import multi_methode_forecast
        df = multi_methode_forecast(data, "LYO_C", "CA_net",
                                    methodes=["budget", "tendance", "hybride"])
        assert isinstance(df, pd.DataFrame)

    def test_multi_3_methodes_x_12_mois(self, data):
        from forecast import multi_methode_forecast
        df = multi_methode_forecast(data, "LYO_C", "CA_net",
                                    methodes=["budget", "tendance", "hybride"])
        assert len(df) == 3 * 12

    def test_multi_colonne_methode(self, data):
        from forecast import multi_methode_forecast
        df = multi_methode_forecast(data, "LYO_C", "CA_net",
                                    methodes=["budget", "tendance"])
        assert set(df["methode"].unique()) == {"budget", "tendance"}


# ─── forecast_groupe ────────────────────────────────────────────────────────

class TestForecastGroupe:

    def test_groupe_retourne_dataframe(self, data):
        from forecast import forecast_groupe
        df = forecast_groupe(data, kpi="CA_net", methode="hybride")
        assert isinstance(df, pd.DataFrame)

    def test_groupe_8_lignes(self, data):
        """7 sites + 1 ligne groupe = 8 lignes."""
        from forecast import forecast_groupe
        df = forecast_groupe(data, kpi="CA_net", methode="hybride")
        assert len(df) == 8

    def test_groupe_contient_ligne_groupe(self, data):
        from forecast import forecast_groupe
        df = forecast_groupe(data, kpi="CA_net", methode="hybride")
        assert "GROUPE" in df["site_code"].values

    def test_groupe_budget_somme_sites(self, data):
        """Budget groupe = Σ budgets sites."""
        from forecast import forecast_groupe
        df = forecast_groupe(data, kpi="CA_net", methode="budget")
        sites_bgt = df[df["site_code"] != "GROUPE"]["budget_annuel"].sum()
        groupe_bgt = float(df[df["site_code"] == "GROUPE"]["budget_annuel"].iloc[0])
        assert abs(sites_bgt - groupe_bgt) < 1.0


# ─── Utilitaires ────────────────────────────────────────────────────────────

class TestUtilitaires:

    @pytest.mark.parametrize("mois,attendu", [
        (1, "1+11"), (4, "4+8"), (9, "9+3"), (12, "12+0"),
    ])
    def test_cadence_label(self, mois, attendu):
        from forecast import cadence_label
        assert cadence_label(mois) == attendu
