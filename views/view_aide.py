"""
views/view_aide.py
Guide d'utilisation du dashboard FloMind Budget.

Format : 5 onglets (tabs Streamlit)
  1. Vue d'ensemble — comment naviguer
  2. KPI & métriques — définitions SIG
  3. Waterfall & heatmap — comment lire
  4. Rolling Forecast — méthodes et bandes P10-P90
  5. Alertes & seuils — logique de détection
"""
from __future__ import annotations
import streamlit as st
from components.style import page_header, section_title


# ── Styles spécifiques à cette page ──────────────────────────────────────────
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
</style>
"""


def _callout(texte: str) -> None:
    st.markdown(f'<div class="aide-callout">{texte}</div>', unsafe_allow_html=True)

def _tip(texte: str) -> None:
    st.markdown(f'<div class="aide-tip">💡 {texte}</div>', unsafe_allow_html=True)

def _warn(texte: str) -> None:
    st.markdown(f'<div class="aide-warn">⚠️ {texte}</div>', unsafe_allow_html=True)


def render() -> None:
    """Point d'entrée de la page Aide."""
    st.markdown(_AIDE_CSS, unsafe_allow_html=True)

    page_header(
        title    = "📖 Guide d'utilisation",
        subtitle = "Comment lire et exploiter le dashboard FloMind Budget",
        badges   = ["FloMind v1.0", "CDG × Data × IA"],
    )

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🗺️ Navigation",
        "📊 KPI & SIG",
        "📉 Graphiques",
        "📡 Forecast",
        "🔔 Alertes",
    ])

    # ════════════════════════════════════════════════════════════════════════
    # ONGLET 1 — NAVIGATION
    # ════════════════════════════════════════════════════════════════════════
    with tab1:
        section_title("Vue d'ensemble du dashboard")

        st.markdown("""
Le dashboard est organisé en **4 écrans** accessibles depuis la navigation gauche,
plus ce guide. Chaque écran répond à un besoin précis selon le profil utilisateur.
        """)

        st.markdown("""
| Écran | Pour qui | Ce qu'on y fait |
|---|---|---|
| **Tour de contrôle** | Direction Générale | Vision consolidée réseau, alertes, atterrissages annuels |
| **Drill-down site** | Responsable de site / DG | Analyse détaillée d'un site : P&L mensuel, dérives, courbes |
| **Analyse des écarts** | Contrôleur de gestion | Identification des dérives par compte, waterfall mensuel |
| **Rolling Forecast** | CDG / DG | Projection de fin d'année, comparaison méthodes, intervalles P10-P90 |
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

- **Préparation Codir mensuel** → régler sur le mois écoulé, exporter les commentaires CDG
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
        section_title("Les indicateurs clés (KPI Strip)")

        _callout(
            "La rangée de <b>5 cartes KPI</b> en haut de chaque écran "
            "donne la photographie instantanée de la période sélectionnée. "
            "La <b>couleur de la bordure supérieure</b> identifie le type de métrique ; "
            "la <b>flèche</b> indique si l'écart est favorable (▲ vert) ou défavorable (▼ rouge)."
        )

        st.markdown("""
<table class="sig-table">
<tr>
    <th>Couleur</th><th>KPI</th><th>Lecture</th>
</tr>
<tr>
    <td><span class="sig-badge sig-blue">■ Bleu</span></td>
    <td><b>CA YTD Réel</b></td>
    <td>Chiffre d'affaires net cumulé Jan → mois sélectionné. Comprend les ventes marchandises
    nettes des RRR accordés et des retours.</td>
</tr>
<tr>
    <td><span class="sig-badge sig-cyan">■ Cyan</span></td>
    <td><b>Atterrissage CA</b></td>
    <td>Projection du CA total à fin décembre, calculée par la méthode hybride
    (tendance YTD + budget restant). Permet de savoir si l'objectif annuel sera atteint.</td>
</tr>
<tr>
    <td><span class="sig-badge sig-amber">■ Amber</span></td>
    <td><b>EBE YTD Réel</b></td>
    <td>Excédent Brut d'Exploitation cumulé. Mesure la performance opérationnelle
    avant dotations et éléments financiers. C'est le KPI de pilotage central en CDG.</td>
</tr>
<tr>
    <td><span class="sig-badge sig-purple">■ Violet</span></td>
    <td><b>REX YTD Réel</b></td>
    <td>Résultat d'Exploitation = EBE − Dotations aux amortissements et provisions.
    Reflète le résultat après prise en compte de l'usure des actifs.</td>
</tr>
<tr>
    <td><span class="sig-badge sig-cyan">■ Cyan</span></td>
    <td><b>Atterrissage EBE</b></td>
    <td>Projection EBE annuel. Permet d'anticiper si le seuil de rentabilité
    sera atteint en fin d'exercice.</td>
</tr>
</table>
        """, unsafe_allow_html=True)

        st.divider()
        section_title("Soldes Intermédiaires de Gestion (SIG)")

        st.markdown("""
Le SIG est la cascade de calcul qui décompose le CA en résultat net.
Chaque ligne représente une valeur ajoutée ou une consommation de ressources.
        """)

        st.markdown("""
<table class="sig-table">
<tr><th>Indicateur</th><th>Formule</th><th>Ce qu'il mesure</th></tr>
<tr>
    <td><span class="sig-badge sig-blue">CA net</span></td>
    <td>Ventes − RRR accordés − Retours</td>
    <td>Volume d'activité après corrections commerciales.</td>
</tr>
<tr>
    <td><span class="sig-badge sig-green">MC</span> Marge commerciale</td>
    <td>CA net − Coût d'achat des marchandises vendues</td>
    <td>La valeur créée sur la fonction achats-ventes.
    Le taux de marge (MC/CA) est l'indicateur de compétitivité achat.</td>
</tr>
<tr>
    <td>VA — Valeur ajoutée</td>
    <td>MC − Services extérieurs (loyers, maintenance, honoraires…)</td>
    <td>La richesse produite après consommation des services tiers.</td>
</tr>
<tr>
    <td><span class="sig-badge sig-amber">EBE</span></td>
    <td>VA − Charges de personnel − Impôts et taxes</td>
    <td><b>Indicateur central de performance opérationnelle.</b>
    Indépendant de la politique d'amortissement et de financement.
    Permet la comparaison inter-sites et inter-exercices.</td>
</tr>
<tr>
    <td><span class="sig-badge sig-purple">REX</span></td>
    <td>EBE − Dotations aux amortissements − Reprises sur provisions</td>
    <td>Résultat après prise en compte de l'usure et des risques.</td>
</tr>
<tr>
    <td>RCAI</td>
    <td>REX + Produits financiers − Charges financières</td>
    <td>Résultat avant IS, intègre le coût de financement.</td>
</tr>
<tr>
    <td>RN — Résultat net</td>
    <td>RCAI − IS − Participation</td>
    <td>Le bénéfice (ou la perte) final après toutes les charges.</td>
</tr>
</table>
        """, unsafe_allow_html=True)

        _tip(
            "Dans un réseau multi-sites, l'<b>EBE</b> est généralement le meilleur indicateur "
            "de comparaison entre sites car il neutralise les différences de politique "
            "d'investissement (dotations) et de structure de financement."
        )

    # ════════════════════════════════════════════════════════════════════════
    # ONGLET 3 — GRAPHIQUES
    # ════════════════════════════════════════════════════════════════════════
    with tab3:

        section_title("Le Waterfall (décomposition des écarts)")

        col_wf, col_wf_txt = st.columns([2, 3], gap="large")

        with col_wf_txt:
            st.markdown("""
Le waterfall décompose l'écart global **Budget → Réel** en contributions
par classe du SIG. Il répond à la question : *d'où vient la différence ?*

**Lecture :**

- **Barre grise — Budget** : point de départ (objectif)
- **Barres vertes** : classes qui ont **amélioré** le résultat vs budget
  (ex : CA supérieur au budget, charges inférieures au budget)
- **Barres rouges** : classes qui ont **détérioré** le résultat vs budget
  (ex : CA inférieur au budget, charges supérieures au budget)
- **Barre bleue/rouge — Réel** : résultat final, somme de tous les drivers

**Exemple de lecture :**
> Budget = 120 K€ | Produits +15 K€ | Achats −8 K€ | Personnel −5 K€
> → Réel = 122 K€ (+2 K€ vs budget)
            """)

            _warn(
                "Les barres représentent des <b>contributions au résultat net</b>, "
                "pas des valeurs absolues. Une barre rouge sur 'Charges personnel' signifie "
                "que les charges ont été supérieures au budget (impact négatif sur le résultat)."
            )

        st.divider()
        section_title("La Heatmap (écarts % multi-sites × mois)")

        col_hm, col_hm_txt = st.columns([2, 3], gap="large")

        with col_hm_txt:
            st.markdown("""
La heatmap affiche les **écarts en % vs budget** pour chaque site et chaque mois.
Elle permet d'identifier en un coup d'œil les problèmes persistants vs ponctuels.

**Code couleur :**
- 🟢 **Vert** — surperformance : réel > budget
- 🔴 **Rouge** — sous-performance : réel < budget
- ⬜ **Gris clair** — mois non encore réalisé

**Patterns à surveiller :**

| Pattern | Diagnostic probable |
|---|---|
| Colonne rouge (1 mois, tous sites) | Événement exogène (saisonnalité, incident marché) |
| Ligne rouge (1 site, tous mois) | Problème structurel du site : concurrence, management, emplacement |
| Carré rouge (1 site, quelques mois) | Incident ponctuel : problème fournisseur, travaux, turn-over |
| Gradient rouge → vert | Redressement en cours — surveiller la durabilité |
            """)

            _tip(
                "Changez le KPI de la heatmap (EBE, CA, REX, MC) pour croiser les diagnostics. "
                "Un site rouge en EBE mais vert en CA peut indiquer une dérive de charges "
                "malgré une bonne dynamique commerciale."
            )

    # ════════════════════════════════════════════════════════════════════════
    # ONGLET 4 — FORECAST
    # ════════════════════════════════════════════════════════════════════════
    with tab4:
        section_title("Comprendre le Rolling Forecast")

        _callout(
            "Le rolling forecast est le <b>différenciateur clé de FloMind</b> vs Excel ou Power BI. "
            "Il recalcule en temps réel la projection de fin d'année "
            "en tenant compte de la tendance YTD, avec des intervalles de confiance."
        )

        st.markdown("""
**Les 4 éléments du graphique :**

**① Ligne grise pointillée — Budget annuel**
L'objectif fixé en début d'exercice. C'est la référence statique.
Il ne change pas au fil des mois.

**② Ligne bleue pleine — Réel**
Les données constatées (Jan → mois courant).
C'est la seule certitude — on ne peut pas la modifier.

**③ Ligne orange — Forecast P50 (scénario central)**
Projection pour les mois restants.
C'est l'atterrissage le plus probable selon la méthode choisie.

**④ Bande orange transparente — Intervalle P10-P90**
La plage d'incertitude calculée par 1 000 simulations bootstrap sur les résidus historiques.
- **P10** = il y a 10% de chances de faire pire que cette borne
- **P90** = il y a 10% de chances de faire mieux que cette borne
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
    <td>Réel YTD + budget restant (mois par mois)</td>
    <td>Référence baseline en début d'exercice (T1-T2).
    Suppose que les mois restants se déroulent exactement comme prévu.</td>
</tr>
<tr>
    <td><b>Tendance</b></td>
    <td>Ratio YTD (réel/budget) appliqué uniformément au budget restant</td>
    <td>Présentation Codir, facile à expliquer à la DG.
    Pertinent si la performance YTD est homogène dans le temps.</td>
</tr>
<tr>
    <td><b>WLS</b></td>
    <td>Régression pondérée sur les réalisés (poids décroissants vers le passé)</td>
    <td>Mois 7+ avec une inflexion récente visible.
    Donne plus de poids aux derniers mois pour détecter un retournement.</td>
</tr>
<tr>
    <td><span class="sig-badge sig-amber">Hybride ★</span></td>
    <td>55% Tendance + 45% WLS (pondération dynamique selon la volatilité)</td>
    <td><b>Méthode recommandée par défaut.</b>
    Équilibre entre la robustesse de la tendance et la réactivité de la WLS.</td>
</tr>
</table>
        """, unsafe_allow_html=True)

        _tip(
            "Comparez les 4 méthodes dans le tableau 'Comparaison méthodes' de l'écran Forecast. "
            "Si toutes convergent vers le même atterrissage : signal fort. "
            "Si elles divergent fortement : la performance est volatile — élargir la bande d'alerte."
        )

        st.divider()
        section_title("Interpréter les KPI d'atterrissage")

        st.markdown("""
Les 5 cartes sous le graphique résument la situation annuelle :

| Carte | Lecture | Action si défavorable |
|---|---|---|
| **Budget annuel** | Objectif fixé — immuable | — |
| **Réel YTD** | Acquis — ne peut pas changer | Analyser les dérives passées |
| **Forecast P50** | Ce qu'on attend probablement | Ajuster le plan d'action restant |
| **P10 pessimiste** | 9 chances sur 10 de faire mieux | Si P10 < seuil critique : alerte |
| **P90 optimiste** | 9 chances sur 10 de faire moins bien | Plafond réaliste du potentiel |
        """)

    # ════════════════════════════════════════════════════════════════════════
    # ONGLET 5 — ALERTES
    # ════════════════════════════════════════════════════════════════════════
    with tab5:
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
Filtre les micro-comptes (un écart de 80 % sur 50 € n'est pas matériel).
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
    <td>Double critère de base vérifié (5 % et 2 000 €)</td>
    <td>Suivi dans la prochaine revue. Pas d'escalade immédiate.</td>
</tr>
</table>
        """, unsafe_allow_html=True)

        _warn(
            "Les seuils par défaut sont calibrés pour le secteur négoce B2B "
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
            "Dans l'écran <b>Analyse des écarts</b>, vous pouvez ajuster les seuils "
            "en temps réel avec les curseurs de filtrage. "
            "Baissez les seuils pour un audit approfondi, remontez-les "
            "pour une revue rapide de direction."
        )
