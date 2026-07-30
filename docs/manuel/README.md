# Manuel de la plateforme

Le manuel est **généré**. N'éditez jamais `docs/MANUEL.html` : il est écrasé à chaque
construction.

```bash
node docs/manuel/build.mjs
```

Le fichier produit — `docs/MANUEL.html` — est **autonome** : styles et comportements inline,
aucune ressource distante. Il s'ouvre hors ligne, se transmet par mail tel quel, et s'enregistre
en PDF A4 depuis le navigateur (bouton en bas à droite).

## Où modifier quoi

| Vous voulez… | Fichier |
|---|---|
| Corriger ou enrichir le texte | `contenu/<NN>-<sujet>.mjs` |
| Ajouter un chapitre | un nouveau fichier `contenu/`, préfixé de son rang |
| Ajouter une annexe | idem, avec `annexe: true` dans l'export |
| Changer le nom du produit, la version, l'accent | `identite.mjs` |
| Changer la mise en page ou le rendu papier | `_moteur/manuel.css` |
| Changer le sommaire actif, la recherche, l'impression | `_moteur/manuel.js` |

La **numérotation** des chapitres et des sections est calculée : insérer une section au milieu ne
demande pas de renuméroter les suivantes. Le **sommaire** — celui de l'écran comme celui du papier
— se déduit du contenu ; il ne peut donc pas diverger.

Les fichiers de `contenu/` sont ordonnés par leur préfixe numérique. Pour insérer un chapitre entre
deux existants, renommez les fichiers suivants : l'ordre de lecture est celui du disque, visible
d'un `ls`, sans index à tenir à jour.

## Structure d'un chapitre

```js
export const chapitre = {
    annexe: false,             // true → numérotée A, B, C…
    titre: 'Concepts',
    intro: 'Une phrase ou deux qui situent le chapitre.',
    sections: [
        { titre: 'L\'activité', corps: `<p>…</p>` },
    ],
};
```

Le `corps` est du HTML. Classes disponibles, toutes stylées pour l'écran **et** le papier :

| Classe | Usage |
|---|---|
| `.defs` | Liste de définitions (`<div><dt>…</dt><dd>…</dd></div>`) |
| `.etapes` | Marche à suivre numérotée (`<ol class="etapes">`) |
| `.note` | Encadré ; variantes `.attention`, `.danger`, `.ok` |
| `.cartes` / `.carte` | Grille de deux cartes par ligne |
| `.cycle` | Suite d'états (`<span>` séparés par `<i>→</i>`, `.fin` pour l'état terminal) |
| `.pastille` | Pastille de statut ; variantes `.ok`, `.alerte`, `.danger`, `.neutre` |
| `table`, `pre`, `code` | Stylés par défaut |

## Règle de rédaction

**Rien n'est décrit qui n'existe pas dans le produit.** Ce qui est prévu mais non implémenté est
listé explicitement en annexe C — un manuel qui promet ce qui n'existe pas rend suspectes toutes
ses autres pages.

Le corps du manuel ne nomme **ni métier, ni secteur, ni entreprise** : il parle d'« organisation »,
d'« entité », d'« activités ». Décliner le document pour un autre déploiement ne demande donc que
de changer `identite.mjs`.

## Vérifier avant diffusion

Ouvrez `docs/MANUEL.html`, puis :

1. le sommaire suit-il la lecture, et le filtre trouve-t-il un terme accentué tapé sans accent ?
2. « Enregistrer en PDF » → marges **par défaut**, **graphiques d'arrière-plan cochés**, échelle
   100 % ;
3. dans le PDF : chaque chapitre commence-t-il sur une page neuve, aucun titre séparé de son
   texte, aucun tableau coupé, les encadrés et pastilles sont-ils bien colorés ?
