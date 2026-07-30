export const chapitre = {
    titre: 'Présentation',
    intro:
        'Ce chapitre situe la plateforme : le problème qu\'elle résout, ce qu\'elle ne '
        + 'prétend pas faire, les personnes auxquelles elle s\'adresse et les principes '
        + 'auxquels elle se tient. Le lire prend dix minutes et évite les malentendus '
        + 'coûteux plus tard.',
    sections: [
        {
            titre: 'Le problème',
            corps: `
<p>Dans la plupart des organisations, le travail d'une direction se suit dans des
classeurs. Un onglet par sujet, une couleur par état, un fichier par personne. Cela
fonctionne, jusqu'à un certain volume — puis cela cesse, toujours de la même façon :</p>

<ul>
  <li>personne ne sait dire, à un instant donné, <strong>combien de dossiers sont en retard</strong>
      ni depuis combien de temps ;</li>
  <li>un engagement pris envers un demandeur n'est <strong>rattaché à rien</strong> : il vit dans un
      courriel, on s'aperçoit qu'il est dépassé quand le demandeur relance ;</li>
  <li>une modification de fichier <strong>n'a pas d'auteur</strong> — on découvre qu'une date a
      changé, sans savoir par qui ni quand ;</li>
  <li>consolider un état pour la direction générale <strong>coûte deux jours</strong> de
      copier-coller, et le résultat est déjà périmé le jour de sa présentation ;</li>
  <li>l'arrivée d'un collaborateur suppose de lui expliquer une organisation de fichiers
      que <strong>personne n'a écrite</strong>.</li>
</ul>

<p>Le point commun de ces symptômes n'est pas le manque d'outils : c'est l'absence d'un
<strong>endroit unique</strong> où une chose à faire existe, avec son responsable, son échéance
et son historique.</p>`,
        },
        {
            titre: 'Ce que fait la plateforme',
            corps: `
<p>La plateforme centralise les <strong>activités</strong> d'une organisation — tout ce qui est
suivi de bout en bout par une équipe —, leur applique des <strong>engagements de délai</strong>,
<strong>trace chaque action</strong> et restitue à la direction des <strong>indicateurs fiables</strong>.</p>

<div class="cartes">
  <div class="carte"><b>Un référentiel unique</b><span>Chaque dossier a une référence lisible, un
    responsable désigné, une échéance et un état. Il n'existe qu'à un seul endroit.</span></div>
  <div class="carte"><b>Des délais tenus</b><span>Les engagements de prise en charge et de
    résolution sont calculés à l'ouverture. L'approche et le dépassement se signalent seuls.</span></div>
  <div class="carte"><b>Une mémoire vérifiable</b><span>Toute modification est journalisée avec son
    auteur, l'ancienne et la nouvelle valeur. Rien ne s'efface.</span></div>
  <div class="carte"><b>Un pilotage immédiat</b><span>Les indicateurs se recalculent en continu et
    s'exportent. Le rapport n'est plus un travail, c'est une lecture.</span></div>
</div>

<p>Le vocabulaire du manuel reste volontairement neutre. Une <em>activité</em> peut être un
incident technique, une demande d'un collaborateur, un projet, un changement à valider, une
recommandation d'audit, un risque à traiter — ou tout autre objet que votre organisation suit.
Les types, les catégories, les états et les délais sont des <strong>paramètres</strong>, non du code.</p>`,
        },
        {
            titre: 'Ce qu\'elle ne fait pas',
            corps: `
<p>Une frontière claire vaut mieux qu'une promesse large. La plateforme n'est pas :</p>

<div class="defs">
  <div><dt>Un outil de supervision technique</dt>
       <dd>Elle ne surveille ni serveurs, ni réseau, ni applications en temps réel. Elle
       enregistre et pilote le <em>traitement</em> de ce qui a été constaté, pas la constatation.</dd></div>
  <div><dt>Un logiciel de comptabilité</dt>
       <dd>Elle suit des budgets de projet et des engagements, pas des écritures comptables.</dd></div>
  <div><dt>Une messagerie ni un espace documentaire</dt>
       <dd>Les échanges et les pièces jointes qu'elle porte sont ceux d'un dossier. Elle ne
       remplace ni la messagerie de l'organisation, ni sa gestion électronique de documents.</dd></div>
  <div><dt>Un progiciel générique du marché</dt>
       <dd>Elle est conçue pour être <em>réglée</em> sur le fonctionnement réel d'une organisation,
       pas pour lui imposer le sien. C'est un choix, avec sa contrepartie : le paramétrage initial
       demande des décisions (cf. chapitre sur l'administration).</dd></div>
</div>`,
        },
        {
            titre: 'À qui s\'adresse ce manuel',
            corps: `
<p>Trois lectures cohabitent dans ce document. Chacune a son point d'entrée.</p>

<table>
  <thead><tr><th>Vous êtes…</th><th>Vous cherchez…</th><th>Commencez par</th></tr></thead>
  <tbody>
    <tr><td><strong>Utilisateur</strong><br>vous traitez des dossiers au quotidien</td>
        <td>vous connecter, comprendre une fiche, faire avancer un dossier</td>
        <td>chapitres <em>Concepts</em> et <em>Prise en main</em>, puis le module qui vous concerne</td></tr>
    <tr><td><strong>Administrateur fonctionnel</strong><br>vous réglez la plateforme</td>
        <td>créer des comptes, ouvrir des droits, définir catégories et délais</td>
        <td>chapitre <em>Administration</em></td></tr>
    <tr><td><strong>Responsable technique</strong><br>vous installez et exploitez</td>
        <td>installer, sauvegarder, superviser, mettre à jour</td>
        <td>chapitres <em>Sécurité</em> et <em>Exploitation</em></td></tr>
  </tbody>
</table>

<div class="note">
  <b>Convention de lecture</b>
  <p>Les termes qui ont un sens précis dans la plateforme — <em>activité</em>, <em>profil</em>,
  <em>périmètre</em>, <em>engagement de service</em> — sont définis au chapitre suivant et repris
  dans le glossaire en annexe. Un mot du manuel désigne toujours la même chose.</p>
</div>`,
        },
        {
            titre: 'Principes directeurs',
            corps: `
<p>Ces principes ne décrivent pas une intention : ils se vérifient dans le produit. Ils
expliquent la plupart des choix que vous rencontrerez en l'utilisant.</p>

<ol class="etapes">
  <li><b>Ce qui varie est paramétré, jamais codé</b>
      Catégories, états, délais, profils, sources : ajouter une valeur relève du paramétrage,
      sans nouvelle version du logiciel ni interruption de service.</li>
  <li><b>Tout accès est vérifié côté serveur</b>
      Un bouton absent de l'écran ne protège rien. Chaque appel est contrôlé par le serveur,
      indépendamment de ce que l'interface a bien voulu afficher.</li>
  <li><b>Rien ne disparaît</b>
      Le journal est en ajout seul. Une correction laisse une trace de l'ancienne valeur. Un
      dossier ne se supprime pas : il change d'état.</li>
  <li><b>Évoluer sans refondre</b>
      Un nouveau type d'activité est une déclinaison d'un socle commun, pas une réécriture. Les
      responsabilités, les délais, l'historique et les indicateurs sont mutualisés.</li>
  <li><b>La couleur porte du sens</b>
      Elle signale un état ou une action, jamais un décor. Aucun clignotement, aucune animation
      gratuite : un écran de travail se consulte des heures durant.</li>
</ol>`,
        },
    ],
};
