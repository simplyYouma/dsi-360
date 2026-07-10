# ADR-0005 — Incidents et demandes : miroir de l'import, pas outil de travail

- **Statut** : **Accepté** — les incidents et les demandes sont traités dans un autre système.
  DSI 360 en reflète l'état pour en suivre l'évolution et en tirer des statistiques. On y observe,
  on n'y agit pas. Remplace le volet « exception des tickets importés » de
  [ADR-0003](0003-profils-metier-et-perimetre-dsi.md) §3 et §5.
- **Date** : 10 juillet 2026.
- **Décideurs** : porteur du projet (DSI AFG Bank Mali).

## Contexte

Un rapport quotidien est importé (`source = 'IMPORT_SD'`). Il porte le statut, la priorité, la
catégorie, le demandeur et le **gestionnaire** de chaque ticket. Le traitement réel — prise en
charge, résolution, clôture — se fait dans le système d'origine.

Trois défauts en découlaient, tous nés de l'idée que la plateforme pouvait piloter ces tickets :

1. **L'upsert préservait `responsable_id`** pour ne pas écraser une assignation faite ici, tout en
   réécrivant `donnees.gestionnaire` (le nom du rapport). Les deux pouvaient diverger : la fiche
   affichait un gestionnaire qui n'était plus celui du fichier.
2. **L'import remplaçait intégralement `donnees`**, où l'escalade manuelle écrivait
   `niveau_support` et `transfere_dbs`. Un import survenant après une escalade les effaçait sans
   bruit, ramenant le ticket au N1.
3. **L'import ne journalisait aucune transition.** `audit.historique_statuts` ne lisant que les
   actions `CREATION` et `TRANSITION`, un incident passé de Nouveau à Clôturé par imports
   successifs avait un **historique vide**, et aucune statistique de durée par statut n'aurait pu
   le voir.

## Décision

### 1. Le fichier fait autorité

À chaque import, le ticket est réaligné sur le rapport : titre, statut, priorité, catégorie,
demandeur, **et gestionnaire**. `responsable_id` n'est plus préservé.

### 2. Le gestionnaire décide du niveau — tout ce qui n'est pas nous est DBS

Le nom de la colonne « gestionnaire » est rapproché d'un compte DSI par nom normalisé (accents
retirés, les deux ordres prénom/nom). S'il correspond à l'un des nôtres, le ticket est **à son
niveau** (N1 ou N2, lu sur son compte). Sinon, c'est **DBS** : le ticket n'a pas de responsable chez
nous, et il est au **niveau 3**.

Le niveau est donc **déduit**, jamais décidé. L'escalade manuelle disparaît — route, bouton, et les
clés `donnees.niveau_support` / `donnees.transfere_dbs`, devenues muettes.

**Aucun compte n'est créé par l'import**, ni aucune adresse e-mail fabriquée. Les comptes sont créés
par l'administrateur. Corollaire : un agent qui traite des tickets **doit déclarer son niveau** à la
création de son compte, sans quoi ses tickets retomberaient au N1 par défaut et la statistique
mentirait en silence. Seul l'administrateur, qui ne traite pas de tickets, est sans niveau.

### 3. Lecture seule

Pour ces deux modules uniquement, le serveur ne monte plus : transition de statut, assignation (et
assignation en lot), réévaluation impact/urgence, changement de catégorie, désignation de
contributeurs et de valideurs, décision. La création manuelle n'existait déjà pas.

`capacites(..., lecture_seule=True)` renvoie toutes les permissions à faux : l'écran ne propose
rien, plutôt que de laisser cliquer là où le serveur répondrait 404.

**Ce qui reste** : lire la fiche, son historique et son niveau ; exporter ; déposer des pièces
jointes (**incidents seulement** — les demandes n'en ont jamais eu) ; et la **discussion interne**
à la DSI. Nos échanges nous appartiennent — ils ne viennent pas du fichier, et l'import ne les
touche pas (tables séparées).

Ni les incidents ni les demandes n'ont de **tâches** : les routes qui pointaient vers les pièces
jointes de leurs tâches ne sont plus montées.

### 4. Le cycle de vie est journalisé

L'import consigne une entrée `CREATION` à l'apparition d'un ticket, et une `TRANSITION` à chaque
changement d'état — et rien d'autre : le rapport est réimporté chaque jour, l'immense majorité des
lignes ne bouge pas. L'historique de la fiche se remplit, et les statistiques de durée par statut
deviennent possibles.

## Conséquences

- ➕ Une seule source de vérité. Ce que l'écran montre est ce que le fichier dit.
- ➕ Le support voit le niveau de chaque ticket bouger seul après l'import, dans la liste comme dans
  la fiche, sans rien décider.
- ➕ Le parcours d'un ticket devient analysable, ce qui est la raison d'être de ces deux modules.
- ➖ Le journal d'audit grossit : un import où 500 tickets changent d'état écrit 500 entrées, et il
  est chaîné par empreinte. À surveiller si le volume quotidien croît.
- ➖ Un ticket dont le gestionnaire n'est pas rapproché (DBS) n'a pas de responsable : il échappe à
  l'évaluation des gestionnaires (`/analyses/gestionnaires`) et à la file « Mes tickets ». C'est
  voulu — DBS n'est pas nous — mais il faudra un indicateur propre au volume parti chez DBS.
- ➖ Un nom mal orthographié dans le rapport fait basculer le ticket chez DBS sans avertissement.
  Un écran de rapprochement (« ces N noms n'ont trouvé aucun compte ») serait utile.

## Suites

1. **Indicateur DBS** : volume et ancienneté des tickets partis chez DBS, aujourd'hui invisibles
   dans l'évaluation des gestionnaires.
2. **Rapprochement des noms** : signaler à l'import les gestionnaires non reconnus, pour distinguer
   un vrai agent DBS d'une faute de frappe.
3. **Statistiques de cycle de vie** : maintenant que les transitions sont journalisées, mesurer le
   temps passé dans chaque statut.
4. **Pièces jointes des demandes** : les incidents en acceptent, les demandes non. L'asymétrie n'est
   pas décidée, elle est héritée. À trancher.
