# Dossier de présentation

Le document commercial de la plateforme, au format magazine, à remettre à une
direction ou à un prospect. Il est **généré** : n'éditez jamais
`docs/PRESENTATION.html`, il est écrasé à chaque construction.

```bash
cd docs/presentation
npm install     # une seule fois (sharp, pour préparer logo et couverture)
npm run build
```

Le fichier produit est **autonome** : styles, comportements, logo et visuel de
couverture sont embarqués. Il s'ouvre hors ligne, s'envoie par mail tel quel, et
s'exporte en **PDF A4 paginé** depuis le bouton en bas à droite.

## Y joindre vos captures d'écran

Ouvrez le fichier dans un navigateur. Chaque page porte un cadre en pointillés
avec l'intitulé de la capture attendue — cliquez dessus, choisissez l'image.
Rien ne quitte votre poste : l'image est lue en local.

Le cadre épouse ensuite le format réel de la capture, sans la rogner ni
l'aplatir. **Un cadre laissé vide disparaît à l'export** : un dossier envoyé ne
montre jamais un emplacement en attente. Vous pouvez donc n'en remplir que la
moitié et l'envoyer quand même.

⚠️ Les captures sont attachées à la page ouverte, pas au fichier. Exportez le
PDF avant de fermer l'onglet.

## Où modifier quoi

| Vous voulez… | Fichier |
|---|---|
| Corriger ou enrichir le texte | `contenu/plateforme.mjs` |
| Changer le nom, le logo, la couverture, l'accent, le contact | `identite.mjs` |
| Changer la mise en page ou le rendu papier | `_moteur/deck.css` |
| Changer la pagination, le chargement des captures, l'export | `_moteur/deck.js` |

## Règle de rédaction

**Aucun métier, aucun secteur, aucune entreprise n'est nommé.** Le dossier parle
d'« organisation », de « direction », d'« entité », d'« activités ». Il doit
pouvoir être remis à un service qualité, à une direction des opérations ou à un
cabinet d'audit sans qu'une seule phrase sonne comme si elle avait été écrite
pour quelqu'un d'autre.

**Rien n'est promis qui n'existe pas.** Le contenu est adossé à ce que fait
réellement le code. Ce qui est prévu mais non implémenté est documenté dans le
manuel (`docs/manuel/`, annexe C) — pas vendu ici.

## Voir aussi

`docs/manuel/` — le **manuel** de la plateforme : documentation de référence
complète (concepts, prise en main, modules, administration, sécurité,
exploitation). Deux documents, deux usages : celui-ci convainc, l'autre explique.
