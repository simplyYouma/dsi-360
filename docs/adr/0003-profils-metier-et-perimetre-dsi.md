# ADR-0003 — Profils métier DSI, direction unique, RBAC par action

- **Statut** : **Accepté** — les profils du cahier des charges (7 rôles fonctionnels) sont remplacés
  par les **profils métier réels de la DSI**, gérables depuis l'administration. La plateforme ne
  sert **que la DSI**. Remplace le volet « 7 profils » de `CLAUDE.md` §4.
- **Date** : 9 juillet 2026.
- **Décideurs** : porteur du projet (DSI AFG Bank Mali).
- **Partiellement remplacé** par [ADR-0005](0005-incidents-et-demandes-en-lecture-seule.md) :
  l'escalade manuelle (§3) et l'exception des tickets importés (§5) n'existent plus. Le niveau d'un
  ticket se déduit de son gestionnaire, et les incidents et demandes sont en lecture seule.

## Contexte

Le cahier des charges prévoyait 7 profils : Administrateur, DSI, Chef de Service, Chef de Projet,
Technicien, Métier, Direction Générale. Ces rôles décrivent une **hiérarchie**, pas l'organisation
réelle du travail à la DSI.

Une première correction (migration `20260709140000_profils_dsi.sql`) avait déjà retiré Chef de
Service, Chef de Projet, Technicien et Métier au profit d'un profil unique « Gestionnaire ». Cette
consolidation allait dans le bon sens mais restait trop grossière : **les gestionnaires ne font pas
le même métier**, et n'ont donc pas à disposer des mêmes actions.

Trois faits tranchent le sujet :

1. **Tous les utilisateurs de la plateforme sont de la DSI.** Les autres directions n'ont pas de
   compte : le demandeur d'un ticket n'accède pas au système.
2. **DBS n'est pas un utilisateur.** C'est le niveau 3, hors de la DSI. Ses agents
   travaillent hors de la plateforme ; ils apparaissent dans les fichiers importés mais n'ont ni
   compte, ni donnée persistée ici.
3. **Le métier détermine l'action.** Un agent du HelpDesk et un agent Réseau télécom n'ont ni les
   mêmes tickets, ni les mêmes gestes (valider, clôturer).

## Décision

### 1. Cinq profils, paramétrables

| Code | Libellé | Transverse |
|---|---|---|
| `ADMIN` | Administrateur | oui |
| `SUPPORT_APP_HELPDESK` | IT Support Applicatif et HelpDesk | non |
| `RESEAU_TELECOM` | Réseau télécom | non |
| `SYSTEME_RESEAU_TELECOM` | Système et Réseau télécom | non |
| `SUPPORT_APP` | IT Support Applicatif | non |

Les profils `DSI`, `GESTIONNAIRE` et `DG` sont **supprimés**. La « vue Direction Générale » du
cahier est une **restitution** (tableau de bord, analyses, exports), pas un profil de connexion :
elle sera servie par les rapports, non par un compte dédié.

Ces cinq profils sont un **point de départ, pas un vocabulaire figé** : l'administration peut en
créer, en renommer et en supprimer (refus si des comptes y sont rattachés). Seul `ADMIN` est
protégé — le supprimer fermerait la porte à clé de l'intérieur.

### 2. Une seule direction : DSI

Le référentiel `core.direction` ne contient plus que `DSI`. Les directions `DBS`, `DG`, `EXPLOIT`
et `METIER` sont supprimées, et les activités qui les référençaient sont rattachées à la DSI.

Le **cloisonnement par direction reste dans le code** (`activites_communs._visible`) : il devient
neutre — une seule direction, tout le monde voit tout — mais il n'est pas démonté. Le jour où une
autre entité du Groupe utilise la plateforme, le mécanisme est déjà là, et ses tests aussi.

### 3. Niveaux de support : N1 et N2 à la DSI, N3 = DBS

`core.utilisateur.niveau_support` ne vaut plus que **1 ou 2** : la DSI n'a pas d'agent N3.

Un ticket dont le gestionnaire n'est pas l'un des nôtres est **chez DBS, donc en N3** : il n'a pas
de responsable ici, reste visible et tracé, et le traitement a lieu hors du système.

> **Amendé par [ADR-0005](0005-incidents-et-demandes-en-lecture-seule.md).** Le geste manuel
> « escalader » a été retiré : le niveau n'est pas décidé, il se **lit sur le gestionnaire** que
> porte le rapport quotidien.

### 4. RBAC : accès par module **et par action**

`core.acces_role` passe de `(profil, module)` à `(profil, module, action)`. Vocabulaire d'actions :

| Action | Sens |
|---|---|
| `lire` | consulter la liste et le détail |
| `creer` | créer une activité |
| `modifier` | éditer les champs, assigner, commenter |
| `valider` | approuver / rejeter (CAB, ECAB, clôture d'audit) |
| `cloturer` | clore une activité |

Un profil peut ainsi lire les changements sans les valider. Chaque route déclare l'action qu'elle
exige ; le contrôle reste **côté serveur** (CLAUDE.md §6.3), la matrice reste **paramétrable**
(§6.2) et toute modification est **auditée** (§6.4).

### 5. Rôles sur une activité, distincts de l'accès au module

L'accès au module (`core.acces_role`) dit quelles **pages** un profil voit. Le rôle sur une
activité dit ce qu'on peut y **faire**. Il découle de qui est responsable, contributeur, valideur,
ou assigné d'une de ses tâches.

L'administrateur distribue le travail — assigner le gestionnaire, fixer impact et urgence, désigner
contributeurs et valideurs. Le gestionnaire et les contributeurs l'exécutent. Le valideur ne fait
que décider ; l'administrateur ne décide pas à sa place (séparation des tâches). L'assigné d'une
tâche n'en change que le statut : il rend compte, il ne se redistribue pas le travail.

On ne désigne qu'un compte **actif dont le profil a l'accès au module** : nommer quelqu'un à qui
l'écran resterait fermé n'aurait aucun sens.

Le serveur calcule les capacités (`peut_assigner`, `peut_travailler`…) et les expose dans le détail
de l'activité. **L'écran obéit, il ne rejoue pas la règle** — sinon elle vit à deux endroits et
finit par diverger. Source unique : `application/autorisations.capacites`.

Mais **l'écran n'est pas la garde** : chaque route d'écriture déclare son exigence. L'oubli est une
faille silencieuse — les capacités renvoyées disaient « non », l'écran masquait la commande, et la
route répondait quand même 200. Toute route qui écrit prend `CtxActeur` ou `CtxAdmin`, jamais le
simple accès au module.

**Cas des tickets importés** : incidents et demandes viennent du rapport quotidien.
[ADR-0005](0005-incidents-et-demandes-en-lecture-seule.md) tranche : on ne les travaille pas ici,
on les observe. Toutes leurs capacités sont à faux, pour tout le monde, l'administrateur compris.

### 6. Incarnation d'un compte — développement seulement

`POST /auth/incarner` délivre un jeton d'un autre compte, pour éprouver les vues par profil. Le
serveur répond ensuite comme au compte incarné : on éprouve les gardes réelles, pas seulement
l'affichage.

C'est une porte dérobée, donc trois verrous : hors `dev` la route répond **404** et n'apparaît pas
dans le contrat OpenAPI (on ne documente pas une porte qu'on n'ouvre pas) ; seul un administrateur
peut l'emprunter ; chaque passage est **journalisé**. Côté écran, un bandeau permanent rappelle
qu'on regarde par les yeux d'un autre, et `/moi` expose l'environnement — le navigateur ne peut pas
le deviner, un build de production servi depuis un poste de développement mentirait.

**Incarner, c'est regarder ses écrans, pas devenir cette personne.** Le jeton délivré porte la
marque `incarne_par` (l'e-mail de l'administrateur), que `/moi` restitue et que le rafraîchissement
conserve — sans quoi, au bout de quinze minutes, l'administrateur redeviendrait lui-même sans s'en
apercevoir. Deux gestes sont refusés au visiteur : **changer le mot de passe** du compte incarné
(403 — on n'accède pas aux secrets d'autrui), et **enchaîner** une seconde incarnation (403 — le
journal désignerait le mauvais responsable). L'écran, lui, ne réclame plus à un compte incarné
d'activer son mot de passe : un agent créé par l'administration n'en a pas encore.

## Conséquences

- ➕ Les profils reflètent enfin les métiers de la DSI, et l'administration peut les faire évoluer
  sans déploiement — conforme au principe SSOT (§6.2).
- ➕ Le RBAC devient assez fin pour que « les actions sont définies par profil » soit vrai.
- ➖ **Chaque route doit déclarer son action.** C'est le coût réel de la décision : `exiger_acces`
  devient `exiger(module, action)`, et les ~19 routeurs sont repris. Livré par tranches vérifiées.
- ➖ **`CLAUDE.md` §4 devient faux** et doit être corrigé : « 7 profils » → « profils métier
  paramétrables, `ADMIN` protégé ». Aucun code ne doit dépendre d'une liste figée de profils.
- ➖ Les comptes portant un profil supprimé sont basculés vers `SUPPORT_APP_HELPDESK`. Sur la base
  de développement, les 53 comptes concernés viennent du jeu de démonstration : il est régénéré
  après migration (`infra/local/donnees-demo.ps1`) plutôt que migré.
- Les tests d'intégration RBAC encodent la matrice réelle : la modifier fait échouer la suite, ce
  qui est le comportement voulu.

## À confirmer / suites

1. **Accès par défaut de chaque profil métier** : quels modules et quelles actions pour Réseau
   télécom, Système et Réseau télécom, IT Support Applicatif ? Le seed les ouvre aujourd'hui sur
   **tous les modules** — un agent HelpDesk voit donc Projets, Changements et Gouvernance. Cela ne
   lui donne aucun pouvoir (il n'y est acteur de rien), mais l'encombre. À restreindre depuis
   l'administration, ou dans le seed.
2. **Restitution DG** : par quel canal (rapport PDF planifié, compte en lecture seule, export) ?
3. **Transfert DBS** : faut-il notifier DBS par e-mail au passage en N3, ou le transfert reste-t-il
   entièrement manuel hors plateforme ?
4. **Direction du demandeur** : `core.demandeur.direction_id` pointe le même référentiel que le
   cloisonnement. Or un demandeur *vient* d'une autre direction (Métier, Exploitation…) — c'est une
   information d'origine, pas un périmètre de sécurité. Table vide aujourd'hui, donc sans effet ;
   à séparer en deux notions le jour où les demandeurs porteront leur direction d'origine.
