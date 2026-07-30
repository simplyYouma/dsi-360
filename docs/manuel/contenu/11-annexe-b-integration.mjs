export const chapitre = {
    annexe: true,
    titre: 'Intégration',
    intro:
        'Pour les équipes qui interrogent la plateforme depuis un autre système. Les '
        + 'conventions de l\'interface de programmation, le format des erreurs, et ce sur '
        + 'quoi il est prudent de s\'appuyer.',
    sections: [
        {
            titre: 'Conventions',
            corps: `
<div class="defs">
  <div><dt>Base et version</dt><dd>Toutes les routes vivent sous un préfixe versionné. La version
    ne change pas sans rupture assumée : un client existant continue de fonctionner.</dd></div>
  <div><dt>Format</dt><dd>JSON en UTF-8, noms de champs en minuscules avec tirets bas, dates au
    format international en temps universel.</dd></div>
  <div><dt>Authentification</dt><dd>Un jeton porteur sur chaque appel, sauf les points de santé et
    la connexion.</dd></div>
  <div><dt>Documentation vivante</dt><dd>Le service publie sa propre description exhaustive et
    interrogeable. <strong>C'est elle qui fait foi</strong> : elle est générée depuis le code, donc
    toujours à jour, là où un document rédigé finit par mentir.</dd></div>
</div>

<h3>Listes</h3>
<p>Les lectures de liste sont paginées et renvoient une enveloppe qui porte, avec les éléments, le
total, la page et la taille demandées. Filtres et recherche libre passent en paramètres.</p>

<pre><code>{
  "elements": [ … ],
  "total": 128,
  "page": 1,
  "taille": 15
}</code></pre>`,
        },
        {
            titre: 'Erreurs',
            corps: `
<p>Toutes les erreurs partagent un corps unique, porteur d'un <strong>identifiant de
corrélation</strong>. Cet identifiant se retrouve dans les journaux du serveur : c'est ce qu'un
utilisateur doit communiquer au support, plutôt que de décrire l'écran.</p>

<pre><code>{
  "erreur": {
    "code": "REGLE_METIER",
    "message": "La clôture requiert la validation des valideurs désignés.",
    "details": [ … ],
    "correlation_id": "c1a2b3d4"
  }
}</code></pre>

<table>
  <thead><tr><th>Statut</th><th>Code</th><th>Signification</th></tr></thead>
  <tbody>
    <tr><td class="num">400</td><td><code>VALIDATION</code></td><td>Entrée invalide au regard du schéma attendu.</td></tr>
    <tr><td class="num">401</td><td><code>NON_AUTHENTIFIE</code></td><td>Jeton absent, expiré ou invalide.</td></tr>
    <tr><td class="num">403</td><td><code>NON_AUTORISE</code></td><td>Profil ou rôle insuffisant pour cette action.</td></tr>
    <tr><td class="num">404</td><td><code>INTROUVABLE</code></td><td>Ressource inexistante <strong>ou hors de votre périmètre</strong>.</td></tr>
    <tr><td class="num">409</td><td><code>CONFLIT</code></td><td>Transition d'état interdite, ou doublon.</td></tr>
    <tr><td class="num">422</td><td><code>REGLE_METIER</code></td><td>Règle du domaine violée — par exemple une clôture sans validation.</td></tr>
    <tr><td class="num">429</td><td>—</td><td>Trop de tentatives de connexion : le compte est temporairement verrouillé.</td></tr>
    <tr><td class="num">500</td><td><code>ERREUR_INTERNE</code></td><td>Inattendu. Journalisé avec son identifiant de corrélation.</td></tr>
    <tr><td class="num">503</td><td>—</td><td>Base de données injoignable. Le service se rétablit seul à son retour.</td></tr>
  </tbody>
</table>

<div class="note">
  <b>404 plutôt que 403 hors périmètre</b>
  <p>Un client qui interroge un dossier hors de son périmètre reçoit « introuvable ». Ne traitez
  donc pas un 404 comme la preuve qu'une ressource n'existe pas : c'est peut-être qu'elle ne vous
  regarde pas.</p>
</div>`,
        },
        {
            titre: 'Points d\'entrée notables',
            corps: `
<table>
  <thead><tr><th>Famille</th><th>Ce qu'on y trouve</th></tr></thead>
  <tbody>
    <tr><td><strong>Santé</strong></td><td>Vivacité du processus et disponibilité réelle du service,
      hors authentification. À brancher sur la supervision.</td></tr>
    <tr><td><strong>Session</strong></td><td>Connexion, renouvellement, déconnexion, changement et
      réinitialisation de mot de passe.</td></tr>
    <tr><td><strong>Profil courant</strong></td><td>Identité, accès effectifs et périmètre de
      l'appelant. C'est le point d'entrée d'un client qui veut savoir ce qu'il a le droit
      d'afficher.</td></tr>
    <tr><td><strong>Référentiels</strong></td><td>Catégories, états et cycles de vie, agents
      désignables, engagements effectifs d'un module. À interroger plutôt qu'à recopier.</td></tr>
    <tr><td><strong>Modules d'activités</strong></td><td>Liste filtrable, compteurs, détail, transitions,
      assignation, évaluation, acteurs, décisions, tâches, documents, liens, notes, export.</td></tr>
    <tr><td><strong>Tableau de bord et analyses</strong></td><td>Indicateurs agrégés sur une période.</td></tr>
    <tr><td><strong>Recherche</strong></td><td>Recherche globale, cloisonnée par accès et périmètre.</td></tr>
    <tr><td><strong>Notifications</strong></td><td>Consultation, marquage comme lu, préférences.</td></tr>
    <tr><td><strong>Import</strong></td><td>Dépôt d'un classeur et état du dernier dépôt de chaque
      nature.</td></tr>
    <tr><td><strong>Administration</strong></td><td>Comptes, profils, matrice des accès, catégories,
      engagements de service, journal et son export.</td></tr>
  </tbody>
</table>

<div class="note attention">
  <b>Deux règles pour un client durable</b>
  <ul>
    <li><strong>Lisez les référentiels, ne les recopiez pas.</strong> Catégories, états et
        engagements changent par paramétrage : un client qui les code en dur casse au premier
        réglage.</li>
    <li><strong>Fiez-vous aux capacités renvoyées avec un dossier</strong> plutôt que de
        réimplémenter les règles de droits. Elles sont calculées par le serveur, qui reste seul
        juge.</li>
  </ul>
</div>`,
        },
    ],
};
