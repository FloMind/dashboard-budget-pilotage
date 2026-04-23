"""
tests/conftest.py
Fixtures pytest partagées — chargées une seule fois pour toute la suite.
"""
import pytest
import sys
from pathlib import Path

# Ajouter la racine du projet au path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def data():
    """DashboardData chargé une seule fois pour toute la session de tests."""
    from loader import load_data
    return load_data(ROOT / "data" / "sample_budget_v2.xlsx")


@pytest.fixture(scope="session")
def sites(data):
    return data.sites


@pytest.fixture(scope="session")
def mois_reel(data):
    return data.mois_reel
