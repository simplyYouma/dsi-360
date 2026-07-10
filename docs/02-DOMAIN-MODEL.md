# 02 — Modèle de domaine

> Le cœur de DSI 360. Tout ce que pilote la DSI partage un **socle commun** (une « Activité ») ;
> chaque module en est une **spécialisation** avec sa propre machine à états. Tout ce qui peut
> varier (catégories, SLA, priorités, statuts, profils…) est **paramétrable** (cf. SSOT, CLAUDE.md §6).

## 1. L'entité pivot : `Activité`

Une **Activité** = toute chose suivie de bout en bout par la DSI (incident, demande, problème,
changement, projet, recommandation, risque). Socle commun à toutes :

| Attribut | Détail |
|---|---|
| `reference` | identifiant lisible, unique, préfixé par module : `INC-2026-00042`, `DEM-…`, `PRB-…`, `CHG-…`, `PRJ-…`, `AUD-…`, `RSQ-…` |
| `module` / `type` | incident, demande, problème, changement, projet, recommandation, risque |
| `titre`, `description` | — |
| `demandeur` | qui est à l'origine |
| `responsable_principal` | **un** responsable (accountable) |
| `contributeurs[]` | acteurs impliqués (responsible) |
| `valideurs[]` | qui valide / approuve (selon workflow) |
| `direction` / `service` | périmètre concerné |
| `categorie` | **paramétrable par module** |
| `impact`, `urgence` | saisis ou déduits |
| `priorite` | **P1…P5**, dérivée de la **matrice impact × urgence** (paramétrable) |
| `statut` | machine à états **propre au module** (cf. §3) |
| `sla_prise_en_charge`, `sla_resolution` | cibles issues de la **matrice SLA** (paramétrable) |
| dates | `cree_le`, `pris_en_charge_le`, `echeance_le`, `resolu_le`, `cloture_le` |
| `pieces_jointes[]`, `commentaires[]` | — |
| audit | chaque changement journalisé (qui, quand, **ancienne → nouvelle valeur**, IP) |

> **Choix de conception** : un **socle générique + spécialisations** (et non sept entités sans
> rapport). Avantage : responsabilités, SLA, priorité, notifications, audit, recherche et reporting
> sont **mutualisés** ; ajouter un module = une spécialisation, pas une refonte.

## 2. Priorité et SLA (communs, paramétrables)

- **Priorité = f(Impact, Urgence)** → **P1 (Critique) … P5 (Très faible)**, via une **matrice
  paramétrable**. Impact gradué (ex. > 50 % des utilisateurs / 10–50 % / partie du business /
  individu).
- **SLA = (cible de prise en charge, cible de résolution)** paramétrée par **type × priorité ×
  criticité × catégorie**. Exemple du cahier : Critique 15 min / 4 h · Haute 30 min / 8 h · Moyenne
  2 h / 2 j · Faible 1 j / 5 j.
- Les **échéances** sont calculées à la prise en charge ; un **ordonnanceur in-process** (asyncio,
  cf. ADR-0002) surveille approche et **dépassement** de SLA → notifications.
- **Niveau de support** : **N1 et N2 à la DSI, N3 = DBS**. Il n'est pas décidé, il se **déduit** du
  gestionnaire : le niveau porté par son compte, ou N3 si le gestionnaire n'est pas des nôtres
  ([ADR-0005](adr/0005-incidents-et-demandes-en-lecture-seule.md)).

## 3. Machines à états par module (cycles de vie ITIL)

> Issues des procédures **SI-12.01 → 05**. Les statuts sont **paramétrables** mais ces transitions
> sont les valeurs par défaut métier.

- **Incident** : `Nouveau` → `Ouvert` (en cours) → `Résolu` → `Clôturé`. Transverses : `Réouvert`
  (par l'utilisateur), `Annulé` (résolution non nécessaire). Clôture ≤ 24 h après résolution.
- **Demande de service** : `Nouvelle` → `Qualifiée/Catégorisée` → `En cours` → `En validation` →
  `Résolue` → `Clôturée`. Transverses : `Rejetée`, `Réouverte`. Catégories : compte, habilitations,
  logiciel, assistance, **VPN**, matériel, autres.
- **Problème** : `Nouveau` → `En cours d'analyse` → (`Erreur connue` / **KEDB**) → `Résolu` →
  `Clôturé`. Transverse : `Réouvert`. Peut **générer une RFC** (changement).
- **Changement (RFC)** : `Brouillon` → `Soumis` → `Évaluation` (impact + risque) → **`CAB`/`ECAB`**
  (`Validé` / `Rejeté`) → `Planifié` → `En implémentation` → `Implémenté` → `Revue
  post-implémentation` → `Clôturé`. Transverse : `Retour arrière`. **Types** : *Standard*
  (pré-approuvé), *Normal* (CAB, ≤ 3–4 j), *Urgent* (ECAB, ≤ 6 h).
- **Projet** : `Cadrage` → `En cours` (jalons, % d'avancement, budget, COPIL) → `Clôturé`.
  Transverse : `Suspendu`.
- **Recommandation d'audit** : `Ouverte` → `Plan d'action` → `En cours` → `En validation de clôture`
  → `Clôturée`. Marqueur `En retard`. **Sources** : Audit Groupe, Audit Interne, BCEAO, Contrôle
  Permanent, Risques, Commissaires aux comptes.
- **Risque IT** : `Identifié` → `Évalué` (**Probabilité × Impact = Criticité**) → `Traitement` →
  `Maîtrisé` / `Accepté` → `Revue périodique`.

## 4. Référentiels paramétrables (Single Source Of Truth)

Aucune de ces valeurs n'est codée en dur : on les édite depuis l'administration.

- **Modules / types** d'activité.
- **Catégories** par module.
- **Matrice de priorité** (impact × urgence → P1…P5).
- **Matrice SLA** (type/priorité/criticité → prise en charge + résolution).
- **Statuts** et transitions par module.
- **Profils & permissions** (RBAC, §5) ; le **niveau de support** est porté par le compte agent.
- **Sources d'audit**, **types de changement**, **directions / services**.

## 5. Acteurs & droits (RBAC — profils métier paramétrables)

Cf. [ADR-0003](adr/0003-profils-metier-et-perimetre-dsi.md). Les profils décrivent les **métiers de
la DSI**, pas une hiérarchie. Ils s'ajoutent, se renomment et se suppriment depuis l'administration.

| Profil (défaut) | Transverse | Portée |
|---|---|---|
| **Administrateur** | oui | accès complet, paramétrage |
| **IT Support Applicatif et HelpDesk** | non | opérationnel, sa direction |
| **Réseau télécom** | non | opérationnel, sa direction |
| **Système et Réseau télécom** | non | opérationnel, sa direction |
| **IT Support Applicatif** | non | opérationnel, sa direction |

`ADMIN` est **protégé** : il ne se supprime pas et reste transverse — sinon plus personne
n'administre la plateforme. Aucun code ne dépend d'une liste figée de profils.

Cloisonnement vérifié **côté serveur** : chacun ne voit/agit que dans son périmètre. La plateforme
ne servant que la DSI (direction unique), il est aujourd'hui neutre ; le mécanisme et ses tests
restent en place. La correspondance profil → droits est **paramétrable**, par module et par action ;
les actions sensibles (validation CAB/ECAB, clôture, paramétrage) restent gardées en dur
(séparation des tâches).

## 6. Traçabilité (audit append-only)

Toute action (création, modification, affectation, validation, clôture, suppression) est journalisée :
**utilisateur, date/heure, module, action, ancienne valeur → nouvelle valeur, adresse IP**.
Append-only, jamais d'effacement, consultable par les administrateurs (exigence cahier §7).

## 7. Indicateurs (reporting / tableau de bord)

Incidents ouverts · incidents critiques · **MTTR** · taux de résolution · demandes en cours ·
**respect SLA** · projets en cours / en retard · changements planifiés · **% hors CAB** ·
recommandations ouvertes / en retard · risques critiques · taux de réouverture · volume par
catégorie. Restitution : tableau de bord exécutif + exports **PDF / Excel / CSV**.
