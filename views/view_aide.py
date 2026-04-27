"""
views/view_aide.py
Guide d'utilisation du dashboard FloMind Budget.

Format : 6 onglets (tabs Streamlit)
  1. Navigation       — comment naviguer, sélecteur de période
  2. KPI & SIG        — cascade SIG, définitions, lecture des cartes
  3. Graphiques       — waterfall, heatmap, VA
  4. Rolling Forecast — méthodes et bandes P10-P90
  5. Reforecast CDG   — hypothèses typées, cascade, persistance
  6. Alertes & seuils — logique de détection, niveaux, exclusions
"""
from __future__ import annotations
import streamlit as st
from components.style import page_header, section_title

_AIDE_CSS = """
<style>
.aide-callout {
    border-left: 3px solid var(--blue);
    background: var(--surface-2);
    padding: 0.75rem 1rem;
    border-radius: 0 8px 8px 0;
    margin: 0.75rem 0;
    font-size: 0.87rem;
    color: var(--text-muted);
    line-height: 1.6;
}
.aide-callout b { color: var(--text); }
.aide-tip {
    border-left: 3px solid var(--green);
    background: var(--green-dim);
    padding: 0.75rem 1rem;
    border-radius: 0 8px 8px 0;
    margin: 0.75rem 0;
    font-size: 0.87rem;
    line-height: 1.6;
}
.aide-warn {
    border-left: 3px solid var(--amber);
    background: var(--amber-dim);
    padding: 0.75rem 1rem;
    border-radius: 0 8px 8px 0;
    margin: 0.75rem 0;
    font-size: 0.87rem;
    line-height: 1.6;
}
.sig-table { width: 100%; border-collapse: collapse; font-size: 0.84rem; margin: 0.5rem 0 1rem; }
.sig-table th {
    text-align: left;
    padding: 0.45rem 0.75rem;
    border-bottom: 2px solid var(--border);
    font-size: 0.72rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-muted);
    font-weight: 600;
}
.sig-table td {
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid var(--border);
    color: var(--text);
    vertical-align: top;
    line-height: 1.5;
}
.sig-table tr:last-child td { border-bottom: none; }
.sig-table tr:hover td { background: var(--surface-2); }
.sig-badge {
    display: inline-block;
    padding: 0.1rem 0.45rem;
    border-radius: 4px;
    font-size: 0.72rem;
    font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
}
.sig-blue   { background: var(--blue-dim);  color: var(--blue); }
.sig-green  { background: var(--green-dim); color: var(--green); }
.sig-amber  { background: var(--amber-dim); color: var(--amber); }
.sig-purple { background: rgba(124,58,237,0.10); color: #7C3AED; }
.sig-cyan   { background: rgba(8,145,178,0.10);  color: #0891B2; }
.sig-slate  { background: rgba(100,116,139,0.10); color: #64748B; }
</style>
"""


def _callout(texte: str) -> None:
    st.markdown(f'<div class="aide-callout">{texte}</div>', unsafe_allow_html=True)

def _tip(texte: str) -> None:
    st.markdown(f'<div class="aide-tip">💡 {texte}</div>', unsafe_allow_html=True)

def _warn(texte: str) -> None:
    st.markdown(f'<div class="aide-warn">⚠️ {texte}</div>', unsafe_allow_html=True)


def render() -> None:
    st.markdown(_AIDE_CSS, unsafe_allow_html=True)

    page_header(
        title    = "📖 Guide d'utilisation",
        subtitle = "Comment lire et exploiter le dashboard FloMind Budget",
        badges   = ["FloMind v2.0", "CDG × Data × IA"],
    )

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🗺️ Navigation",
        "📊 KPI & SIG",
        "📉 Graphiques",
        "📡 Forecast",
        "🔄 Reforecast CDG",
        "🔔 Alertes",
    ])

    # ════════════════════════════════════════════════════════════════════════
    # ONGLET 1 — NAVIGATION
    # ════════════════════════════════════════════════════════════════════════
    with tab1:
        section_title("Vue d'ensemble du dashboard")

        st.markdown("""
Le dashboard est organisé en **5 écrans métier** + ce guide, accessibles depuis la navigation gauche.
Chaque écran répond à un besoin précis selon le profil utilisateur.
        """)

        st.markdown("""
| Écran | Pour qui | Ce qu'on y fait |
|---|---|---|
| **Tour de contrôle** | Direction Générale | Vision consolidée réseau : VA, alertes, waterfall, atterrissages |
| **Drill-down site** | Responsable site / DG | P&L mensuel détaillé, dérives par compte, courbes budget vs réel |
| **Analyse des écarts** | Contrôleur de gestion | Identification des dérives par compte, waterfall mensuel |
| **Rolling Forecast** | CDG / DG | Projection fin d'année, comparaison méthodes, intervalles P10-P90 |
| **Reforecast CDG** | Contrôleur de gestion | Révision formelle du budget par hypothèses opérationnelles typées |
        """)

        st.divider()
        section_title("Sélecteur de période")

        _callout(
            "Le curseur <b>Période d'analyse</b> dans la sidebar permet de "
            "<b>rejouer le dashboard à n'importe quel mois réalisé</b>. "
            "Jan → Mar donne la photo de fin T1 ; Jan → Déc montre l'année clôturée. "
            "Tous les KPI, graphiques et alertes se recalculent instantanément."
        )

        st.markdown("""
**Cas d'usage typiques :**

- **Préparation Codir mensuel** → régler sur le mois écoulé, analyser les alertes
- **Revue de performance annuelle** → régler sur Déc, comparer réel vs budget 12 mois
- **Analyse d'un pic inhabituel** → recouper avec le mois concerné pour isoler la cause
- **Démo prospect** → déplacer le curseur en direct pour montrer la réactivité du suivi
        """)

        _tip(
            "Le sélecteur ne modifie pas les données source. Il filtre la vue. "
            "Les données brutes (12 mois complets) restent accessibles à tout moment."
        )

    # ════════════════════════════════════════════════════════════════════════
    # ONGLET 2 — KPI & SIG
    # ════════════════════════════════════════════════════════════════════════
    with tab2:
        section_title("Les 6 cartes KPI — cascade SIG")

        _callout(
            "La rangée de <b>6 cartes KPI</b> en haut du Tour de contrôle suit exactement "
            "la <b>cascade SIG</b> : CA → Marge → VA → EBE → Atterrissages. "
            "L'ordre de lecture est économiquement logique : du volume à la rentabilité."
        )

        st.markdown("""
<table class="sig-table">
<tr>
    <th>#</th><th>Couleur</th><th>KPI</th><th>Lecture</th>
</tr>
<tr>
    <td>1</td>
    <td><span class="sig-badge sig-blue">■ Bleu</span></td>
    <td><b>CA YTD Réel</b></td>
    <td>Chiffre d'affaires net cumulé Jan → mois sélectionné.
    Point d'entrée de la cascade — le volume d'activité.</td>
</tr>
<tr>
    <td>2</td>
    <td><span class="sig-badge sig-green">■ Vert</span></td>
    <td><b>Taux de marge brute %</b></td>
    <td>MC / CA net. <b>1er levier actionnable par le directeur de site</b> :
    reflète la qualité des achats et la politique tarifaire.
    Affiché en points d'écart vs budget (ex : −1.5 pt).</td>
</tr>
<tr>
    <td>3</td>
    <td><span class="sig-badge sig-purple">■ Violet</span></td>
    <td><b>VA YTD Réel</b></td>
    <td>Valeur Ajoutée = MC − Services extérieurs.
    Richesse produite avant masse salariale.
    Indicateur clé pour la banque et les RH.</td>
</tr>
<tr>
    <td>4</td>
    <td><span class="sig-badge sig-amber">■ Amber</span></td>
    <td><b>EBE YTD (≈ EBITDA)</b></td>
    <td><b>Indicateur central de pilotage.</b>
    Mesure la performance opérationnelle indépendamment
    des amortissements et du financement.</td>
</tr>
<tr>
    <td>5</td>
    <td><span class="sig-badge sig-cyan">■ Cyan</span></td>
    <td><b>Atterrissage CA</b></td>
    <td>Projection du CA total à fin décembre.
    Permet de savoir si l'objectif annuel sera atteint.</td>
</tr>
<tr>
    <td>6</td>
    <td><span class="sig-badge sig-cyan">■ Cyan</span></td>
    <td><b>Atterrissage EBE</b></td>
    <td>Projection EBE annuel.
    Permet d'anticiper si le seuil de rentabilité sera tenu.</td>
</tr>
</table>
        """, unsafe_allow_html=True)

        _warn(
            "Le <b>REX</b> (Résultat d'Exploitation) n'est pas dans le KPI strip. "
            "Raison : les dotations aux amortissements sont figées en début d'exercice "
            "et non actionnables en cours d'année. L'EBE est l'indicateur de pilotage mensuel "
            "pertinent. Le REX est disponible dans le tableau atterrissage et le drill-down site."
        )

        st.divider()
        section_title("Soldes Intermédiaires de Gestion (SIG)")

        st.markdown("""
Le SIG est la cascade de calcul qui décompose le CA en résultat net.
La cascade est garantie cohérente sur tous les sites et toutes les périodes :
**CA net ≥ MC ≥ VA ≥ EBE ≥ REX**
        """)

        st.markdown("""
<table class="sig-table">
<tr><th>Indicateur</th><th>Formule</th><th>Ce qu'il mesure</th><th>Levier CDG</th></tr>
<tr>
    <td><span class="sig-badge sig-blue">CA net</span></td>
    <td>Ventes − RRR accordés − Retours</td>
    <td>Volume d'activité après corrections commerciales.</td>
    <td>Commercial, tarification</td>
</tr>
<tr>
    <td><span class="sig-badge sig-green">MC</span></td>
    <td>CA net − Coût d'achat marchandises</td>
    <td>Valeur créée sur la fonction achats-ventes.
    Le taux MC/CA mesure la compétitivité achat.</td>
    <td>Achats, mix produit, prix vente</td>
</tr>
<tr>
    <td>VA — Valeur ajoutée</td>
    <td>MC − Services extérieurs 61 et 62<br>
    (loyers, maintenance, honoraires, intérim…)</td>
    <td>Richesse produite après consommation des services tiers.
    Indicateur clé banque / RH.</td>
    <td>Frais généraux, sous-traitance</td>
</tr>
<tr>
    <td><span class="sig-badge sig-amber">EBE ≈ EBITDA</span></td>
    <td>VA − Charges de personnel − Impôts et taxes</td>
    <td><b>Indicateur central.</b> Indépendant des amortissements
    et du financement. Permet la comparaison inter-sites.</td>
    <td>Masse salariale, productivité</td>
</tr>
<tr>
    <td><span class="sig-badge sig-purple">REX</span></td>
    <td>EBE − Dotations aux amortissements et provisions</td>
    <td>Résultat après usure des actifs.
    Utile pour la comparaison avec les concurrents et la banque.</td>
    <td>Politique d'investissement</td>
</tr>
<tr>
    <td>RCAI</td>
    <td>REX + Produits financiers − Charges financières</td>
    <td>Résultat avant IS, intègre le coût de financement.</td>
    <td>Structure financière</td>
</tr>
<tr>
    <td>RN</td>
    <td>RCAI − IS − Participation</td>
    <td>Bénéfice ou perte final après toutes les charges.</td>
    <td>Optimisation fiscale</td>
</tr>
</table>
        """, unsafe_allow_html=True)

        _tip(
            "Dans un réseau multi-sites, l'<b>EBE</b> est le meilleur indicateur "
            "de comparaison car il neutralise les différences de politique d'investissement "
            "(dotations) et de structure de financement entre sites. "
            "EBE ÷ CA net = taux d'EBE : standard de référence sectoriel."
        )

    # ════════════════════════════════════════════════════════════════════════
    # ONGLET 3 — GRAPHIQUES
    # ════════════════════════════════════════════════════════════════════════
    with tab3:
        section_title("Section Valeur Ajoutée")

        _callout(
            "La section VA apparaît en haut du Tour de contrôle, avant le waterfall. "
            "Elle répond à la question : <b>nos sites créent-ils assez de richesse "
            "après les charges de services extérieurs ?</b>"
        )

        st.markdown("""
**Tableau Taux VA % par site :**
- **VA K€** : valeur ajoutée brute YTD en K€
- **Tx VA % réel** : VA / CA net — taux de valeur ajoutée réalisé
- **Tx VA % budget** : taux budgeté pour référence
- **Δ (pts)** : écart en points — vert si VA > budget, rouge si VA < budget

**Bar chart réel vs budget :**
Sites triés par taux VA décroissant. Identifie instantanément les sites
qui consomment trop de services extérieurs vs leur niveau d'activité.
        """)

        _tip(
            "Un taux VA faible peut signifier : loyer trop élevé, recours excessif à l'intérim, "
            "honoraires non budgétés, ou mix de sous-traitance défavorable — "
            "et non forcément un problème commercial."
        )

        st.divider()
        section_title("Le Waterfall — décomposition des écarts")

        st.markdown("""
Le waterfall décompose l'écart global **Budget → Réel** en contributions
par classe du SIG. Il répond à : *d'où vient la différence ?*

**Lecture :**

- **Barre grise — Budget** : point de départ (objectif)
- **Barres vertes** : classes qui ont **amélioré** le résultat vs budget
  (CA supérieur, charges inférieures au budget)
- **Barres rouges** : classes qui ont **détérioré** le résultat vs budget
  (CA inférieur, charges supérieures au budget)
- **Barre finale — Réel** : résultat final, somme de tous les drivers
        """)

        _warn(
            "Les barres représentent des <b>contributions au résultat net</b>, "
            "pas des valeurs absolues. Une barre rouge sur 'Charges personnel' signifie "
            "que les charges ont été supérieures au budget — impact négatif sur le résultat."
        )

        st.divider()
        section_title("La Heatmap — écarts % multi-sites × mois")

        st.markdown("""
La heatmap affiche les **écarts en % vs budget** pour chaque site et chaque mois.
Elle permet d'identifier les problèmes persistants vs ponctuels.

**Code couleur :**
- 🟢 **Vert** — surperformance : réel > budget
- 🔴 **Rouge** — sous-performance : réel < budget
- ⬜ **Gris clair** — mois non encore réalisé

**Patterns à surveiller :**

| Pattern | Diagnostic probable |
|---|---|
| Colonne rouge (1 mois, tous sites) | Événement exogène (saisonnalité, incident marché) |
| Ligne rouge (1 site, tous mois) | Problème structurel du site : concurrence, management |
| Carré rouge (1 site, quelques mois) | Incident ponctuel : fournisseur, travaux, turn-over |
| Gradient rouge → vert | Redressement en cours — surveiller la durabilité |
        """)

        _tip(
            "Changez le KPI de la heatmap (EBE, CA, VA, MC) pour croiser les diagnostics. "
            "Un site rouge en EBE mais vert en CA → dérive de charges malgré une bonne dynamique commerciale."
        )

    # ════════════════════════════════════════════════════════════════════════
    # ONGLET 4 — FORECAST
    # ════════════════════════════════════════════════════════════════════════
    with tab4:
        section_title("Comprendre le Rolling Forecast")

        _callout(
            "Le rolling forecast est le <b>différenciateur clé de FloMind</b> vs Excel ou Power BI. "
            "Il recalcule en temps réel la projection de fin d'année "
            "avec des intervalles de confiance P10–P50–P90."
        )

        st.markdown("""
**Les 4 éléments du graphique :**

**① Ligne grise pointillée — Budget annuel**
L'objectif fixé en début d'exercice. Référence statique, ne change jamais.

**② Ligne bleue pleine — Réel**
Les données constatées (Jan → mois courant). Seule certitude — ne peut pas être modifiée.

**③ Ligne orange — Forecast P50 (scénario central)**
Projection pour les mois restants. Atterrissage le plus probable selon la méthode choisie.
P50 = médiane sur 1 000 simulations bootstrap (pas le forecast déterministe).

**④ Bande orange transparente — Intervalle P10–P90**
Calculée par bootstrap sur les résidus historiques.
- **P10** → 10% de chances de faire pire que cette borne
- **P90** → 10% de chances de faire mieux que cette borne
- **Bande étroite** → site régulier, performance prévisible
- **Bande large** → site volatile, surveillance accrue nécessaire
        """)

        st.divider()
        section_title("Les 4 méthodes de forecast")

        st.markdown("""
<table class="sig-table">
<tr><th>Méthode</th><th>Principe</th><th>Quand l'utiliser</th></tr>
<tr>
    <td><b>Budget</b></td>
    <td>Réel YTD + budget restant mois par mois</td>
    <td>Référence baseline en début d'exercice (T1-T2).
    Suppose que les mois restants se déroulent exactement comme prévu.</td>
</tr>
<tr>
    <td><b>Tendance</b></td>
    <td>Ratio YTD (réel/budget) appliqué au budget restant</td>
    <td>Présentation Codir, facile à expliquer.
    Pertinent si la performance YTD est homogène dans le temps.</td>
</tr>
<tr>
    <td><b>WLS</b></td>
    <td>Régression pondérée (decay=0.75, mois récents prioritaires)</td>
    <td>Mois 7+ avec une inflexion récente visible.
    Donne plus de poids aux derniers mois pour détecter un retournement.</td>
</tr>
<tr>
    <td><span class="sig-badge sig-amber">Hybride ★</span></td>
    <td>55% Tendance + 45% WLS</td>
    <td><b>Méthode recommandée par défaut.</b>
    Équilibre robustesse de la tendance et réactivité de la WLS.</td>
</tr>
</table>
        """, unsafe_allow_html=True)

        _tip(
            "Si les 4 méthodes convergent vers le même atterrissage : signal fort. "
            "Si elles divergent fortement : performance volatile — élargir la bande d'alerte "
            "et investiguer les causes de variabilité."
        )

    # ════════════════════════════════════════════════════════════════════════
    # ONGLET 5 — REFORECAST CDG
    # ════════════════════════════════════════════════════════════════════════
    with tab5:
        section_title("Reforecast CDG — révision budgétaire par hypothèses")

        _callout(
            "Le Reforecast CDG est la <b>révision formelle du budget</b> par le contrôleur de gestion. "
            "Contrairement à l'atterrissage algorithmique (tendance pure), "
            "il intègre le <b>jugement CDG sous forme d'hypothèses opérationnelles typées</b>."
        )

        st.markdown("""
**La différence fondamentale :**

| | Atterrissage algo | Reforecast CDG |
|---|---|---|
| **Base** | Tendance historique | Hypothèses opérationnelles |
| **Qui** | Automatique | CDG (jugement humain) |
| **Quand** | Temps réel | Révision mensuelle formelle |
| **Exemple** | "La tendance WLS donne 485 K€" | "On a perdu le client Dupont (-8K€/mois) et signé un nouveau contrat (+5K€/mois)" |
        """)

        st.divider()
        section_title("Les 58 hypothèses typées — 5 catégories")

        st.markdown("""
<table class="sig-table">
<tr><th>Catégorie</th><th>Nb</th><th>Exemples</th><th>Impact cascade</th></tr>
<tr>
    <td>🔵 CA & Commercial</td>
    <td>14</td>
    <td>Perte client, nouveau contrat, AO remporté/perdu,
    hausse tarifaire, saisonnalité, fermeture temporaire…</td>
    <td><b>CA → MC → VA → EBE</b></td>
</tr>
<tr>
    <td>🟢 Achats & Marge brute</td>
    <td>10</td>
    <td>Hausse fournisseur, rupture → spot, RFA,
    nouveau fournisseur, déstockage, mix produit…</td>
    <td><b>MC → VA → EBE</b></td>
</tr>
<tr>
    <td>🟠 Charges de personnel</td>
    <td>12</td>
    <td>Recrutement CDI, départ non remplacé, NAO,
    prime exceptionnelle, chômage partiel, rupture conv.…</td>
    <td><b>EBE uniquement</b></td>
</tr>
<tr>
    <td>🔴 Services ext. & Frais généraux</td>
    <td>12</td>
    <td>Travaux, loyer, énergie, assurance, honoraires,
    IT, déplacements, logistique, sous-traitance…</td>
    <td><b>VA → EBE</b> (impact SIG intermédiaire)</td>
</tr>
<tr>
    <td>⚪ Événements exceptionnels</td>
    <td>10</td>
    <td>Sinistre, provision litige, subvention,
    redressement URSSAF, cession d'actif, créance irrécouvrable…</td>
    <td><b>EBE direct</b></td>
</tr>
</table>
        """, unsafe_allow_html=True)

        st.divider()
        section_title("La cascade SIG — pourquoi c'est important")

        _callout(
            "Chaque hypothèse impacte les KPIs selon sa nature économique. "
            "Un loyer plus élevé impacte d'abord la <b>VA</b> puis l'<b>EBE</b> — "
            "pas le CA ni la marge. Un recrutement impacte uniquement l'<b>EBE</b>. "
            "Cette distinction est essentielle pour un diagnostic correct."
        )

        st.markdown("""
```
CA commercial  ──→  CA_net
                      │
             × taux_marge_brute
                      ↓
Achats/marge   ──→  MC (Marge commerciale)
                      │
             − services extérieurs 61/62
                      ↓
Services ext.  ──→  VA (Valeur Ajoutée)
                      │
             − charges de personnel
             − impôts et taxes
                      ↓
Personnel      ──→  EBE (≈ EBITDA)
                      │
Exceptionnel   ──→  impact direct EBE
```
        """)

        st.divider()
        section_title("Utilisation pratique — les 4 onglets")

        st.markdown("""
**➕ Ajouter une hypothèse**
1. Sélectionner la catégorie et le type d'hypothèse
2. Lire la description et la cascade impactée
3. Saisir les paramètres (montant, %, mois de début, mois de fin)
4. Vérifier la **prévisualisation instantanée** de l'impact
5. Valider → l'hypothèse est sauvegardée et le graphique se met à jour

**📋 Hypothèses actives**
Liste des hypothèses saisies pour le site sélectionné.
Chaque hypothèse peut être supprimée individuellement.
Vue consolidée réseau disponible en bas de page.

**📊 Graphique comparatif**
4 courbes : Budget / Réel / Reforecast CDG / Atterrissage algo.
5 cartes KPI : Budget annuel / Réel YTD / RFC CDG / Atterrissage algo / Écart RFC vs Algo.

**🌐 Récap réseau**
Tableau de synthèse tous sites avec Δ RFC vs Budget et Δ RFC vs Atterrissage.
        """)

        _tip(
            "Les hypothèses sont sauvegardées dans <code>data/hypotheses.json</code> "
            "(non versionné sur GitHub). Elles persistent entre les sessions. "
            "Pour repartir à zéro : bouton 'Tout effacer' dans l'onglet 'Hypothèses actives'."
        )

        _warn(
            "Le reforecast CDG n'impacte que les <b>mois futurs</b> (postérieurs au mois réalisé). "
            "On ne peut pas réviser le passé — les mois réalisés restent le réel comptable."
        )

    # ════════════════════════════════════════════════════════════════════════
    # ONGLET 6 — ALERTES
    # ════════════════════════════════════════════════════════════════════════
    with tab6:
        section_title("Logique de détection des alertes")

        _callout(
            "FloMind utilise un <b>double critère de matérialité</b> pour éviter les faux positifs "
            "sur les micro-comptes. Une alerte n'est déclenchée que si "
            "<b>les deux conditions sont simultanément vérifiées</b>."
        )

        col_a1, col_a2 = st.columns(2, gap="large")
        with col_a1:
            st.markdown("""
**Critère 1 — Écart en %**
```
|réel - budget| / |budget| ≥ seuil %
```
Détecte les dérives relatives importantes.
Seuil par défaut : **5 %**

Exemple : budget 10 K€, réel 9 K€
→ écart = 10 % ≥ 5 % ✓
            """)
        with col_a2:
            st.markdown("""
**Critère 2 — Écart en €**
```
|réel - budget| ≥ seuil €
```
Filtre les micro-comptes (80 % sur 50 € = pas matériel).
Seuil par défaut : **2 000 €**

Exemple : budget 10 K€, réel 9 K€
→ écart = 1 000 € < 2 000 € ✗ → pas d'alerte
            """)

        st.markdown("→ **L'alerte n'est déclenchée que si les deux critères sont satisfaits.**")

        st.divider()
        section_title("Niveaux de priorité")

        st.markdown("""
<table class="sig-table">
<tr><th>Priorité</th><th>Critère</th><th>Action attendue</th></tr>
<tr>
    <td>🔴 <b>P1 — Critique</b></td>
    <td>Écart > 15 % ET > 5 000 € sur un compte stratégique (CA, EBE, personnel)</td>
    <td>Remontée immédiate DG. Analyse causale + plan d'action sous 48h.</td>
</tr>
<tr>
    <td>🟠 <b>P2 — Important</b></td>
    <td>Écart > 8 % ET > 3 000 €</td>
    <td>Discussion en revue mensuelle CDG. Commentaire obligatoire.</td>
</tr>
<tr>
    <td>🟡 <b>P3 — Surveillance</b></td>
    <td>Double critère de base (5 % et 2 000 €)</td>
    <td>Suivi dans la prochaine revue. Pas d'escalade immédiate.</td>
</tr>
</table>
        """, unsafe_allow_html=True)

        _warn(
            "Les seuils par défaut sont calibrés pour le négoce B2B "
            "(marges 30-45 %, tickets moyens élevés). "
            "Ils sont ajustables dans <code>config/settings.py</code> "
            "pour chaque déploiement client."
        )

        st.divider()
        section_title("Classes exclues du périmètre d'alerte")

        st.markdown("""
Certaines classes sont exclues par défaut pour éviter le bruit :

- **Dotations** — dépendent de la politique d'amortissement, pas de l'activité courante
- **IS et participation** — calculés en fin d'exercice, dérive normale en infraannuel
- **Résultats exceptionnels** — par nature non récurrents, ne doivent pas polluer le suivi opérationnel

Ces exclusions sont paramétrables dans `config/settings.py`.
        """)

        _tip(
            "Dans l'écran <b>Analyse des écarts</b>, les seuils sont ajustables "
            "en temps réel avec les curseurs de filtrage. "
            "Baissez les seuils pour un audit approfondi, remontez-les "
            "pour une revue rapide de direction."
        )
