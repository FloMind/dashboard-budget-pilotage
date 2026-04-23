# FloMind — Dashboard Budget Multi-Sites

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io)
[![Pytest](https://img.shields.io/badge/tests-133%20passed-22c55e)](tests/)
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e.svg)](LICENSE)

> **Dashboard de pilotage budgétaire multi-sites** pour PME réseau (négoce, franchise, distribution B2B).
> Conçu par FloMind Consulting — CDG × Data × IA pour PME.

---

## Pourquoi ce dashboard ?

Les PME réseau pilotent encore leur budget sous Excel. Le problème : **Excel dit où on en est, pas où on va finir.**

| Question | Écran |
|---|---|
| Où en est chaque site par rapport au budget ? | Tour de contrôle |
| D'où viennent les dérives ? | Analyse des écarts |
| Si on continue comme ça, on finit où ? | Rolling Forecast |

**Différenciateur clé vs Power BI / Excel** : forecast rolling P10–P50–P90 avec bandes de confiance bootstrap. Le DG agit *avant* que le problème soit consommé.

---

## Fonctionnalités

- **Tour de contrôle** — KPI strip, waterfall YTD consolidé, heatmap multi-sites × mois, alertes par priorité, tableau atterrissage groupe
- **Drill-down site** — P&L mensuel, courbes budget vs réel, top dérives
- **Analyse des écarts** — double critère matérialité (% ET €), waterfall mensuel interactif, commentaire CDG
- **Rolling Forecast** — 4 méthodes (Budget / Tendance / WLS / Hybride), bandes P10–P50–P90 bootstrap, comparaison méthodes
- **Guide d'utilisation** — définitions SIG, lecture graphiques, logique alertes
- **Sélecteur de période** — rejouer le dashboard à n'importe quel mois (Jan → Déc)

---

## Démarrage rapide

### Windows — double-cliquer sur `launch.bat`

Crée automatiquement le venv, installe les dépendances et ouvre le navigateur.

### Ligne de commande

```bash
git clone https://github.com/FloMind/dashboard-budget-pilotage.git
cd dashboard-budget-pilotage
pip install -r requirements.txt
streamlit run app.py
```

---

## Architecture

```
dashboard-budget-pilotage/
├── app.py                       # Point d'entrée Streamlit (routing, sidebar, CSS)
├── loader.py                    # Lecture Excel, SIG, enrichissement, helpers
├── metrics.py                   # KPIs, atterrissages, alertes, rankings
├── forecast.py                  # Rolling forecast P10/P50/P90 (4 méthodes, bootstrap)
├── views/
│   ├── view_tour_de_controle.py
│   ├── view_drill_site.py
│   ├── view_ecarts.py
│   ├── view_forecast.py
│   └── view_aide.py             # Guide d'utilisation intégré
├── components/
│   ├── style.py                 # Système de design (CSS, KPI cards HTML, PLOTLY_THEME)
│   ├── charts.py                # Constructeurs Plotly
│   └── formatters.py
├── config/settings.py
├── .streamlit/config.toml       # Thème Light Pro (sidebar dark, fond clair)
├── data/sample_budget_v2.xlsx   # Données démo (96 comptes × 7 sites × 12 mois)
├── tests/                       # 133 tests pytest
├── launch.bat                   # Lanceur Windows
└── launch.sh                    # Lanceur macOS/Linux
```

---

## Stack

| Technologie | Version | Rôle |
|---|---|---|
| Streamlit | 1.56 | Interface web |
| Plotly | 6.7 | Graphiques interactifs |
| Pandas | 3.0 | DataFrames, agrégations SIG |
| NumPy | 2.4 | Bootstrap P10/P90, WLS |
| openpyxl | 3.1 | Lecture Excel |

---

## Méthodes de forecast

| Méthode | Principe |
|---|---|
| Budget | Réel YTD + budget restant |
| Tendance | Ratio YTD appliqué au budget restant |
| WLS | Régression pondérée (decay=0.75, mois récents prioritaires) |
| **Hybride** | **55% Tendance + 45% WLS — recommandé** |

P50 = médiane bootstrap (pas le forecast déterministe) — P10 ≤ P50 ≤ P90 garanti sur 2 688 combinaisons testées.

---

## Tests

```bash
pytest tests/ -v   # 133 passed
```

---

## Déploiement Streamlit Cloud

```
share.streamlit.io → New app
  Repository : FloMind/dashboard-budget-pilotage
  Branch     : main
  Main file  : app.py
```

---

## Roadmap

- [ ] Authentification RBAC (bcrypt)
- [ ] Export PDF (fpdf2)
- [ ] Commentaires CDG persistants
- [ ] Comparaison N-1
- [ ] GitHub Actions CI

---

## Auteur

**Florent — FloMind Consulting**
CDG × Data × IA pour PME · Ain / Rhône / Saône-et-Loire

*Certification Data Scientist — Mines Paris PSL (2025)*
*~13 ans en contrôle de gestion multi-sites*

---

MIT License — Les données synthétiques ne représentent aucune entreprise réelle.
