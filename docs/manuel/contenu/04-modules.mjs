export const chapitre = {
    titre: 'Les modules',
    intro:
        'Un module par domaine suivi. Tous reposent sur le socle du chapitre 2 — mêmes '
        + 'responsabilités, mêmes engagements, même historique. Ce chapitre ne répète donc '
        + 'que ce qui leur est propre : ce qu\'ils ajoutent, et ce qu\'ils interdisent.',
    sections: [
        {
            titre: 'Tableau de bord',
            corps: `
<p>La vue d'ouverture. Elle répond à trois questions, dans cet ordre : <em>où en est-on</em>,
<em>qu'est-ce qui dérape</em>, <em>par quoi commencer</em>.</p>

<div class="cartes">
  <div class="carte"><b>Indicateurs</b><span>Volumes par module, respect des engagements, retards,
    répartitions. Chaque valeur porte sa tendance sur la période.</span></div>
  <div class="carte"><b>Signaux</b><span>Ce qui demande une décision : engagements dépassés,
    dossiers non assignés, échéances imminentes.</span></div>
  <div class="carte"><b>À traiter en premier</b><span>Une liste courte, ordonnée par urgence réelle
    plutôt que par date de création.</span></div>
  <div class="carte"><b>Période ajustable</b><span>Tout l'écran se recalcule sur la fenêtre choisie
    — les derniers jours, ou deux dates précises.</span></div>
</div>

<p>L'écran s'exporte en <strong>PDF</strong> et chaque visuel en <strong>image</strong>, pour être
repris tel quel dans un support de comité.</p>`,
        },
        {
            titre: 'Incidents',
            corps: `
<p>Ce qui interrompt ou dégrade un service. Le module en suit le traitement : classement,
priorité, responsable, niveau de support, délais, historique.</p>

<div class="cycle">
  <span>Nouveau</span><i>→</i><span>Ouvert</span><i>→</i><span>Résolu</span><i>→</i>
  <span class="fin">Clôturé</span>
</div>

<div class="note attention">
  <b>Module en lecture seule</b>
  <p>Les incidents ne se créent pas ici et leur état ne s'y modifie pas : ils sont traités dans
  l'outil de service desk de l'organisation et arrivent par <strong>import quotidien</strong>
  (cf. chapitre Administration). La plateforme en reflète l'état pour en suivre l'évolution, en
  tirer les statistiques et mesurer la charge. On y observe, on n'y agit pas.</p>
  <p>Restent possibles, parce qu'elles n'appartiennent qu'à vous : la <strong>discussion
  interne</strong>, les <strong>pièces jointes</strong> et une <strong>annotation</strong> propre à
  l'équipe. L'import ne les touche jamais.</p>
</div>

<h3>Le niveau de support</h3>
<p>Il ne se choisit pas : il se <strong>déduit</strong> du gestionnaire. Le niveau porté par son
compte s'applique ; si le gestionnaire indiqué par l'import ne correspond à aucun compte, le
dossier est réputé traité par un niveau externe. C'est ce qui permet de mesurer la répartition
réelle de la charge sans saisie supplémentaire.</p>

<div class="note">
  <b>L'import ne crée jamais de compte</b>
  <p>Il rapproche un nom d'un compte existant. Sans correspondance, le dossier reste sans
  responsable interne. Créer les comptes reste un acte d'administration, délibéré.</p>
</div>`,
        },
        {
            titre: 'Demandes',
            corps: `
<p>Ce que les collaborateurs sollicitent : création de compte, habilitation, logiciel, matériel,
accès distant, assistance. Les catégories sont paramétrables.</p>

<div class="cycle">
  <span>Nouvelle</span><i>→</i><span>Qualifiée</span><i>→</i><span>En cours</span><i>→</i>
  <span>En validation</span><i>→</i><span>Résolue</span><i>→</i><span class="fin">Clôturée</span>
</div>

<p>Comme les incidents, le module est <strong>en lecture seule</strong> et alimenté par l'import
quotidien. Les demandes se distinguent des incidents sur un point : elles passent le plus souvent
par une <strong>validation</strong>, et c'est là que se logent les délais réels — une demande n'attend
pas la technique, elle attend une décision.</p>`,
        },
        {
            titre: 'Projets',
            corps: `
<p>Le module le plus riche, et le seul dont l'échéance n'est pas un engagement de service mais une
<strong>date de fin</strong>.</p>

<div class="cycle">
  <span>Cadrage</span><i>→</i><span>En cours</span><i>→</i><span class="fin">Clôturé</span>
  <i>·</i><span>Suspendu</span>
</div>

<div class="defs">
  <div><dt>Types de projet</dt><dd>Paramétrables. Chaque type peut porter des <strong>jalons
    types</strong>, créés automatiquement à l'ouverture d'un projet — deux projets de même nature
    démarrent donc avec le même squelette.</dd></div>
  <div><dt>Jalons</dt><dd>Étapes datées, marquées atteintes ou non, avec rappels avant échéance.</dd></div>
  <div><dt>Tâches</dt><dd>Le travail réel : titre, assigné, échéance, statut, ordre. Réordonnables.</dd></div>
  <div><dt>Avancement</dt><dd>Se lit des jalons atteints et des tâches terminées.</dd></div>
  <div><dt>Budget</dt><dd>Champ de suivi du projet. La plateforme n'est pas un outil comptable :
    elle enregistre un montant et son suivi, elle ne tient pas d'écritures.</dd></div>
  <div><dt>Notes, documents, liens</dt><dd>La mémoire du projet : décisions, comptes rendus,
    livrables, ressources externes.</dd></div>
</div>`,
        },
        {
            titre: 'Changements',
            corps: `
<p>Toute modification volontaire d'un service en production. C'est le module où la validation
compte le plus, parce que c'est là qu'on casse ce qui marche.</p>

<div class="cycle">
  <span>Brouillon</span><i>→</i><span>Soumis</span><i>→</i><span>Évaluation</span><i>→</i>
  <span>Comité</span><i>→</i><span>Validé</span><i>→</i><span>Planifié</span><i>→</i>
  <span>En implémentation</span><i>→</i><span>Implémenté</span><i>→</i><span>Revue</span><i>→</i>
  <span class="fin">Clôturé</span>
</div>
<p>Transitions transverses : <strong>Rejeté</strong> et <strong>Retour arrière</strong>.</p>

<table>
  <caption>Trois natures de changement, trois régimes d'approbation</caption>
  <thead><tr><th>Nature</th><th>Approbation</th><th>Usage</th></tr></thead>
  <tbody>
    <tr><td><strong>Standard</strong></td><td>Pré-approuvée</td>
        <td>Opération répétitive, au risque connu et à la procédure écrite.</td></tr>
    <tr><td><strong>Normal</strong></td><td>Comité de validation</td>
        <td>Le cas courant : évaluation d'impact et de risque, puis décision collégiale.</td></tr>
    <tr><td><strong>Urgent</strong></td><td>Comité restreint</td>
        <td>Rétablir un service ou parer un risque immédiat. Circuit court, revue <em>a posteriori</em>
        obligatoire.</td></tr>
  </tbody>
</table>

<div class="note">
  <b>La revue post-implémentation n'est pas une formalité</b>
  <p>C'est l'étape qui distingue un processus de changement d'un simple registre. Elle consigne ce
  qui s'est réellement passé — y compris quand tout s'est bien passé. Sans elle, l'indicateur
  « part de changements hors comité » ne mesure plus rien.</p>
</div>`,
        },
        {
            titre: 'Audit et recommandations',
            corps: `
<p>Le suivi des recommandations formulées par les instances de contrôle. La <strong>source</strong>
est portée par la catégorie et se paramètre : audit interne, audit du groupe, régulateur, contrôle
permanent, gestion des risques, commissaires aux comptes — ou toute autre instance propre à votre
organisation.</p>

<div class="cycle">
  <span>Ouverte</span><i>→</i><span>Plan d'action</span><i>→</i><span>En cours</span><i>→</i>
  <span>Validation de clôture</span><i>→</i><span class="fin">Clôturée</span>
</div>

<p>Une recommandation ne se clôt pas seule : la <strong>validation de clôture</strong> est confiée à
des valideurs désignés, et le dossier doit porter ses <strong>justificatifs</strong>. C'est
exactement ce qu'un contrôleur demandera — autant que ce soit déjà rangé.</p>

<div class="note ok">
  <b>Ce que ce module fait gagner</b>
  <p>La question d'un auditeur n'est jamais « avez-vous corrigé ? » mais « <em>prouvez</em> que vous
  avez corrigé, et montrez quand ». Un plan d'action daté, tracé, avec ses pièces et sa validation,
  répond en une impression.</p>
</div>`,
        },
        {
            titre: 'Risques',
            corps: `
<p>L'identification et le traitement des risques. Ce module ne fonctionne pas au délai mais à la
<strong>criticité</strong> et à la <strong>revue périodique</strong>.</p>

<div class="cycle">
  <span>Identifié</span><i>→</i><span>Évalué</span><i>→</i><span>Traitement</span><i>→</i>
  <span class="fin">Maîtrisé</span><i>ou</i><span class="fin">Accepté</span><i>→</i>
  <span>Revue périodique</span>
</div>

<p>La criticité se calcule : <strong>probabilité × impact</strong>. Le résultat positionne le risque
dans une matrice, restituée telle quelle dans les analyses.</p>

<div class="note">
  <b>Pas d'engagement de délai sur un risque</b>
  <p>Un risque ne se « résout » pas en quatre heures : il se traite, puis il se surveille. Lui
  imposer un chronomètre produirait un indicateur faux. Ce qui compte ici, c'est que la
  <strong>revue</strong> ait lieu — et c'est elle qui déclenche des rappels.</p>
</div>

<div class="note danger">
  <b>Limite actuelle</b>
  <p>L'export tabulaire de la liste des risques n'est pas encore disponible côté serveur : les
  boutons d'export de cet écran échouent. Les analyses restituent en revanche la matrice des risques
  et s'exportent normalement.</p>
</div>`,
        },
        {
            titre: 'Cybersécurité',
            corps: `
<p>Le suivi des sujets de sécurité : habilitations sensibles, comptes à privilèges, revues d'accès,
vulnérabilités, correctifs, dispositifs d'authentification. Chaque sujet est une activité, avec ses
responsables, ses engagements, ses pièces et sa revue.</p>

<p>Le module s'appuie sur l'<strong>écran générique d'activités par catégorie</strong> : liste
filtrable, fiche complète, tâches, documents, liens, revue périodique. Les catégories décrivent
la nature du sujet et se paramètrent librement.</p>

<div class="note">
  <b>Un module de suivi, pas un outil de sécurité</b>
  <p>La plateforme ne scanne rien et n'applique aucun correctif. Elle garantit qu'un sujet de
  sécurité identifié a un responsable, une échéance, une trace — et qu'il ne se perd pas. Le
  dispositif d'authentification de la plateforme elle-même est traité au chapitre Sécurité, et n'a
  rien à voir avec ce module.</p>
</div>`,
        },
        {
            titre: 'Gouvernance',
            corps: `
<p>Le suivi des instances et de leurs suites : comités, décisions de direction, plans d'action,
engagements pris. Une décision de comité devient une activité, avec un responsable et une échéance
— ce qui la rend suivable au lieu de la laisser dans un compte rendu.</p>

<p>Comme la cybersécurité, ce module utilise l'écran générique d'activités par catégorie, avec
revue périodique.</p>

<div class="note ok">
  <b>La vertu de ce module</b>
  <p>Un comité produit des décisions ; ce qui manque presque toujours, c'est le lien entre la
  décision et son exécution. En faisant de chaque engagement une activité ordinaire, on le retrouve
  dans les mêmes listes, les mêmes rappels et les mêmes indicateurs que le reste.</p>
</div>`,
        },
        {
            titre: 'Inventaire du patrimoine',
            corps: `
<p>Le registre du parc : matériel, équipements, immobilisations. Chaque bien porte son code
d'immobilisation, sa référence interne, son numéro de série, son modèle, sa désignation, son
emplacement, son détenteur, sa date et sa valeur d'acquisition, sa durée et son taux
d'amortissement.</p>

<div class="defs">
  <div><dt>Valeur nette</dt><dd>Calculée à partir de la valeur d'acquisition, de la durée et du
    taux. Le parc se lit donc aussi comme un actif, pas seulement comme une liste.</dd></div>
  <div><dt>État constaté</dt><dd>Porté par la fiche de l'équipement, avec sa date, son auteur et
    son motif. Un bien peut être en bon état, au rebut, cassé ou non retrouvé.</dd></div>
  <div><dt>Référentiels</dt><dd>Emplacements, départements et types d'équipement sont
    paramétrables.</dd></div>
  <div><dt>Discussion</dt><dd>Chaque équipement porte son fil d'échanges, comme une activité.</dd></div>
</div>

<p>Le parc s'alimente par <strong>import de classeur</strong> et s'exporte. Un
<strong>classeur modèle</strong> est téléchargeable depuis l'écran : c'est le moyen le plus sûr
d'obtenir un fichier que l'import acceptera du premier coup.</p>

<div class="note">
  <b>L'import ne piétine pas la saisie</b>
  <p>Le rapprochement se fait sur le code d'immobilisation. Ce que vos équipes ont renseigné à
  l'écran — état constaté, détenteur, motif — n'est jamais écrasé par un import ultérieur.</p>
</div>`,
        },
        {
            titre: 'Analyses',
            corps: `
<p>L'écran d'étude, distinct du tableau de bord : celui-ci montre l'état du moment, celui-là
cherche à comprendre.</p>

<table>
  <thead><tr><th>Famille</th><th>Ce qu'on y lit</th></tr></thead>
  <tbody>
    <tr><td><strong>Répartitions</strong></td><td>Par module, entité, responsable, priorité, catégorie.</td></tr>
    <tr><td><strong>Engagements</strong></td><td>Respect global, par module et par priorité ; distribution
        des délais ; prise en charge par priorité.</td></tr>
    <tr><td><strong>Flux</strong></td><td>Tendance sur la période, durée passée dans chaque état,
        vieillissement du stock, taux de réouverture.</td></tr>
    <tr><td><strong>Charge par gestionnaire</strong></td><td>Volume, délais et respect des engagements,
        avec une fiche par personne.</td></tr>
    <tr><td><strong>Matrice mensuelle</strong></td><td>Le mois par mois, pour comparer des périodes
        plutôt que des instants.</td></tr>
    <tr><td><strong>Concentration</strong></td><td>Les catégories qui produisent le plus de volume —
        celles sur lesquelles une action de fond paie.</td></tr>
    <tr><td><strong>Matrice des risques</strong></td><td>Probabilité × impact, telle qu'elle se
        présente à un comité.</td></tr>
  </tbody>
</table>

<div class="note">
  <b>À quoi servent ces écrans</b>
  <p>Le vieillissement et la concentration par catégorie sont les deux vues qui font agir : la
  première dit ce qui pourrit dans le stock, la seconde ce qu'il faut traiter à la racine pour que
  le volume baisse. Les moyennes, elles, rassurent sans jamais rien indiquer.</p>
</div>`,
        },
    ],
};
