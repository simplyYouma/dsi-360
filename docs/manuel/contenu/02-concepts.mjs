export const chapitre = {
    titre: 'Concepts',
    intro:
        'Huit notions suffisent à comprendre toute la plateforme. Elles sont communes à '
        + 'tous les modules : ce qui est vrai d\'un incident l\'est d\'un projet ou d\'une '
        + 'recommandation. Assimiler ce chapitre dispense de réapprendre à chaque écran.',
    sections: [
        {
            titre: 'L\'activité, entité pivot',
            corps: `
<p>Une <strong>activité</strong> est toute chose suivie de bout en bout par une équipe. Un incident,
une demande, un projet, un changement, une recommandation d'audit, un risque : ce sont des
<em>types</em> d'activité, pas des objets sans rapport.</p>

<p>Ce choix n'est pas cosmétique. Parce que tout dérive d'un socle commun, les responsabilités,
les délais, l'historique, la recherche, les notifications et les indicateurs sont écrits
<strong>une fois</strong> et valent partout. Ajouter un type d'activité ne demande pas de tout
reconstruire — c'est la raison pour laquelle la plateforme s'étend sans se refondre.</p>

<table>
  <caption>Le socle commun à toute activité</caption>
  <thead><tr><th>Attribut</th><th>Rôle</th></tr></thead>
  <tbody>
    <tr><td><strong>Référence</strong></td><td>Identifiant lisible et unique, préfixé par le type et
      daté — par exemple <code>INC-2026-00042</code>. C'est ce qu'on cite dans un courriel ou au
      téléphone.</td></tr>
    <tr><td><strong>Type</strong></td><td>Le module dont relève l'activité. Il détermine son cycle de
      vie et ses catégories.</td></tr>
    <tr><td><strong>Titre, description</strong></td><td>De quoi il s'agit, en clair.</td></tr>
    <tr><td><strong>Demandeur</strong></td><td>Qui est à l'origine.</td></tr>
    <tr><td><strong>Responsable principal</strong></td><td>Une seule personne, comptable du résultat.</td></tr>
    <tr><td><strong>Contributeurs</strong></td><td>Ceux qui font le travail.</td></tr>
    <tr><td><strong>Valideurs</strong></td><td>Ceux dont l'accord est requis, quand le type le prévoit.</td></tr>
    <tr><td><strong>Entité</strong></td><td>Le périmètre concerné — service, direction, site.</td></tr>
    <tr><td><strong>Catégorie</strong></td><td>Paramétrable, propre à chaque type.</td></tr>
    <tr><td><strong>Impact, urgence</strong></td><td>Les deux entrées d'où découle la priorité.</td></tr>
    <tr><td><strong>Priorité</strong></td><td>De P1 à P5, <em>dérivée</em> de l'impact et de l'urgence.</td></tr>
    <tr><td><strong>État</strong></td><td>Position dans le cycle de vie du type.</td></tr>
    <tr><td><strong>Engagements</strong></td><td>Cibles de prise en charge et de résolution.</td></tr>
    <tr><td><strong>Dates</strong></td><td>Création, prise en charge, échéance, résolution, clôture.</td></tr>
    <tr><td><strong>Échanges, pièces jointes</strong></td><td>La discussion et les preuves attachées au dossier.</td></tr>
    <tr><td><strong>Historique</strong></td><td>Chaque changement, avec auteur, horodatage et valeurs.</td></tr>
  </tbody>
</table>`,
        },
        {
            titre: 'Les quatre responsabilités',
            corps: `
<p>Un dossier sans responsable désigné n'avance pas ; un dossier avec trois responsables non plus.
La plateforme distingue donc quatre rôles, sur chaque activité.</p>

<div class="defs">
  <div><dt>Demandeur</dt>
       <dd>À l'origine de l'activité. Il est informé de l'avancement et, selon le type, de la
       clôture. Il n'a pas de pouvoir de décision sur le traitement.</dd></div>
  <div><dt>Responsable principal</dt>
       <dd><strong>Une seule personne</strong>, jamais un groupe. C'est elle qu'on interroge sur
       l'avancement, elle qui répond du délai. Les indicateurs par responsable s'appuient sur ce
       champ.</dd></div>
  <div><dt>Contributeurs</dt>
       <dd>Ceux qui exécutent. Ils peuvent être plusieurs, appartenir à des équipes différentes,
       entrer et sortir en cours de route.</dd></div>
  <div><dt>Valideurs</dt>
       <dd>Ceux dont l'accord conditionne une transition — approbation d'un changement, validation
       de la clôture d'une recommandation. Le cycle de vie du type indique où leur accord est
       requis.</dd></div>
</div>

<div class="note">
  <b>Pourquoi un seul responsable</b>
  <p>Une responsabilité partagée entre deux personnes est une responsabilité que personne
  n'assume. Le champ n'accepte donc qu'un nom. Le travail, lui, peut être partagé : c'est le rôle
  des contributeurs.</p>
</div>`,
        },
        {
            titre: 'Impact, urgence, priorité',
            corps: `
<p>La priorité ne se saisit pas : elle se <strong>déduit</strong>. On renseigne deux choses
observables, et une matrice paramétrable en tire une priorité de <strong>P1</strong> (critique) à
<strong>P5</strong> (très faible).</p>

<div class="defs">
  <div><dt>Impact</dt><dd><em>Combien de monde, ou quelle part de l'activité, est touché ?</em>
    Gradué — de la personne isolée à la totalité des utilisateurs.</dd></div>
  <div><dt>Urgence</dt><dd><em>À quelle vitesse la situation se dégrade-t-elle ?</em> Indépendante
    de l'impact : une gêne pour une personne peut être très urgente, une panne large peut
    attendre la nuit.</dd></div>
</div>

<table>
  <caption>Exemple de matrice — les valeurs se paramètrent, la mécanique ne change pas</caption>
  <thead><tr><th>Impact ↓ / Urgence →</th><th>Haute</th><th>Moyenne</th><th>Basse</th></tr></thead>
  <tbody>
    <tr><td><strong>Étendu</strong> (majorité des utilisateurs)</td><td>P1</td><td>P2</td><td>P3</td></tr>
    <tr><td><strong>Significatif</strong> (une équipe, un site)</td><td>P2</td><td>P3</td><td>P4</td></tr>
    <tr><td><strong>Limité</strong> (une personne)</td><td>P3</td><td>P4</td><td>P5</td></tr>
  </tbody>
</table>

<div class="note attention">
  <b>Ce que cela évite</b>
  <p>Quand chacun choisit librement la priorité, tout devient prioritaire — et la notion perd son
  sens. En dérivant la priorité de deux faits observables, la plateforme rend la discussion
  possible : on ne débat plus d'un ressenti, on débat de l'impact ou de l'urgence, chacun
  argumentable.</p>
</div>`,
        },
        {
            titre: 'Les engagements de service',
            corps: `
<p>Un <strong>engagement de service</strong> est une promesse de délai, exprimée en deux temps :</p>

<ul>
  <li>la <strong>prise en charge</strong> — le délai au bout duquel quelqu'un s'est saisi du dossier ;</li>
  <li>la <strong>résolution</strong> — le délai au bout duquel le sujet est traité.</li>
</ul>

<p>Les deux cibles sont paramétrées par croisement du <em>type</em>, de la <em>priorité</em>, de la
<em>criticité</em> et de la <em>catégorie</em>. À l'ouverture d'une activité, les échéances sont
calculées et inscrites sur le dossier ; elles ne bougent plus.</p>

<table>
  <caption>Exemple de grille — à ajuster à ce que votre organisation peut réellement tenir</caption>
  <thead><tr><th>Priorité</th><th>Prise en charge</th><th>Résolution</th></tr></thead>
  <tbody>
    <tr><td><span class="pastille danger">P1 — Critique</span></td><td class="num">15 minutes</td><td class="num">4 heures</td></tr>
    <tr><td><span class="pastille alerte">P2 — Haute</span></td><td class="num">30 minutes</td><td class="num">8 heures</td></tr>
    <tr><td><span class="pastille neutre">P3 — Moyenne</span></td><td class="num">2 heures</td><td class="num">2 jours</td></tr>
    <tr><td><span class="pastille neutre">P4 — Faible</span></td><td class="num">1 jour</td><td class="num">5 jours</td></tr>
  </tbody>
</table>

<p>Chaque activité porte en permanence un <strong>état d'engagement</strong>, lisible d'un coup d'œil
dans les listes :</p>

<p>
  <span class="pastille ok">À l'heure</span>&nbsp;
  <span class="pastille alerte">Échéance proche</span>&nbsp;
  <span class="pastille danger">Dépassé</span>
</p>

<div class="note">
  <b>Un engagement réaliste vaut mieux qu'un engagement flatteur</b>
  <p>Une grille trop ambitieuse produit un taux de respect médiocre, que plus personne ne regarde
  au bout de deux mois. Commencez par mesurer vos délais réels pendant quelques semaines, puis
  fixez des cibles légèrement exigeantes. La grille se modifie à tout moment : elle s'applique
  aux activités <em>ouvertes ensuite</em>, jamais rétroactivement.</p>
</div>`,
        },
        {
            titre: 'Cycles de vie',
            corps: `
<p>Chaque type d'activité suit une <strong>suite d'états</strong> et n'autorise que certaines
transitions. On ne passe pas de « nouveau » à « clôturé » sans être passé par la résolution ; on
ne clôture pas un dossier dont la validation est requise et absente.</p>

<h3>Cycle d'un incident</h3>
<div class="cycle">
  <span>Nouveau</span><i>→</i><span>Ouvert</span><i>→</i><span>Résolu</span><i>→</i>
  <span class="fin">Clôturé</span>
</div>
<p>Transitions transverses : <strong>Réouvert</strong> (le demandeur constate que le problème
persiste) et <strong>Annulé</strong> (le traitement s'avère sans objet).</p>

<h3>Cycle d'une demande</h3>
<div class="cycle">
  <span>Nouvelle</span><i>→</i><span>Qualifiée</span><i>→</i><span>En cours</span><i>→</i>
  <span>En validation</span><i>→</i><span>Résolue</span><i>→</i><span class="fin">Clôturée</span>
</div>
<p>Transitions transverses : <strong>Rejetée</strong>, <strong>Réouverte</strong>.</p>

<h3>Cycle d'un changement</h3>
<div class="cycle">
  <span>Brouillon</span><i>→</i><span>Soumis</span><i>→</i><span>Évaluation</span><i>→</i>
  <span>Comité</span><i>→</i><span>Planifié</span><i>→</i><span>En cours</span><i>→</i>
  <span>Implémenté</span><i>→</i><span>Revue</span><i>→</i><span class="fin">Clôturé</span>
</div>
<p>Transition transverse : <strong>Retour arrière</strong>, quand la mise en œuvre échoue et qu'on
revient à l'état antérieur.</p>

<div class="note">
  <b>Les états sont paramétrables, la discipline ne l'est pas</b>
  <p>Vous pouvez renommer un état, en ajouter, en retirer. Ce que vous ne pouvez pas faire, c'est
  contourner une transition : le serveur refuse un passage non prévu et l'explique. C'est ce qui
  garantit qu'un indicateur de « taux de résolution » veut dire quelque chose.</p>
</div>`,
        },
        {
            titre: 'Périmètres et cloisonnement',
            corps: `
<p>Une activité appartient à une <strong>entité</strong> — service, direction, site, filiale, selon
le découpage de votre organisation. Un profil dit <em>transverse</em> voit tout ; un profil qui ne
l'est pas ne voit que les activités de son entité.</p>

<p>Ce cloisonnement est appliqué <strong>au niveau des requêtes</strong>, pas à l'affichage : un
utilisateur qui devinerait la référence d'un dossier hors de son périmètre obtient une réponse
« introuvable », pas le dossier.</p>

<div class="note">
  <b>Un mécanisme qui dort sans nuire</b>
  <p>Si votre déploiement ne comporte qu'une seule entité, le cloisonnement est neutre : tout le
  monde voit tout. Il reste en place et testé. Le jour où une deuxième entité apparaît, il n'y a
  rien à développer — seulement à déclarer l'entité et à retirer le caractère transverse des
  profils concernés.</p>
</div>`,
        },
        {
            titre: 'Les référentiels paramétrables',
            corps: `
<p>Tout ce qui, dans une organisation, est susceptible de changer sans prévenir a été sorti du
code. Ces valeurs s'éditent depuis l'administration, et prennent effet immédiatement.</p>

<div class="defs">
  <div><dt>Types d'activité</dt><dd>Les modules ouverts et leurs préfixes de référence.</dd></div>
  <div><dt>Catégories</dt><dd>Par type. Elles servent au classement, aux statistiques et, souvent,
    au calcul des engagements.</dd></div>
  <div><dt>Matrice de priorité</dt><dd>Impact × urgence → P1 à P5.</dd></div>
  <div><dt>Matrice des engagements</dt><dd>Type, priorité, criticité, catégorie → prise en charge
    et résolution.</dd></div>
  <div><dt>États et transitions</dt><dd>Le cycle de vie de chaque type.</dd></div>
  <div><dt>Profils et droits</dt><dd>Qui accède à quel module, pour quelles actions.</dd></div>
  <div><dt>Entités</dt><dd>Le découpage organisationnel qui porte le cloisonnement.</dd></div>
  <div><dt>Sources et natures</dt><dd>Origines d'une recommandation, types de changement, et autres
    nomenclatures propres à un module.</dd></div>
</div>

<p>La règle est simple : <strong>ajouter une valeur n'est jamais un projet informatique</strong>.
Si vous vous trouvez à demander une évolution logicielle pour créer une catégorie, quelque chose
a été mal paramétré.</p>`,
        },
        {
            titre: 'La traçabilité',
            corps: `
<p>Chaque création, modification, affectation, validation et clôture est journalisée avec :
l'<strong>auteur</strong>, la <strong>date et l'heure</strong>, le <strong>module</strong>,
l'<strong>action</strong>, l'<strong>ancienne et la nouvelle valeur</strong>, et l'<strong>adresse
réseau</strong> d'où l'action a été faite.</p>

<p>Le journal est en <strong>ajout seul</strong> : rien ne s'y modifie, rien ne s'en efface. Les
entrées sont de plus <strong>chaînées par empreinte</strong> — chacune porte la marque de la
précédente, de sorte qu'une altération, même par quelqu'un ayant accès à la base, devient
détectable.</p>

<div class="note ok">
  <b>Ce que la traçabilité permet réellement</b>
  <ul>
    <li>Répondre à un auditeur sans reconstituer quoi que ce soit.</li>
    <li>Comprendre <em>pourquoi</em> une échéance a bougé, et sur décision de qui.</li>
    <li>Distinguer une erreur de saisie d'un contournement délibéré.</li>
    <li>Conserver l'histoire d'un dossier même après le départ de la personne qui l'a traité :
        l'auteur est figé à l'écriture et survit à la suppression de son compte.</li>
  </ul>
</div>`,
        },
    ],
};
