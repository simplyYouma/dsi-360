export const chapitre = {
    titre: 'Adapter la plateforme',
    intro:
        'La plateforme n\'a pas été conçue pour un métier : elle a été conçue pour un mode de '
        + 'travail — des choses à faire, des responsables, des délais, des validations, des '
        + 'preuves. Ce chapitre montre jusqu\'où elle se règle sans développement, où passe '
        + 'la limite, et comment mener un paramétrage qui tienne.',
    sections: [
        {
            titre: 'Ce qui se règle sans développement',
            corps: `
<p>Le principe de conception le plus structurant est aussi le plus utile en déploiement :
<strong>ce qui varie d'une organisation à l'autre n'est pas dans le code</strong>.</p>

<table>
  <thead><tr><th>Élément</th><th>Se règle</th><th>Effet</th></tr></thead>
  <tbody>
    <tr><td>Modules ouverts</td><td>Matrice des accès</td><td>Ce que chaque métier voit dans le rail</td></tr>
    <tr><td>Profils métier</td><td>Administration</td><td>Créer, renommer, supprimer — sans liste figée</td></tr>
    <tr><td>Entités</td><td>Administration</td><td>Le découpage qui porte le cloisonnement</td></tr>
    <tr><td>Catégories</td><td>Par module</td><td>Le vocabulaire de classement de votre organisation</td></tr>
    <tr><td>Matrice de priorité</td><td>Paramétrage</td><td>Ce que « critique » veut dire chez vous</td></tr>
    <tr><td>Engagements de délai</td><td>Par module et priorité</td><td>Les promesses que vous pouvez tenir</td></tr>
    <tr><td>États et transitions</td><td>Cycles de vie</td><td>Votre processus, pas celui d'un éditeur</td></tr>
    <tr><td>Types de projet et jalons types</td><td>Module projets</td><td>Un squelette par nature d'affaire</td></tr>
    <tr><td>Référentiels d'inventaire</td><td>Module inventaire</td><td>Emplacements, types, départements</td></tr>
    <tr><td>Canaux de notification</td><td>Par agent</td><td>Ce que chacun reçoit, et comment</td></tr>
  </tbody>
</table>

<p>Le test est simple : <strong>si vous vous surprenez à demander une évolution logicielle pour
ajouter une catégorie, une entité, un profil ou un délai, c'est un paramétrage qui a été manqué.</strong></p>`,
        },
        {
            titre: 'Une méthode de paramétrage',
            corps: `
<p>Un paramétrage réussi ne se décide pas en réunion : il se dérive de ce qui se fait déjà.</p>

<ol class="etapes">
  <li><b>Inventorier ce que vous suivez réellement</b>
      Listez les objets que votre équipe suit de bout en bout. Chacun devient un <em>type
      d'activité</em>. Résistez à la tentation d'en créer un par nuance : deux objets qui suivent le
      même chemin et se mesurent pareil n'en font qu'un.</li>
  <li><b>Écrire le chemin de chacun</b>
      Les états par lesquels il passe, dans l'ordre, et ceux d'où l'on ne revient pas. Là où
      quelqu'un doit donner son accord, vous avez une <em>porte de validation</em>.</li>
  <li><b>Nommer les catégories</b>
      Reprenez le vocabulaire réellement employé. Une catégorie que personne n'emploie à l'oral ne
      sera pas renseignée à l'écran. Commencez court.</li>
  <li><b>Mesurer avant de promettre</b>
      Faites tourner quelques semaines <strong>sans engagement de délai</strong>, puis regardez vos
      délais réels. Les cibles se fixent à partir de là — légèrement exigeantes, jamais
      fantaisistes.</li>
  <li><b>Ouvrir les droits au plus juste</b>
      Un profil par métier, pas par personne. On ouvre ce dont le métier a besoin ; on n'ouvre pas
      « pour voir ».</li>
  <li><b>Faire une revue à trois mois</b>
      Les catégories inutilisées se suppriment, les délais jamais tenus se rediscutent, les
      profils qui se ressemblent se fusionnent. Un paramétrage qu'on ne revoit jamais devient
      faux.</li>
</ol>`,
        },
        {
            titre: 'Décliner à d\'autres métiers',
            corps: `
<p>Le socle — une chose à faire, un responsable, un délai, une validation, une preuve — ne
appartient à aucun métier. Voici comment il se lit ailleurs.</p>

<div class="cartes">
  <div class="carte"><b>Qualité et conformité</b><span>Non-conformités, actions correctives et
    préventives, audits internes, revues de direction. Les recommandations et leur validation de
    clôture s'y transposent mot pour mot.</span></div>
  <div class="carte"><b>Services généraux et maintenance</b><span>Demandes d'intervention,
    maintenance préventive, parc de bâtiments et d'équipements, contrôles réglementaires
    périodiques. La revue périodique et l'inventaire y servent tels quels.</span></div>
  <div class="carte"><b>Ressources humaines</b><span>Demandes des collaborateurs, dossiers
    d'intégration et de départ, campagnes d'entretiens, plans de formation. Le cloisonnement par
    entité y prend tout son sens.</span></div>
  <div class="carte"><b>Juridique et contrats</b><span>Saisines, échéances contractuelles, suivi
    des engagements, dossiers à valider. Les délais et les preuves sont le cœur du métier.</span></div>
  <div class="carte"><b>Achats et fournisseurs</b><span>Demandes d'achat, validations en cascade,
    suivi des livraisons, réclamations. Le circuit de validation en est le squelette.</span></div>
  <div class="carte"><b>Gestion des risques</b><span>Cartographie, évaluation, plans de traitement,
    revues. Le module de risques est indépendant de la nature des risques suivis.</span></div>
</div>

<div class="note">
  <b>Un exemple de transposition</b>
  <p>Un service qualité qui suit des non-conformités crée un type d'activité « non-conformité »,
  ses catégories (produit, processus, fournisseur, réglementaire), un cycle
  <em>ouverte → analyse → action corrective → vérification d'efficacité → clôturée</em>, une porte
  de validation avant la clôture, et des délais par gravité. Il obtient sans une ligne de code :
  les responsabilités, les rappels d'échéance, les preuves attachées, l'historique inviolable et
  les indicateurs — c'est-à-dire l'essentiel de ce qu'un auditeur lui demandera.</p>
</div>`,
        },
        {
            titre: 'Ce qui demande un développement',
            corps: `
<p>Une frontière honnête vaut mieux qu'une promesse élastique. Relèvent d'un développement :</p>

<div class="defs">
  <div><dt>Un écran métier spécifique</dt>
       <dd>Les modules disposent d'un écran générique complet (liste, fiche, tâches, documents,
       liens, revue). Une présentation particulière — un plan, un calendrier de charge, une saisie
       de terrain — se développe.</dd></div>
  <div><dt>Un calcul propre à votre métier</dt>
       <dd>La priorité et la criticité sont paramétrables ; une formule d'une autre nature ne
       l'est pas.</dd></div>
  <div><dt>Une intégration avec un autre système</dt>
       <dd>L'import de classeur couvre le cas le plus courant. Un échange en temps réel avec un
       progiciel se développe.</dd></div>
  <div><dt>Un nouveau canal de notification</dt>
       <dd>Aujourd'hui : dans la plateforme et par courriel. Tout autre canal se développe.</dd></div>
  <div><dt>Une identité fédérée</dt>
       <dd>L'authentification est locale. Un raccordement à l'annuaire de l'organisation se
       développe — la structure de données le prévoit, le code reste à écrire.</dd></div>
  <div><dt>Des droits par action, paramétrables</dt>
       <dd>Les accès se paramètrent par module ; les actions sensibles sont gardées en dur, par
       séparation des tâches. Rendre ce niveau paramétrable se développe — et demande d'abord de
       vérifier que c'est souhaitable.</dd></div>
</div>`,
        },
        {
            titre: 'Erreurs de paramétrage fréquentes',
            corps: `
<table>
  <thead><tr><th>Erreur</th><th>Conséquence observée</th><th>À faire</th></tr></thead>
  <tbody>
    <tr><td>Trop de catégories dès le départ</td>
        <td>Tout finit dans « autres » ; les statistiques ne servent à rien</td>
        <td>Commencer avec cinq à dix, ajouter sur besoin démontré</td></tr>
    <tr><td>Des délais copiés d'un modèle</td>
        <td>Taux de respect médiocre, indicateur abandonné en deux mois</td>
        <td>Mesurer d'abord, promettre ensuite</td></tr>
    <tr><td>Un profil par personne</td>
        <td>Matrice illisible, droits qui divergent, départs mal gérés</td>
        <td>Un profil par métier</td></tr>
    <tr><td>Tous les profils transverses</td>
        <td>Le cloisonnement ne protège plus rien</td>
        <td>Transverse pour l'administration et le pilotage, pas pour l'opérationnel</td></tr>
    <tr><td>Un cycle de vie à quinze états</td>
        <td>Personne ne fait avancer les dossiers correctement</td>
        <td>Un état n'existe que si quelqu'un agit différemment selon qu'on y est ou non</td></tr>
    <tr><td>Ouvrir tous les modules « pour voir »</td>
        <td>Écrans vides, adoption diluée, confiance entamée</td>
        <td>Ouvrir un module quand son paramétrage est prêt</td></tr>
    <tr><td>Activer les courriels avant d'avoir réglé les préférences</td>
        <td>Boîtes saturées le premier jour, notifications filtrées pour toujours</td>
        <td>Démarrer en notifications internes, ouvrir les courriels ensuite</td></tr>
  </tbody>
</table>

<div class="note ok">
  <b>La règle qui résume les autres</b>
  <p>Chaque élément de paramétrage doit répondre à une question : <em>quelqu'un agit-il
  différemment selon sa valeur ?</em> Si la réponse est non, il ne mérite pas d'exister — il ne
  sera pas renseigné, et il faussera ce qu'on en tire.</p>
</div>`,
        },
    ],
};
