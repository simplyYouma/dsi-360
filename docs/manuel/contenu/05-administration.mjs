export const chapitre = {
    titre: 'Administration',
    intro:
        'Ce chapitre s\'adresse aux administrateurs fonctionnels. Il couvre les comptes, les '
        + 'droits, les référentiels, les engagements de service, l\'import quotidien, les '
        + 'notifications et le journal. C\'est ici que la plateforme se règle sur votre '
        + 'organisation — sans développement.',
    sections: [
        {
            titre: 'Les comptes',
            corps: `
<p>Un compte porte une adresse professionnelle, un profil, une entité de rattachement, un niveau
de support et, éventuellement, une date d'expiration.</p>

<ol class="etapes">
  <li><b>Créer le compte</b>
      Sans mot de passe : un lien d'activation part par courriel. Le domaine de l'adresse est
      contrôlé — les adresses hors des domaines autorisés sont refusées.</li>
  <li><b>Choisir le profil</b>
      Il détermine les modules accessibles. Un profil nouvellement créé n'ouvre <strong>aucun</strong>
      module tant qu'on ne lui en donne pas.</li>
  <li><b>Rattacher à une entité</b>
      C'est ce rattachement qui porte le cloisonnement, pour les profils non transverses.</li>
  <li><b>Fixer le niveau de support</b>
      Obligatoire, sauf pour un administrateur qui ne traite pas de dossiers. Le niveau d'un
      dossier se déduit de son gestionnaire — sans niveau sur le compte, la répartition de charge
      devient fausse.</li>
</ol>

<h3>Fermer un accès</h3>
<p>Deux leviers, à effet <strong>immédiat</strong> : rendre le compte inactif, ou lui donner une date
d'expiration. L'un comme l'autre sont vérifiés <strong>à chaque requête</strong> : une session en
cours ne survit pas au blocage.</p>

<div class="note attention">
  <b>Ne supprimez pas un compte pour fermer un accès</b>
  <p>Désactivez-le. L'historique doit rester lisible : les actions passées portent l'adresse de leur
  auteur, figée à l'écriture, et un dossier doit pouvoir citer qui l'a traité même des années plus
  tard.</p>
</div>

<div class="note danger">
  <b>Le dernier administrateur</b>
  <p>La plateforme refuse de retirer le dernier accès d'administration — sinon plus personne ne
  pourrait la paramétrer, y compris pour se redonner le droit. Ce garde-fou n'est pas
  contournable depuis l'interface.</p>
</div>`,
        },
        {
            titre: 'Profils et droits',
            corps: `
<p>Un <strong>profil</strong> décrit un métier, pas une position hiérarchique. Il se crée, se
renomme et se supprime.</p>

<table>
  <thead><tr><th>Règle</th><th>Pourquoi</th></tr></thead>
  <tbody>
    <tr><td>Un profil porté par des comptes ne se supprime pas</td>
        <td>Sinon ces comptes se retrouveraient sans droits, du jour au lendemain, sans que
        personne l'ait décidé pour eux.</td></tr>
    <tr><td>Le profil d'administration ne se supprime pas et reste transverse</td>
        <td>C'est la clé de la maison : elle ne se jette pas depuis l'intérieur.</td></tr>
    <tr><td>Un profil créé n'ouvre rien</td>
        <td>Sécurité par défaut. On ouvre ce dont on a besoin, on n'ôte pas ce dont on n'a pas
        besoin.</td></tr>
  </tbody>
</table>

<h3>La matrice des accès</h3>
<p>Un tableau croisé <strong>profil × module</strong> : cocher une case ouvre le module au profil.
La modification prend effet immédiatement, sans redémarrage.</p>

<div class="note attention">
  <b>Deux niveaux de droits, à ne pas confondre</b>
  <p><strong>1. L'accès au module</strong> — paramétrable, c'est la matrice ci-dessus. Elle décide de
  ce qu'un profil voit dans le rail de navigation.</p>
  <p><strong>2. Le rôle sur un dossier</strong> — non paramétrable. Sur une activité donnée, on est
  administrateur du module, acteur (responsable ou contributeur) ou valideur, et ce rôle décide de
  ce qu'on peut y faire. Les actions sensibles — valider, clôturer, paramétrer, gérer les comptes —
  restent gardées en dur, par séparation des tâches.</p>
  <p>Autrement dit : ouvrir un module à un profil ne donne pas le droit de tout y faire.</p>
</div>

<h3>Capacités calculées</h3>
<p>Sur chaque dossier, le serveur calcule vos capacités et les renvoie avec la fiche. L'interface
s'y conforme, ce qui explique qu'un même écran n'offre pas les mêmes boutons à deux personnes.</p>

<div class="defs">
  <div><dt>Assigner</dt><dd>Confier le dossier à un gestionnaire.</dd></div>
  <div><dt>Évaluer</dt><dd>Fixer impact et urgence, donc la priorité et les échéances.</dd></div>
  <div><dt>Gérer les acteurs</dt><dd>Désigner contributeurs et valideurs.</dd></div>
  <div><dt>Travailler</dt><dd>Faire avancer l'état, gérer tâches, documents et liens.</dd></div>
  <div><dt>Décider</dt><dd>Approuver ou rejeter, en tant que valideur désigné.</dd></div>
  <div><dt>Compléter le dossier</dt><dd>Enrichir sans changer d'état.</dd></div>
  <div><dt>Annoter</dt><dd>Ajouter une note interne sur un dossier importé.</dd></div>
</div>

<p>Trois régimes se superposent à ces capacités : le régime <strong>normal</strong>, le régime
<strong>lecture seule</strong> (modules alimentés par import) et le régime <strong>clos</strong>
(dossier terminé, plus rien ne bouge).</p>`,
        },
        {
            titre: 'Catégories et référentiels',
            corps: `
<p>Les catégories classent les activités d'un module. Elles servent aux statistiques, aux filtres
et, souvent, au calcul des engagements. On les ajoute et on les retire librement.</p>

<div class="note">
  <b>Combien de catégories ?</b>
  <p>Assez pour distinguer ce qui appelle des traitements différents, pas plus. Une nomenclature à
  quarante entrées n'est jamais renseignée correctement : au bout de trois mois, tout est classé
  dans « autres » et les statistiques ne valent rien. Commencez court ; une catégorie s'ajoute en
  dix secondes le jour où le besoin est démontré.</p>
</div>

<p>Sont également paramétrables depuis l'administration ou les écrans concernés : les
<strong>entités</strong>, les <strong>types de projet</strong> et leurs jalons types, les
<strong>emplacements</strong>, <strong>départements</strong> et <strong>types d'équipement</strong> de
l'inventaire, et les <strong>demandeurs</strong>.</p>`,
        },
        {
            titre: 'Les engagements de service',
            corps: `
<p>L'onglet dédié présente, pour chaque module concerné, une grille <strong>priorité →
(prise en charge, résolution)</strong>, exprimée en minutes et éditable.</p>

<table>
  <thead><tr><th>Module</th><th>Engagements de délai</th><th>Ce qui pilote les rappels</th></tr></thead>
  <tbody>
    <tr><td>Incidents, demandes, changements, cybersécurité, gouvernance, audit</td>
        <td><span class="pastille ok">Oui</span></td><td>Les échéances d'engagement</td></tr>
    <tr><td>Projets</td><td><span class="pastille neutre">Non</span></td>
        <td>La date de fin et les jalons</td></tr>
    <tr><td>Risques</td><td><span class="pastille neutre">Non</span></td>
        <td>La revue périodique</td></tr>
  </tbody>
</table>

<h3>Quand les échéances sont posées</h3>
<p>À la création du dossier, à la ré-évaluation de l'impact ou de l'urgence, et à l'import. Sans
priorité ni date de départ, <strong>aucune échéance n'est inventée</strong> : mieux vaut un dossier
sans engagement qu'un engagement faux.</p>

<h3>Les rappels</h3>
<p>Un ordonnanceur interne balaie régulièrement les dossiers et déclenche des rappels à
<strong>trois paliers du délai consommé — 50 %, 80 % et 100 %</strong>.</p>

<div class="note">
  <b>Pourquoi des paliers proportionnels et non des durées fixes</b>
  <p>Les engagements vont de quinze minutes à plusieurs jours. Un rappel « deux heures avant
  l'échéance » arriverait après coup sur un incident critique et beaucoup trop tôt sur une
  recommandation. Un pourcentage du délai vaut pour les deux.</p>
</div>

<p>Les échéances de <strong>tâches</strong>, de <strong>jalons</strong>, de <strong>projets</strong>
et de <strong>revues</strong> ont leurs propres paliers, en jours. Chaque palier n'est notifié
qu'une fois par destinataire. Un rappel manqué de plus d'une semaine — parce que la plateforme
était arrêtée — est consommé <strong>sans envoi</strong> : personne n'a besoin de recevoir d'un coup
les alertes de la semaine passée.</p>

<h3>L'escalade</h3>
<p>Un dossier de priorité maximale non pris en charge dans les temps déclenche une
<strong>escalade</strong> : notification et courriel au gestionnaire — ou à un administrateur s'il
n'y en a pas — et inscription au journal. Une seule fois par dossier : une escalade répétée
devient un bruit qu'on filtre.</p>

<div class="note attention">
  <b>Rappels et ordonnanceur</b>
  <p>Les rappels sont produits par l'application elle-même. Si le service est arrêté, aucun rappel
  ne part pendant l'arrêt. C'est le prix d'une architecture sans dépendance externe — la
  contrepartie est qu'il n'y a rien d'autre à exploiter et à superviser.</p>
</div>`,
        },
        {
            titre: 'L\'import quotidien',
            corps: `
<p>Les incidents et les demandes proviennent de l'outil de service desk. Un classeur est déposé
sur l'écran d'import ; la plateforme le lit, le rapproche de l'existant et met l'état à jour.</p>

<h3>Le fichier attendu</h3>
<div class="defs">
  <div><dt>Format</dt><dd>Classeur <code>.xlsx</code>, jusqu'à 20 Mo.</dd></div>
  <div><dt>En-têtes</dt><dd>La ligne d'en-têtes est <strong>détectée</strong> — un préambule de
    filtres au-dessus du tableau ne gêne pas. Les colonnes sont reconnues <strong>par leur
    intitulé</strong>, jamais par leur position : une colonne déplacée ou insérée ne casse rien.</dd></div>
  <div><dt>Colonnes indispensables</dt><dd>Type d'enregistrement, statut, numéro, titre, priorité et
    date de la demande. À défaut, l'import est refusé et <strong>énumère ce qui manque</strong>.</dd></div>
  <div><dt>Colonnes exploitées en plus</dt><dd>Catégorie, sous-catégorie, demandeur, gestionnaire,
    date de fermeture, délais de prise en charge et de réparation.</dd></div>
</div>

<h3>Les règles</h3>
<ul>
  <li><strong>Idempotent</strong> : déposer deux fois le même fichier ne crée pas de doublon. Le
      rapprochement se fait sur le numéro d'origine ; une ligne inchangée est comptée comme telle.</li>
  <li><strong>Le fichier fait autorité</strong> sur le titre, la catégorie, le demandeur, le
      gestionnaire, la priorité, le statut et les dates.</li>
  <li><strong>Le fichier ne touche jamais</strong> la discussion interne, les contributeurs, les
      documents ni l'annotation de l'équipe. Ce que vous produisez vous appartient.</li>
  <li><strong>Aucun compte n'est créé.</strong> Le gestionnaire est rapproché d'un compte existant
      par son nom. Sans correspondance, le dossier n'a pas de responsable interne.</li>
  <li>Les <strong>demandeurs</strong> et les <strong>catégories</strong> inconnus sont créés à la
      volée, sans doublon d'orthographe.</li>
  <li>Un <strong>statut non reconnu</strong> n'interrompt pas l'import : le dossier est rangé en
      « ouvert » et le libellé est <strong>remonté dans le compte rendu</strong>, pour que vous
      complétiez la table de correspondance.</li>
</ul>

<div class="note ok">
  <b>Après chaque dépôt, lisez le compte rendu</b>
  <p>Il indique le nombre de dossiers créés, mis à jour et inchangés, ainsi que les anomalies :
  statuts inconnus, gestionnaires sans compte, lignes ignorées. C'est le meilleur indicateur de
  santé de la chaîne — un import qui « passe » en signalant trente gestionnaires inconnus ne
  produit pas des statistiques exploitables.</p>
</div>

<p>L'écran conserve la trace du <strong>dernier dépôt de chaque nature</strong>. Un dépôt unique
accepte indifféremment un classeur de tickets ou d'équipements : la nature est reconnue à ses
en-têtes, et en cas d'échec la plateforme affiche les intitulés qu'elle a lus — de quoi corriger
le fichier sans deviner.</p>`,
        },
        {
            titre: 'Notifications',
            corps: `
<p>Deux canaux fonctionnent : <strong>dans la plateforme</strong> et <strong>par courriel</strong>.
Chaque agent règle ses préférences depuis son compte ; le réglage le suit d'un poste à l'autre.</p>

<table>
  <thead><tr><th>Occasion</th><th>Destinataires</th></tr></thead>
  <tbody>
    <tr><td>Dossier assigné</td><td>Le nouveau responsable</td></tr>
    <tr><td>Désignation comme contributeur ou valideur</td><td>La personne désignée</td></tr>
    <tr><td>Décision attendue</td><td>Les valideurs</td></tr>
    <tr><td>Échéance approchée, puis dépassée</td><td>Responsable et contributeurs</td></tr>
    <tr><td>Escalade</td><td>Gestionnaire, ou administrateur à défaut</td></tr>
    <tr><td>Activité sur un dossier</td><td>Les acteurs, sauf l'auteur de l'action</td></tr>
  </tbody>
</table>

<p>Les courriels portent l'identité de la plateforme et un <strong>lien direct vers le dossier</strong>
concerné. L'envoi est asynchrone, réessayé, et protégé par un <strong>disjoncteur</strong> : une
panne du serveur de messagerie n'interrompt jamais une action ni ne ralentit l'application.</p>

<div class="note attention">
  <b>Deux interrupteurs avant que les courriels partent</b>
  <p>Hors production, <strong>rien n'est envoyé</strong> : les courriels sont seulement journalisés,
  pour éviter d'inonder de vraies boîtes depuis un environnement de test. Et même en production,
  les notifications métier sont <strong>désactivées par défaut</strong> : il faut les activer
  explicitement une fois le serveur de messagerie configuré. C'est délibéré — une plateforme qui
  se met à écrire à toute l'organisation le jour de sa mise en service laisse un mauvais
  souvenir.</p>
</div>

<div class="note">
  <b>Messagerie d'équipe et messagerie instantanée</b>
  <p>Les préférences prévoient ces canaux, mais <strong>aucun envoi n'est implémenté</strong> à ce
  jour. Ne les annoncez pas comme disponibles.</p>
</div>`,
        },
        {
            titre: 'Le journal',
            corps: `
<p>L'onglet Journal donne accès à la totalité des écritures : auteur, horodatage, module, action,
cible, ancienne et nouvelle valeur, adresse réseau. Il se filtre et s'exporte.</p>

<div class="note ok">
  <b>Un journal qu'on ne peut pas réécrire</b>
  <p>La base elle-même refuse toute modification et toute suppression d'une écriture — ce n'est pas
  une règle applicative que l'on pourrait contourner. Chaque entrée porte de plus l'empreinte de la
  précédente : la moindre altération rompt la chaîne et devient détectable, y compris par quelqu'un
  qui aurait un accès direct à la base.</p>
</div>

<p>À quoi cela sert, concrètement :</p>
<ul>
  <li>répondre à une demande de preuve sans rien reconstituer ;</li>
  <li>retrouver qui a modifié une échéance, quand, et depuis quelle valeur ;</li>
  <li>vérifier qu'un import s'est déroulé et ce qu'il a produit ;</li>
  <li>distinguer une erreur de saisie d'un contournement volontaire.</li>
</ul>

<div class="note attention">
  <b>Rétention</b>
  <p>Le journal ne s'élague pas tout seul. Décidez d'une durée de conservation et d'une politique
  d'archivage avec votre responsable de la sécurité, et adossez-la aux sauvegardes de la base
  (cf. chapitre Exploitation).</p>
</div>`,
        },
    ],
};
