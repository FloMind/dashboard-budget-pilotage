# Changelog

Toutes les modifications notables de ce projet sont documentées ici.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/),
et ce projet adhère au [Versionnage Sémantique](https://semver.org/lang/fr/).

Types d'entrées : `Ajouté` · `Modifié` · `Corrigé` · `Supprimé` · `Sécurité`

---

## [Non publié]

*(Fonctionnalités en cours de développement)*

### À venir
- Authentification RBAC : rôles DG (vue consolidée) et directeur de site (vue restreinte)
- Export PDF 3 pages automatique (fpdf2) : KPI strip, alertes, forecast
- Persistance des commentaires CDG (commentaires.json + interface d'édition)
- Comparaison N-1 : données réelles vs données de l'exercice précédent
- Intégration directe API ERP (Sage 100, Cegid X3)

---

## [1.0.0] — 2025-04-23

Première version complète du dashboard — livraison portfolio FloMind.

### Ajouté

**Couche données (`core/`)**
- `loader.py` : chargement et validation du fichier Excel 3 onglets (data, ref_sites, ref_comptes) avec détection automatique du mois courant, enrichissement (écart absolu, %, est_favorable, ordre_classe) et calcul des SIG à 3 granularités (annuel, YTD, mensuel)
- `metrics.py` : KPI strip (15 indicateurs), atterrissage hybride par site et groupe, alertes par double critère matérialité (% ET €), rankings multi-critères, contribution réseau, waterfall mensuel, évolution mensuelle
- `forecast.py` : rolling forecast P10/P50/P90 — 4 méthodes (Budget, Tendance, WLS, Hybride) avec pondération dynamique selon la cadence, bandes de confiance par bootstrap 1 000 simulations, forecast groupe consolidé

**Interface utilisateur (`views/`)**
- Écran 1 — Tour de contrôle : KPI strip, waterfall YTD consolidé, alertes réseau, heatmap EBE sites × mois, tableau atterrissages, donut contribution CA, ranking REX
- Écran 2 — Drill-down site : KPI strip site, courbes mensuelles (sélecteur KPI), tableau P&L classe × mois, top 8 dérives
- Écran 3 — Analyse des écarts : filtres configurables (seuil %, seuil €, sens, site), barres Top N, tableau détaillé colorisé, waterfall mensuel interactif, zone commentaire CDG
- Écran 4 — Rolling Forecast : graphique réel + P50 + bande P10-P90, comparaison 4 méthodes, tableau mensuel détaillé, vue groupe

**Composants partagés (`components/`)**
- `charts.py` : waterfall (go.Waterfall), heatmap (go.Heatmap), courbes mensuelles, graphique forecast avec pont réel→projection, barres horizontales écarts, donut contribution — thème dark slate cohérent
- `formatters.py` : fmt_ke(), fmt_pct(), fmt_ecart_ke(), delta_color(), priorite_label()

**Configuration et données**
- `config/settings.py` : constantes métier centralisées (seuils, chemins, labels, paramètres)
- `app.py` : routing Streamlit, thème CSS dark, sidebar avec statut EBE temps réel
- Plan comptable PCG 2025 — 96 comptes, 15 classes analytiques, SIG complets (MC → VA → EBE → REX → RCAI → RN)
- Données synthétiques — 7 sites Auvergne-Rhône-Alpes, profils distincts (site leader, problème fournisseur, dérive salariale, sous-performance CA, frais généraux excessifs, nouveau site)

**Générateur de données (`generators/`)**
- `generate_sample_v3.py` : 8 064 lignes × 7 sites × 96 comptes, calibration top-down EBE, saisonnalité négoce B2B, bruit stochastique reproductible (seed=42), validation SIG automatique à la génération

**Documentation**
- README.md : badges, valeur business, quickstart 3 commandes, architecture, stack, méthodes forecast, roadmap
- CHANGELOG.md (ce fichier) : format Keep a Changelog
- Docstrings exhaustives sur les 3 modules core (loader, metrics, forecast)

---

## Historique des décisions techniques

| Date | Décision | Justification |
|---|---|---|
| 2025-04 | Convention signe comptable (+ produits / - charges) | Résultat = simple somme, élimine les bugs de double négation |
| 2025-04 | Grain atomique site × mois × compte | Flexibilité maximale pour agrégations SIG |
| 2025-04 | Format wide (montant_budget + montant_reel) | `montant_reel = NaN` signale explicitement les mois futurs |
| 2025-04 | Méthode hybride forecast par défaut | Équilibre robustesse début d'année (tendance) et réactivité fin d'année (WLS) |
| 2025-04 | Bootstrap 1 000 simulations pour P10/P90 | Compromis précision statistique / temps de calcul |
| 2025-04 | Séparation core / views | core/ réutilisable sans Streamlit (notebooks, API) |
| 2025-04 | SIG pré-calculés dans DashboardData | Évite recalculs dans les vues, @st.cache_data une seule fois |

---

*FloMind Consulting · CDG × Data × IA pour PME*
