# FloMind — Budget Dashboard Multi-Sites

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://flomind-budget.streamlit.app)
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e.svg)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

> **Dashboard de pilotage budgétaire multi-sites** pour PME réseau (négoce, franchise, distribution B2B).
> Conçu par [FloMind Consulting](https://flomind.fr) — CDG × Data × IA pour PME.

---

## Pourquoi ce dashboard ?

Les PME réseau pilotent encore leur budget sous Excel. Le problème : **Excel dit où on en est, pas où on va finir.**

Ce dashboard répond aux trois questions que tout DG pose chaque mois :

| Question | Écran |
|---|---|
| 📍 Où en est chaque site par rapport au budget ? | Tour de contrôle |
| 🔍 D'où viennent les dérives ? | Analyse des écarts |
| 📡 Si on continue comme ça, on finit où ? | Rolling Forecast |

**Différenciateur clé vs Power BI / Excel** : deux références simultanées (budget statique + forecast rolling P10–P50–P90 avec bandes de confiance bootstrap). Le DG agit *avant* que le problème soit entièrement consommé.

---

## Captures d'écran

```
┌─────────────────────────────────────────────────────────────────┐
│  📊 Tour de contrôle réseau                                      │
│  CA YTD  │  Att. CA  │  EBE YTD  │  REX YTD  │  Att. EBE      │
│  1 434K€ │  4 202K€  │  87.6K€   │  61.4K€   │  254K€         │
│                                                                   │
│  [Waterfall Budget→Réel]   │  [Alertes réseau par priorité]     │
│  [Heatmap EBE sites×mois]                                        │
│  [Tableau atterrissages]   │  [Donut CA]  │  [Ranking REX]      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  📡 Rolling Forecast — LYO_E / EBE — Cadence 4+8               │
│                                                                   │
│  ·····Budget·····  ──Réel──  - - -Forecast P50- - -            │
│                              ░░░░░Bande P10-P90░░░░░            │
│                                                                   │
│  Budget: 34.9K€  │  YTD réel: -6.6K€  │  Forecast: -7.8K€     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Fonctionnalités

### 🗺️ Écran 1 — Tour de contrôle (vue DG)
- **KPI strip** : CA, EBE, REX — YTD réel vs budget + atterrissage fin d'exercice
- **Waterfall** YTD consolidé : décompose l'écart résultat par classe CDG
- **Heatmap** multi-sites × mois : vision simultanée de 7 sites
- **Alertes** par priorité (double critère : % ET € configurable)
- **Tableau atterrissage** : projection chaque site + consolidé groupe

### 📍 Écran 2 — Drill-down site (vue directeur de site)
- KPI strip avec taux de marge, EBE, REX + atterrissage
- Courbes mensuelles budget vs réel (sélecteur KPI)
- Tableau P&L complet par classe CDG × mois
- Top 8 dérives défavorables du site

### 🔍 Écran 3 — Analyse des écarts (vue CDG)
- Seuils de matérialité configurables (% et € séparément)
- Graphique Top N écarts (barres horizontales)
- Tableau détaillé avec priorité 1/2/3 et colorisation
- Waterfall mensuel interactif (site × mois sélectionnable)
- Zone commentaire CDG libre

### 📡 Écran 4 — Rolling Forecast
- Graphique : réel + P50 orange + bande P10–P90 transparente
- **4 méthodes** : Budget (baseline) / Tendance / WLS / Hybride (recommandé)
- Pondération dynamique selon la cadence (3+9, 4+8, 9+3…)
- Comparaison méthodes en tableau + forecast groupe consolidé

---

## Démarrage rapide

### Prérequis

- Python 3.11+

### Installation en 3 commandes

```bash
git clone https://github.com/FloMind/dashboard-budget-pilotage.git
cd dashboard-budget-pilotage
pip install -r requirements.txt
streamlit run app.py
```

Le dashboard s'ouvre sur `http://localhost:8501`.
Les données de démonstration (`data/sample_budget_v2.xlsx`) sont incluses dans le repo.

### Générer de nouvelles données de démo

```bash
python generators/generate_sample_v3.py
```

> ⚠️ **Ne jamais versionner de données clients réelles.**
> Le dossier `generators/` et les fichiers de données réels sont exclus par `.gitignore`.

---

## Architecture

```
dashboard-budget-pilotage/
│
├── app.py                       # Point d'entrée Streamlit (routing + styles)
│
├── core/                        # Logique métier — indépendante de Streamlit
│   ├── loader.py                # Lecture Excel, validation, enrichissement, SIG
│   ├── metrics.py               # KPIs, atterrissages, alertes, rankings
│   └── forecast.py              # Rolling forecast P10/P50/P90 (4 méthodes)
│
├── views/                       # Vues Streamlit (4 écrans)
│   ├── view_tour_de_controle.py
│   ├── view_drill_site.py
│   ├── view_ecarts.py
│   └── view_forecast.py
│
├── components/                  # Composants partagés inter-vues
│   ├── charts.py                # Constructeurs Plotly (waterfall, heatmap…)
│   └── formatters.py            # Formatage K€, %, delta couleur Streamlit
│
├── config/
│   └── settings.py              # Constantes métier centralisées
│
├── data/
│   └── sample_budget_v2.xlsx    # Données démo (96 comptes × 7 sites × 12 mois)
│
└── generators/                  # Usage interne uniquement — gitignored
    └── generate_sample_v3.py    # Générateur données synthétiques (PCG 2025)
```

**Principe de séparation** : `core/` ne sait pas que Streamlit existe.
Les vues ne font que de l'affichage. Ce découplage permet de réutiliser
`core/` dans des notebooks, une API ou un autre frontend sans modification.

---

## Stack

| Couche | Technologie | Version | Rôle |
|---|---|---|---|
| UI | Streamlit | 1.56 | Interface interactive, thème dark custom |
| Visualisation | Plotly | 6.7 | Waterfall, heatmap, forecast, barres |
| Données | Pandas | 3.0 | Transformations, agrégations SIG |
| Calcul | NumPy | 2.4 | SIG, bootstrap P10/P90 |
| Source | openpyxl | 3.1 | Lecture Excel 3 onglets |

---

## Plan comptable

**96 comptes PCG 2025** organisés en 15 classes analytiques.
SIG complets calculés à 3 granularités : annuel budget, YTD réel vs budget, mensuel.

```
Produits (707-775) → Achats (60x) → Services ext. 61 → Services ext. 62
→ Impôts et taxes → Charges personnel → Autres charges → Dotations
→ Produits/Charges financiers → Exceptionnel → IS
```

**Convention de signe comptable** : produits `(+)` / charges `(-)` / résultat = Σ toutes lignes.
Cette convention simplifie tous les calculs SIG à de simples sommes.

---

## Méthodes de forecast

| Méthode | Principe | Quand l'utiliser |
|---|---|---|
| Budget | Réel YTD + budget restant tel quel | Baseline optimiste |
| Tendance | Ratio YTD appliqué au budget restant | Présentations Codir |
| WLS | Régression pondérée (mois récents = + poids) | Mois 7+ |
| **Hybride** | 55% tendance + 45% WLS (pondération dynamique) | **Recommandé** |

Les bandes P10/P90 sont calculées par **bootstrap** sur 1 000 simulations des résidus historiques.

---

## Déploiement Streamlit Cloud

```
share.streamlit.io → New app → Repo: FloMind/dashboard-budget-pilotage
                            → Branch: main
                            → Main file: app.py
```

---

## Réutilisation

- **Autre plan comptable** : remplacer `data/sample_budget_v2.xlsx` (même format 3 onglets)
- **Autre secteur** : ajuster les classes dans `ref_comptes` — la logique SIG est générique
- **Dashboard P&L** : `core/loader.py` est compatible avec `FloMind/dashboard-pl-multisite`

---

## Roadmap

- [ ] Authentification RBAC (DG / directeur site) — `bcrypt`
- [ ] Export PDF 3 pages automatique — `fpdf2`
- [ ] Commentaires CDG persistants — `commentaires.json`
- [ ] Comparaison N-1 (données historiques)
- [ ] Intégration API ERP (Sage, Cegid)

---

## Auteur

**Florent — FloMind Consulting**
CDG × Data × IA pour PME · Ain / Rhône / Saône-et-Loire

[![LinkedIn](https://img.shields.io/badge/LinkedIn-FloMind-0A66C2?logo=linkedin)](https://linkedin.com/in/flomind)
[![GitHub](https://img.shields.io/badge/GitHub-FloMind-181717?logo=github)](https://github.com/FloMind)

*Certification Data Scientist — Mines Paris PSL (2025)*
*~13 ans en contrôle de gestion multi-sites*

---

## Licence

MIT — voir [LICENSE](LICENSE).
Les données synthétiques (`data/`) ne représentent aucune entreprise réelle.
