# FloMind — Dashboard Budget Multi-Sites

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://dashboard-budget-pilotage.streamlit.app/)
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
| Quelle est ma meilleure estimation révisée ? | Reforecast CDG |

**Différenciateur clé vs Power BI / Excel** : forecast rolling P10–P50–P90 avec bandes de confiance bootstrap + reforecast CDG par hypothèses opérationnelles typées. Le DG agit *avant* que le problème soit consommé.

---

## Fonctionnalités

### Tour de contrôle (vue DG)
- **KPI strip** — cascade SIG : CA réel | Taux marge brute | VA | EBE (≈ EBITDA) | Atterrissage CA | Atterrissage EBE
- **Section Valeur Ajoutée** — tableau taux VA % CA par site (réel vs budget) + bar chart comparatif
- **Alertes réseau** — double critère matérialité (% ET €), 3 niveaux P1/P2/P3
- **Waterfall consolidé** — décomposition Budget → Réel par classe PCG
- **Heatmap EBE** — multi-sites × 12 mois (sélecteur : EBE / CA / VA / MC / REX)
- **Tableau atterrissage réseau** — tous sites + consolidé, donut CA, ranking REX

### Drill-down site (vue directeur de site)
- P&L mensuel complet, courbes budget vs réel, top dérives du site

### Analyse des écarts (vue CDG)
- Double critère matérialité, waterfall mensuel interactif, commentaire CDG

### Rolling Forecast
- 4 méthodes : Budget / Tendance / WLS (decay=0.75) / **Hybride (55%T+45%WLS — recommandé)**
- Bootstrap 1 000 simulations → bandes P10–P50–P90 garanties (P10 ≤ P50 ≤ P90)
- Validé sur 2 688 combinaisons (4 périodes × 7 sites × 3 KPIs × 4 méthodes × 12 mois)

### Reforecast CDG — hypothèses typées
- **58 hypothèses** réparties en 5 catégories :
  - 🔵 CA & Commercial (14) — perte client, nouveau contrat, AO, saisonnalité…
  - 🟢 Achats & Marge brute (10) — hausse fournisseur, rupture, RFA, mix produit…
  - 🟠 Charges de personnel (12) — recrutement, départ, NAO, intérim, prime…
  - 🔴 Services ext. & Frais généraux (12) — loyer, travaux, énergie, IT… *(impact VA → EBE)*
  - ⚪ Événements exceptionnels (10) — sinistre, provision, subvention, redressement…
- **Cascade SIG correcte** : CA → MC (via taux marge) → VA (services ext.) → EBE (personnel)
- Prévisualisation instantanée de l'impact avant validation
- Graphique 4 courbes : Budget / Réel / Reforecast CDG / Atterrissage algo
- Persistance `data/hypotheses.json` (gitignored)

### Sélecteur de période
- `st.select_slider` sidebar : Jan → mois réalisé
- `@st.cache_data` sur `get_filtered_data(mois_sel)` — 0 rechargement Excel

### Guide d'utilisation
- Définitions SIG, lecture graphiques, logique alertes, glossaire CDG

---

## Données démo — 7 profils narratifs

Les données synthétiques (`data/sample_budget_v2.xlsx`) racontent une histoire réelle :

| Site | Profil | Scénario |
|---|---|---|
| LYO_C | ⭐ Site star | +8.8% CA, marge excellente, EBE quasi doublé |
| LYO_E | ⚠️ Dérive achats | Rupture fournisseur → taux MC -11 pts → EBE rouge |
| VLF | 📉 Perte client | CA -14.8% à partir d'avril, provision créance |
| MCN | 🔴 Pression achat | CA conforme mais EBE négatif (achats +9.8%) |
| BGR | ❌ Sous-performance structurelle | Tout rouge, -12.5% CA chronique |
| CLM | 🔄 Redressement | Rouge T1-T2, retour orange T3, vert T4 |
| ANC | 🚀 Nouveau site | Démarrage lent, surcoûts ouverture, accélération T3 |

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

### Régénérer les données démo

```bash
python generators/generate_sample_v3.py
```

---

## Architecture

```
dashboard-budget-pilotage/
├── app.py                        # Point d'entrée Streamlit (routing, sidebar, CSS)
├── loader.py                     # Lecture Excel, SIG, enrichissement, helpers
├── metrics.py                    # KPIs, atterrissages, alertes, rankings
├── forecast.py                   # Rolling forecast P10/P50/P90 (4 méthodes, bootstrap)
├── hypotheses_store.py           # Bibliothèque 58 hypothèses + calcul cascade SIG + persistance JSON
├── views/
│   ├── view_tour_de_controle.py  # KPI strip + VA + Alertes + Waterfall + Heatmap + Atterrissage
│   ├── view_drill_site.py        # Drill-down site
│   ├── view_ecarts.py            # Analyse des écarts
│   ├── view_forecast.py          # Rolling forecast
│   ├── view_reforecast_cdg.py    # Reforecast CDG — 58 hypothèses typées
│   └── view_aide.py              # Guide d'utilisation intégré
├── components/
│   ├── style.py                  # Système de design (CSS, KPI cards HTML, PLOTLY_THEME)
│   ├── charts.py                 # Constructeurs Plotly
│   └── formatters.py
├── config/settings.py
├── .streamlit/config.toml        # Thème Light Pro (sidebar dark #1A2B4A, fond #F4F7FC)
├── data/
│   ├── sample_budget_v2.xlsx     # Données démo 7 profils narratifs (gittracked)
│   ├── reforecast.json           # Reforecast manuel (gitignored)
│   └── hypotheses.json           # Hypothèses CDG (gitignored)
├── generators/
│   └── generate_sample_v3.py     # Générateur données démo (gitignored)
├── tests/                        # 133 tests pytest
├── requirements.txt              # Dépendances production (Streamlit Cloud)
├── requirements-dev.txt          # Dépendances développement (pytest, black, ruff, mypy)
├── launch.bat                    # Lanceur Windows (auto venv + port conflict detection)
└── launch.sh                     # Lanceur macOS/Linux
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

## Cascade SIG

```
CA net ≥ MC ≥ VA ≥ EBE ≥ REX   (validé pour tous sites, toutes périodes)

Convention de signe PCG :
  est_favorable = ecart_absolu > 0   (universel, tous comptes)
  REX exclu du KPI strip : dotations figées, non actionnable mensuellement
```

---

## Méthodes de forecast

| Méthode | Principe |
|---|---|
| Budget | Réel YTD + budget restant |
| Tendance | Ratio YTD appliqué au budget restant |
| WLS | Régression pondérée (decay=0.75, mois récents prioritaires) |
| **Hybride** | **55% Tendance + 45% WLS — recommandé** |

P50 = médiane bootstrap sur 1 000 simulations (pas le forecast déterministe).  
P10 ≤ P50 ≤ P90 garanti par construction sur 2 688 combinaisons testées.

---

## Tests

```bash
# Lancer tous les tests
pytest tests/ -v   # 133 passed

# Avec coverage
pytest tests/ --cov=. --cov-report=term-missing
```

---

## Déploiement Streamlit Cloud

```
share.streamlit.io → New app
  Repository : FloMind/dashboard-budget-pilotage
  Branch     : main
  Main file  : app.py
```

> ⚠️ **Note** : l'authentification RBAC (bcrypt) n'est pas encore activée.
> Le dashboard est accessible sans login — à ne pas déployer avec des données réelles
> avant activation de l'auth.

---

## Roadmap

- [ ] Authentification RBAC (bcrypt) — bloquant pour déploiement multi-utilisateurs
- [ ] Export PDF (fpdf2) — livrable Codir
- [ ] Comparaison N-1
- [ ] Commentaires CDG persistants
- [ ] GitHub Actions CI
- [x] Reforecast CDG — 58 hypothèses typées avec cascade SIG
- [x] KPI strip cascade SIG (CA / Tx Marge / VA / EBE / Atterrissages)
- [x] Données démo narratives (7 profils contrastés)
- [x] Layout tour de contrôle optimisé (VA + Alertes en tête)

---

## Auteur

**Florent — FloMind Consulting**  
CDG × Data × IA pour PME · Ain / Rhône / Saône-et-Loire

*Certification Data Scientist — Mines Paris PSL (2025)*  
*~13 ans en contrôle de gestion multi-sites*

---

MIT License — Les données synthétiques ne représentent aucune entreprise réelle.
