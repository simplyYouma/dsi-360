export const chapitre = {
    titre: 'Sécurité',
    intro:
        'Ce que la plateforme protège, comment, et ce qu\'elle ne protège pas. Chaque '
        + 'mécanisme est décrit avec sa raison d\'être : une mesure de sécurité qu\'on ne '
        + 'comprend pas finit toujours par être désactivée « le temps d\'un test ».',
    sections: [
        {
            titre: 'Authentification',
            corps: `
<p>La plateforme gère ses propres identifiants. L'annuaire de l'organisation n'est pas la source
d'identité : c'est une décision assumée, pas un manque.</p>

<div class="defs">
  <div><dt>Mot de passe</dt><dd>Défini par l'agent lui-même via un lien d'activation à usage
    unique. Stocké sous forme d'empreinte <strong>argon2</strong> — irréversible. Aucun
    administrateur ne peut le lire, et il n'est jamais transmis par un tiers.</dd></div>
  <div><dt>Session</dt><dd>Jeton d'accès de courte durée, renouvelé automatiquement. Se déconnecter
    revient à oublier les jetons côté poste.</dd></div>
  <div><dt>Révocation immédiate</dt><dd>L'état actif et la date d'expiration du compte sont
    vérifiés <strong>à chaque requête</strong> : un jeton encore valide ne survit pas au blocage du
    compte.</dd></div>
  <div><dt>Anti-énumération</dt><dd>« Mot de passe oublié » répond la même chose que le compte
    existe ou non, et une adresse inconnue n'écrit rien en base.</dd></div>
  <div><dt>Frein anti-force brute</dt><dd>Après plusieurs échecs, verrou temporaire. Le verrou prime
    sur le mot de passe, y compris s'il est correct — sinon la différence de réponse trahirait la
    réussite.</dd></div>
</div>

<div class="note attention">
  <b>Limites assumées, à connaître avant de vous engager</b>
  <ul>
    <li><strong>Pas de second facteur</strong> aujourd'hui. C'est le principal écart ; il est
        identifié et le renforcement prévu vise en priorité les comptes d'administration, qui
        créent les comptes et lisent le journal.</li>
    <li><strong>Pas de révocation centralisée</strong> au départ d'un collaborateur : c'est un mot
        de passe de plus, hors du référentiel de l'organisation. Le blocage et l'expiration de
        compte sont les leviers, et ils sont <em>manuels</em>. Inscrivez-les à votre procédure de
        sortie.</li>
  </ul>
</div>`,
        },
        {
            titre: 'Autorisation',
            corps: `
<p>Trois barrières indépendantes, toutes vérifiées <strong>côté serveur</strong>.</p>

<ol class="etapes">
  <li><b>L'accès au module</b>
      Matrice profil × module, paramétrable. Sans accès, l'appel est refusé — que l'écran ait ou
      non affiché quelque chose.</li>
  <li><b>Le rôle sur le dossier</b>
      Administrateur du module, acteur ou valideur. Non paramétrable : c'est ce qui garantit la
      séparation entre organiser et exécuter.</li>
  <li><b>Le périmètre</b>
      Un profil non transverse ne voit que son entité. Un dossier hors périmètre répond
      <strong>« introuvable »</strong>, jamais « interdit ».</li>
</ol>

<div class="note">
  <b>Pourquoi « introuvable » plutôt qu'« interdit »</b>
  <p>Répondre « accès refusé » confirmerait l'existence du dossier — donc son numéro, donc son
  ordre de grandeur, donc le volume traité par une autre entité. Une réponse « introuvable » ne
  révèle rien.</p>
</div>

<h3>Règles complémentaires</h3>
<ul>
  <li>On ne désigne qu'un compte <strong>actif</strong> dont le profil a accès au module — impossible
      de confier un dossier à quelqu'un qui ne pourra pas l'ouvrir.</li>
  <li>La liste des valideurs se <strong>fige à la première décision</strong>.</li>
  <li>L'assigné d'une tâche n'en modifie que le <strong>statut</strong>, pas l'intitulé ni
      l'échéance.</li>
  <li>Un dossier <strong>clos</strong> n'accepte plus d'écriture.</li>
</ul>`,
        },
        {
            titre: 'Le journal inviolable',
            corps: `
<p>Le journal est protégé à deux niveaux, dont l'un échappe à l'application elle-même.</p>

<table>
  <thead><tr><th>Protection</th><th>Effet</th></tr></thead>
  <tbody>
    <tr><td><strong>Ajout seul, imposé par la base</strong></td>
        <td>La base refuse toute modification et toute suppression d'écriture. Ce n'est pas une
        règle applicative : même un accès direct à la base ne permet pas de réécrire une ligne par
        les voies normales.</td></tr>
    <tr><td><strong>Chaînage par empreinte</strong></td>
        <td>Chaque écriture porte l'empreinte de la précédente. Supprimer ou altérer une entrée
        rompt la chaîne, et la rupture se voit.</td></tr>
    <tr><td><strong>Auteur figé</strong></td>
        <td>L'adresse de l'auteur est écrite dans l'entrée, et non référencée. L'histoire reste
        lisible après la suppression du compte.</td></tr>
    <tr><td><strong>Adresse réseau captée automatiquement</strong></td>
        <td>Aucun appel n'a à la fournir — donc aucun ne peut la falsifier.</td></tr>
  </tbody>
</table>`,
        },
        {
            titre: 'Durcissement',
            corps: `
<ul>
  <li><strong>En-têtes de sécurité</strong> posés sur chaque réponse, et politique stricte sur les
      ressources que la page a le droit de charger.</li>
  <li><strong>Validation stricte des entrées</strong> : tout ce qui arrive est décrit par un schéma
      et refusé s'il n'y correspond pas.</li>
  <li><strong>Requêtes paramétrées</strong> : aucune donnée d'utilisateur n'est concaténée dans une
      requête.</li>
  <li><strong>Pièces jointes bornées</strong> en taille et contrôlées en type.</li>
  <li><strong>Secrets hors du dépôt</strong>, dans un fichier de configuration non versionné.
      <strong>L'application refuse de démarrer hors développement avec un secret d'usine</strong> —
      la négligence la plus courante est ainsi rendue impossible plutôt que déconseillée.</li>
  <li><strong>Chiffrement du transport</strong> assuré par le serveur frontal (cf. Exploitation).</li>
</ul>`,
        },
        {
            titre: 'Résilience',
            corps: `
<p>Une plateforme de pilotage doit rester consultable quand l'infrastructure vacille — c'est
souvent à ce moment qu'on en a besoin.</p>

<div class="defs">
  <div><dt>Base redémarrée</dt><dd>Les connexions mortes sont détectées et renouvelées ; l'application
    se rétablit seule dès que la base revient.</dd></div>
  <div><dt>Requête qui pend</dt><dd>Des délais bornent la connexion et l'exécution. Sans eux, les
    connexions s'accumulent jusqu'à faire tomber l'application <em>avec</em> la base.</dd></div>
  <div><dt>Base injoignable</dt><dd>Réponse propre « service indisponible », jamais une erreur
    interne qui divulgue des détails techniques.</dd></div>
  <div><dt>Migration en échec</dt><dd>Journalisée, elle ne bloque pas le démarrage.</dd></div>
  <div><dt>Balayage d'échéances en échec</dt><dd>Isolé : un incident ne tue jamais la boucle.</dd></div>
  <div><dt>Messagerie en panne</dt><dd>Disjoncteur : les envois cessent le temps de la panne, sans
    jamais interrompre l'action de l'utilisateur.</dd></div>
  <div><dt>Serveur injoignable</dt><dd>Le poste client affiche un message compréhensible, pas une
    erreur technique brute.</dd></div>
</div>`,
        },
        {
            titre: 'Vérification continue',
            corps: `
<p>La sécurité se vérifie, elle ne se déclare pas.</p>

<div class="cartes">
  <div class="carte"><b>Tests automatisés</b><span>Plusieurs centaines de tests couvrent
    l'authentification, le frein anti-force brute, les droits, le cloisonnement, la lecture seule
    des modules importés, les gardes d'action et le caractère inviolable du journal.</span></div>
  <div class="carte"><b>Test d'intrusion rejouable</b><span>Un scénario automatisé où un compte à
    faible privilège tente de franchir une vingtaine de gardes : élévation de privilège,
    usurpation d'identité, écriture sur un dossier en lecture seule, auto-désignation, injection,
    fuite d'information. Chaque tentative doit échouer ; le script s'arrête à la première
    faille.</span></div>
</div>

<div class="note ok">
  <b>À dérouler avant chaque mise en production</b>
  <p>Le test d'intrusion se lance contre un environnement de recette, en une commande. C'est le
  moyen le plus économique de vérifier qu'une évolution n'a pas ouvert une porte — et la preuve la
  plus convaincante à présenter à un responsable de la sécurité.</p>
</div>

<div class="note attention">
  <b>Ce qui n'est pas couvert</b>
  <p>Les tests automatisés portent sur le serveur. <strong>Il n'y a pas de tests automatisés de
  l'interface</strong> à ce jour : les parcours d'écran se vérifient à la main. Tenez-en compte dans
  votre plan de recette.</p>
</div>`,
        },
    ],
};
