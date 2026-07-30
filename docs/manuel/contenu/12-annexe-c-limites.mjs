export const chapitre = {
    annexe: true,
    titre: 'Limites connues',
    intro:
        'Ce que la plateforme ne fait pas encore, écrit noir sur blanc. Un manuel qui tait '
        + 'ses limites se retourne contre celui qui l\'a écrit — à la première démonstration, '
        + 'puis à chaque fois. Ce qui suit est l\'état exact du produit à la date de ce '
        + 'document.',
    sections: [
        {
            titre: 'Fonctionnalités annoncées ailleurs, non disponibles',
            corps: `
<table>
  <thead><tr><th>Sujet</th><th>État réel</th><th>Contournement</th></tr></thead>
  <tbody>
    <tr><td><strong>Second facteur d'authentification</strong></td>
        <td>Aucun. La décision est prise, la construction reste à faire.</td>
        <td>Frein anti-force brute, jetons courts, révocation immédiate des comptes.</td></tr>
    <tr><td><strong>Identité fédérée</strong> (annuaire, identité unique)</td>
        <td>Non implémentée. La structure de données prévoit la porte, le code n'existe pas.</td>
        <td>Authentification locale ; blocage manuel au départ d'un collaborateur.</td></tr>
    <tr><td><strong>Notifications vers une messagerie d'équipe ou instantanée</strong></td>
        <td>Les préférences existent, aucun envoi n'est codé.</td>
        <td>Notifications internes et courriel.</td></tr>
    <tr><td><strong>Génération de PDF côté serveur</strong></td>
        <td>Absente. Le PDF est produit par le navigateur, à partir de ce qui est affiché.</td>
        <td>Export PDF depuis le tableau de bord et l'espace personnel ; exports tabulaires
        côté serveur pour le reste.</td></tr>
    <tr><td><strong>Export tabulaire des risques</strong></td>
        <td>Le bouton existe à l'écran, la route serveur non : l'export échoue.</td>
        <td>Passer par les analyses, qui restituent et exportent la matrice des risques.</td></tr>
    <tr><td><strong>Écrans spécialisés cybersécurité et gouvernance</strong></td>
        <td>Servis par l'écran générique d'activités par catégorie.</td>
        <td>L'écran générique couvre liste, fiche, tâches, documents, liens et revue.</td></tr>
    <tr><td><strong>Module « problèmes »</strong> (analyse de causes récurrentes)</td>
        <td>Non implémenté. Des engagements de service subsistent en base sans module
        correspondant.</td>
        <td>Suivre l'analyse de fond comme un projet ou une activité de gouvernance.</td></tr>
    <tr><td><strong>Plan de continuité, budget consolidé, application mobile</strong></td>
        <td>Non implémentés. Le budget n'existe qu'en champ de suivi d'un projet.</td>
        <td>—</td></tr>
    <tr><td><strong>Droits paramétrables par action</strong></td>
        <td>Seul l'accès <em>par module</em> est paramétrable ; les actions sensibles sont gardées
        en dur.</td>
        <td>C'est un choix de séparation des tâches avant d'être une limite. À rediscuter avant de
        le lever.</td></tr>
    <tr><td><strong>Tests automatisés de l'interface</strong></td>
        <td>Inexistants. Le serveur est en revanche couvert par plusieurs centaines de tests.</td>
        <td>Prévoir une recette manuelle des parcours d'écran à chaque livraison.</td></tr>
  </tbody>
</table>`,
        },
        {
            titre: 'Limites structurelles assumées',
            corps: `
<p>Celles-ci ne sont pas des manques à combler : ce sont des contreparties de choix explicites.</p>

<div class="defs">
  <div><dt>Les rappels dépendent du service</dt>
       <dd>L'ordonnanceur vit dans le processus applicatif — un composant de moins à exploiter.
       Contrepartie : service arrêté, aucun rappel ne part. Un rappel manqué de plus d'une semaine
       est consommé sans envoi, pour ne pas déverser d'un coup les alertes du passé.</dd></div>
  <div><dt>Un mot de passe de plus</dt>
       <dd>L'authentification locale évite une dépendance à un annuaire et fonctionne partout.
       Contrepartie : pas de révocation centralisée. Le blocage manuel doit figurer dans votre
       procédure de départ.</dd></div>
  <div><dt>Les modules importés ne s'éditent pas</dt>
       <dd>Incidents et demandes reflètent un système amont qui fait autorité. Contrepartie : on
       ne corrige pas ici une donnée fausse là-bas. Discussion, pièces jointes et annotation
       interne restent possibles.</dd></div>
  <div><dt>La qualité des statistiques dépend de l'import</dt>
       <dd>Un gestionnaire sans compte correspondant, un statut non reconnu, une catégorie
       fantaisiste : le compte rendu d'import les signale, mais il faut le lire. Une chaîne
       d'import qu'on ne surveille pas produit des indicateurs faux <em>sans jamais tomber en
       panne</em> — c'est la défaillance la plus coûteuse, parce qu'elle est silencieuse.</dd></div>
</div>`,
        },
        {
            titre: 'Avant de vous engager auprès d\'un tiers',
            corps: `
<p>Une liste de vérification, à dérouler avant toute présentation ou tout engagement contractuel.</p>

<ol class="etapes">
  <li><b>Vérifier l'état réel des fonctionnalités citées</b>
      Le tableau ci-dessus décrit l'état à la date de ce manuel. Il vieillit ; le code, non.</li>
  <li><b>Nommer les prérequis d'exploitation</b>
      Serveur de messagerie, chiffrement du transport, sauvegardes planifiées, supervision. Sans
      eux, une partie des promesses ne tient pas.</li>
  <li><b>Cadrer le paramétrage initial</b>
      Catégories, cycles de vie, engagements de délai et profils sont des décisions
      d'organisation. Elles prennent du temps et n'appartiennent pas à l'éditeur.</li>
  <li><b>Poser la question de l'identité et du second facteur</b>
      Si l'interlocuteur a une exigence forte sur ce point, elle relève aujourd'hui d'un
      développement. Mieux vaut l'annoncer que de la découvrir en recette.</li>
  <li><b>Prévoir la recette de sécurité</b>
      Le test d'intrusion rejouable se déroule en une commande contre un environnement de
      recette. C'est la preuve la plus convaincante à produire — et elle ne coûte presque rien.</li>
</ol>

<div class="note ok">
  <b>Le principe qui vaut pour tout ce manuel</b>
  <p>Rien n'y est décrit qui n'existe pas dans le produit. C'est ce qui rend utilisable le reste du
  document : quand un manuel promet ce qui n'existe pas, on ne sait plus lesquelles de ses pages
  croire.</p>
</div>`,
        },
    ],
};
