# 05 — Design System

> Objectif : un rendu **au niveau des captures d'inspiration** (`_sources-conception/inspi-1…3`) —
> clair, aéré, **premium**, jamais « template ». On **réutilise et prolonge** le design system de
> **DORIS** (tokens, primitives maison), pour la cohérence Groupe.

## 1. Direction visuelle (tirée des captures)

- **Fond clair / blanc cassé**, surfaces **blanches** en **cartes arrondies** avec ombre très douce ;
  beaucoup d'**espace** (respiration), hiérarchie typographique nette.
- **Layout** : **sidebar** de navigation à gauche (icônes + libellés, repliable) + **topbar**
  (recherche globale, notifications, profil) — cf. `inspi-2`.
- **Couleur = sens uniquement** : un **accent** de marque sobre (actions, sélection) ; le reste en
  **neutres** (gris/texte). Les couleurs vives sont réservées aux **statuts** (vert/ambre/rouge) et
  aux séries de graphiques.
- **Composants data** vus dans les inspis, à fournir en natif maison :
  - **cartes KPI** avec valeur + **delta** fléché (`inspi-2`, `inspi-3`) ;
  - **pastilles de statut** (Excellent/Vigilance/Dépassé…) dans les tableaux (`inspi-1`) ;
  - **mini-courbes (sparklines)** en bout de ligne (`inspi-1`) ;
  - **donut** de répartition + barres latérales (`inspi-2`) ;
  - **fil d'activité récente**, **liste de tâches** (accepter/refuser), **échéances à venir**
    (`inspi-2`) — parfaitement aligné avec SLA / échéances de DSI 360.

## 2. Tokens (variables CSS, un seul point de pilotage)

Aucune valeur en dur dans les composants. Thème **clair par défaut**, **sombre** prévu (`data-theme`).

- **Primaire = NOIRE** (`--accent` ≈ `#16181d` en clair) ; s'inverse en **blanc** sur thème sombre
  (texte foncé via `--on-accent`). Pas de bleu de marque.
- **Couleurs** : `--bg`, `--surface`, `--bg-subtle`, `--border`, `--text`, `--text-muted`,
  `--accent` (+ `--accent-subtle`, `--accent-hover`), statuts `--status-ok|warn|danger` (+ `*-bg`).
- **Palette catégorielle** `--cat-1 … --cat-8` (indigo, teal, ambre, rose, violet, vert, cyan,
  orange) : **touche de couleur** pour graphiques, badges, pastilles de catégorie. Sans valeur de
  statut (à ne pas confondre avec ok/warn/danger). La base reste neutre ; la couleur ponctue.
- **Typo** : échelle `--text-xs … --text-2xl`, poids `--weight-regular|medium|semibold`,
  chiffres **tabulaires** pour les valeurs.
- **Espacement** : échelle `--space-1 … --space-8`.
- **Rayons / ombres** : `--radius-sm|md|lg`, `--shadow-md` (douce).

## 3. Primitives maison (zéro composant natif du navigateur)

`Button` (primaire/secondaire/fantôme/danger) · `Card` · `Select`/`Dropdown` (portail, accessible
clavier) · `DatePicker`/`Calendar` · `Input` / `MotDePasse` (œil) · `Table` (tri, **pagination
numérotée**) · `StatusBadge` (pastille + libellé) · `KpiCard` (valeur + delta + sparkline) ·
`Sparkline` (SVG) · `Donut` · `Toast` (fond sémantique) · `Pagination` · `Modale` · `Skeleton`
(chargement élégant) · `Avatar` (illustré). **Icônes : Lucide.** **Zéro emoji** dans l'UI.

### 3 bis. Modales (référence premium)

Style retenu (cf. inspiration validée) — composant `Modale` :

- **Surface blanche, très arrondie** (`--radius-xl` ≈ 24 px), **ombre flottante** (`--shadow-lg`),
  généreusement aérée (`--space-6`).
- **Bouton fermer circulaire** (≈ 56 px) **flottant en haut à droite**, débordant légèrement le coin,
  avec sa propre ombre. Sur mobile, il revient dans le coin.
- **Grand titre** (`--text-2xl`, semibold), puis le corps.
- **Champ de recherche en pilule** (`--radius-pill`) avec icône à gauche, le cas échéant.
- **Lignes de liste** (`LigneListe`) : pastille ronde (initiales / icône / avatar) + libellé +
  **chevron** à droite, surlignage au survol.
- **Pied d'action aligné à droite** (bouton primaire / secondaire).
- Ferme via le **X**, **Échap**, ou **clic sur le fond** ; verrouille le défilement ; `aria-modal`.

## 4. Règles non négociables

- **Aucun composant natif** (listes déroulantes, calendriers, scrollbars, toasts, `alert()`…) : tout maison.
- **Aucune animation clignotante** ; transitions sobres ; respect de `prefers-reduced-motion`.
- **La couleur porte du sens** (statut/accent) — pas de décor coloré gratuit.
- **Tableaux** pour les vues de gestion/matrices (rôles × droits, SLA…), pas des cartes.
- **Graphiques originaux et premium** (jamais le rendu par défaut d'une lib) ; sparklines maison.
- **Accessibilité** : contrastes suffisants, focus visibles, navigation clavier, libellés ARIA.
- **i18n** prête (français au lancement, structure pour l'anglais) ; **responsive** (la DSI est mobile).

## 5. Écrans phares (cohérents avec les inspis)

- **Tableau de bord exécutif** : bandeau de **cartes KPI** (incidents ouverts/critiques, respect SLA,
  projets en retard, recommandations en retard, risques critiques) + **donut** de répartition +
  **fil d'activité** + **échéances/SLA à venir**.
- **Listes d'activités** (incidents, demandes…) : **tableau** avec pastille de statut, priorité
  colorée, échéance SLA, **sparkline** de tendance, pagination numérotée.
- **Fiche d'activité** : en-tête (référence, statut, priorité, SLA), responsabilités, historique
  (timeline d'audit), pièces jointes, workflow (validation/CAB selon module).
