export const chapitre = {
    titre: 'Prise en main',
    intro:
        'De la réception du courriel d\'activation à la lecture d\'une fiche. Ce chapitre '
        + 'suffit à un nouvel arrivant : au bout, il sait se connecter, se repérer, trouver '
        + 'ce qui le concerne et comprendre ce qu\'un écran lui dit.',
    sections: [
        {
            titre: 'Activer son compte',
            corps: `
<p>Un compte est créé par un administrateur, <strong>sans mot de passe</strong>. Vous recevez un
courriel contenant un lien d'activation. Tant que vous ne l'avez pas utilisé, le compte existe
mais ne s'ouvre pas.</p>

<ol class="etapes">
  <li><b>Ouvrez le courriel d'activation</b>
      L'objet commence par le nom de la plateforme. Le lien est valable une heure.</li>
  <li><b>Choisissez votre mot de passe</b>
      Vous seul le connaissez. Aucun administrateur ne peut le lire ; il n'est pas non plus
      transmis par un tiers.</li>
  <li><b>Connectez-vous</b>
      Le lien d'activation est à <strong>usage unique</strong> : une fois consommé, il ne sert plus.</li>
</ol>

<div class="note attention">
  <b>Le lien a expiré ?</b>
  <p>Utilisez « Mot de passe oublié » sur l'écran de connexion, ou demandez à un administrateur de
  relancer l'envoi. Un lien expiré n'est jamais réactivé : un nouveau est émis.</p>
</div>`,
        },
        {
            titre: 'Se connecter',
            corps: `
<p>L'accès se fait avec votre <strong>adresse professionnelle</strong> et votre mot de passe. La
session reste ouverte tant que vous êtes actif ; elle se renouvelle seule en arrière-plan.</p>

<h3>Mot de passe oublié</h3>
<p>Saisissez votre adresse : un lien de réinitialisation vous parvient. La plateforme affiche
<strong>le même message que le compte existe ou non</strong> — c'est délibéré : autrement, cet écran
permettrait de découvrir qui possède un compte.</p>

<h3>Compte temporairement verrouillé</h3>
<p>Après plusieurs échecs consécutifs, le compte se verrouille <strong>quelques minutes</strong>.
Le verrou prime sur le mot de passe : même juste, il est refusé pendant le délai. Là encore c'est
voulu — sinon une réponse différente indiquerait à un attaquant qu'il a trouvé le bon mot de passe.</p>

<div class="note">
  <b>Le verrou est temporaire, jamais définitif</b>
  <p>Un verrou permanent permettrait d'exclure n'importe qui du système en se trompant exprès à sa
  place. Il suffit donc d'attendre. Chaque tentative — réussie, échouée ou bloquée — est
  journalisée.</p>
</div>

<h3>Premier mot de passe imposé</h3>
<p>Si un administrateur a marqué votre compte « à renouveler », la plateforme n'ouvre rien d'autre
que l'écran de changement de mot de passe, tant qu'il n'est pas changé. Ce contrôle est appliqué
<strong>par le serveur</strong>, pas seulement par l'écran.</p>`,
        },
        {
            titre: 'Se repérer dans l\'interface',
            corps: `
<p>L'écran se lit en trois zones, constantes d'un module à l'autre.</p>

<div class="defs">
  <div><dt>Le rail de navigation</dt>
       <dd>À gauche, repliable. Les modules y sont groupés par intention : votre espace, le
       pilotage, les activités, la maîtrise et la conformité, le patrimoine, la gouvernance, le
       système. <strong>Vous ne voyez que les modules auxquels votre profil donne accès</strong> —
       un module absent du rail n'est pas caché, il vous est fermé.</dd></div>
  <div><dt>La barre supérieure</dt>
       <dd>Fil d'Ariane, <strong>recherche globale</strong>, cloche de notifications, votre compte.</dd></div>
  <div><dt>La zone de travail</dt>
       <dd>Liste, fiche ou tableau de bord selon l'écran.</dd></div>
</div>

<h3>La recherche globale</h3>
<p>Elle cherche dans tous les modules auxquels vous avez accès, et <strong>respecte votre
périmètre</strong> : un dossier hors de votre entité n'apparaît pas, même en tapant sa référence
exacte. Une référence (<code>INC-2026-00042</code>) mène directement à la fiche.</p>

<h3>Les notifications</h3>
<p>La cloche rassemble ce qui vous concerne : dossiers qui vous sont confiés, échéances qui
approchent, engagements dépassés, décisions attendues de vous. Vous réglez vous-même, dans vos
préférences, ce qui vous parvient <strong>dans la plateforme</strong> et ce qui vous parvient
<strong>par courriel</strong> — le réglage suit votre compte, pas le navigateur utilisé.</p>

<div class="note">
  <b>Mon espace</b>
  <p>L'entrée « Mes tickets » regroupe, sur un seul écran, ce dont vous êtes responsable, les
  tâches qui vous sont assignées et vos propres indicateurs. C'est le point de départ naturel d'une
  journée — les listes par module servent plutôt à chercher.</p>
</div>`,
        },
        {
            titre: 'Lire une liste d\'activités',
            corps: `
<p>Chaque module présente ses activités dans un tableau homogène. Les colonnes changent, la
grammaire non.</p>

<table>
  <thead><tr><th>Colonne</th><th>Ce qu'elle dit</th></tr></thead>
  <tbody>
    <tr><td><strong>Référence</strong></td><td>Identifiant du dossier. C'est ce qu'on cite.</td></tr>
    <tr><td><strong>Titre</strong></td><td>L'objet, en clair.</td></tr>
    <tr><td><strong>Catégorie</strong></td><td>Classement paramétrable du module.</td></tr>
    <tr><td><strong>Responsable</strong></td><td>La personne comptable du dossier. Vide = non assigné.</td></tr>
    <tr><td><strong>État</strong></td><td>Position dans le cycle de vie, avec un ton : en cours, en attente, terminé.</td></tr>
    <tr><td><strong>Échéance</strong></td><td>Le sablier d'engagement : temps restant, ou retard.</td></tr>
  </tbody>
</table>

<h3>Les filtres</h3>
<p>Au-dessus de chaque liste : l'état, le responsable, les dossiers <strong>non assignés</strong>,
ceux <strong>en retard</strong>, et une recherche libre. Les compteurs par état s'affichent en
bandeau : ils donnent la forme du stock avant même de filtrer.</p>

<h3>Le sablier d'engagement</h3>
<p>Il condense l'essentiel d'un dossier en un symbole :</p>
<p>
  <span class="pastille ok">À l'heure</span>&nbsp;
  <span class="pastille alerte">Échéance proche</span>&nbsp;
  <span class="pastille danger">Dépassé</span>&nbsp;
  <span class="pastille neutre">Sans engagement</span>
</p>
<p>Un dossier arrivé en phase terminale <strong>cesse de courir après son délai</strong> : un dossier
clos n'est jamais « en retard ».</p>`,
        },
        {
            titre: 'Lire une fiche',
            corps: `
<p>La fiche est l'écran où l'on travaille. Sa structure est la même partout.</p>

<ol class="etapes">
  <li><b>L'en-tête</b>
      Référence, titre, état, priorité, engagement. Les actions possibles y figurent — et
      <strong>seulement celles que vous pouvez réellement faire</strong> : la plateforme calcule vos
      capacités sur ce dossier précis et n'affiche pas de bouton qui échouerait.</li>
  <li><b>Les responsabilités</b>
      Demandeur, responsable, contributeurs, valideurs. Chaque désignation est journalisée.</li>
  <li><b>Le corps du dossier</b>
      Description, tâches, jalons, documents, liens utiles — selon le module.</li>
  <li><b>La discussion interne</b>
      Fil d'échanges de l'équipe, avec mentions, images et accusés de lecture. Elle reste
      <strong>interne</strong> : le demandeur n'y a pas accès.</li>
  <li><b>L'historique</b>
      Le parcours des états, puis le journal détaillé : qui a changé quoi, quand, depuis quelle
      valeur.</li>
</ol>

<div class="note">
  <b>Un bouton absent n'est pas un bouton caché</b>
  <p>Si une action ne s'affiche pas, c'est que votre rôle sur ce dossier ne l'autorise pas — ou que
  l'état courant ne la permet pas. Le serveur applique la même règle : contourner l'écran ne donne
  rien.</p>
</div>`,
        },
        {
            titre: 'Faire avancer un dossier',
            corps: `
<p>Les gestes du quotidien, et qui peut les faire.</p>

<table>
  <thead><tr><th>Geste</th><th>Qui</th><th>Effet</th></tr></thead>
  <tbody>
    <tr><td><strong>Assigner un responsable</strong></td><td>Administrateur du module</td>
        <td>Confie le dossier. Seul un compte actif ayant accès au module est désignable.</td></tr>
    <tr><td><strong>Évaluer</strong> (impact, urgence)</td><td>Administrateur du module</td>
        <td>Recalcule la priorité et, avec elle, les échéances d'engagement.</td></tr>
    <tr><td><strong>Ajouter des contributeurs</strong></td><td>Administrateur du module</td>
        <td>Ouvre le dossier à d'autres intervenants.</td></tr>
    <tr><td><strong>Désigner des valideurs</strong></td><td>Administrateur du module</td>
        <td>Conditionne certaines transitions à leur accord. <strong>La liste se fige dès la première
        décision rendue</strong> — sinon on pourrait changer le jury en cours de vote.</td></tr>
    <tr><td><strong>Changer d'état</strong></td><td>Responsable, contributeurs</td>
        <td>Seules les transitions prévues sont proposées. Une transition interdite est refusée et
        expliquée.</td></tr>
    <tr><td><strong>Décider</strong> (approuver / rejeter)</td><td>Valideurs désignés</td>
        <td>Débloque ou arrête la transition soumise à validation.</td></tr>
    <tr><td><strong>Tâches, documents, liens, notes</strong></td><td>Responsable, contributeurs</td>
        <td>Constituent le dossier. L'assigné d'une tâche n'en change que le statut.</td></tr>
  </tbody>
</table>

<div class="note attention">
  <b>Séparation des tâches</b>
  <p>Organiser un dossier et l'exécuter sont deux choses distinctes. Un administrateur de module
  distribue le travail et arbitre ; un acteur exécute. Cette frontière n'est pas paramétrable : elle
  est tenue par le serveur, précisément parce qu'elle protège la valeur des indicateurs et des
  validations.</p>
</div>`,
        },
    ],
};
