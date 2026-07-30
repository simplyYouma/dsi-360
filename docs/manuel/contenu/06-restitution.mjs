export const chapitre = {
    titre: 'Restituer et exporter',
    intro:
        'Une plateforme de pilotage ne vaut que par ce qu\'elle permet de dire. Ce chapitre '
        + 'recense ce qui se mesure, ce qui s\'exporte, et surtout comment lire ces chiffres '
        + 'sans se tromper — car un indicateur mal compris coûte plus cher que pas '
        + 'd\'indicateur du tout.',
    sections: [
        {
            titre: 'Ce que la plateforme mesure',
            corps: `
<p>Tous les indicateurs se calculent en direct à partir des activités : il n'y a pas de saisie
d'indicateur, donc pas d'écart entre le terrain et le rapport.</p>

<table>
  <thead><tr><th>Famille</th><th>Indicateurs</th></tr></thead>
  <tbody>
    <tr><td><strong>Volumes</strong></td><td>Activités ouvertes, par module, par état, par catégorie,
      par entité, par responsable. Créations et clôtures sur la période.</td></tr>
    <tr><td><strong>Délais</strong></td><td>Respect des engagements — global, par module, par priorité.
      Répartition des dossiers à l'heure, en approche, dépassés. Distribution des délais réels.
      Délai de prise en charge par priorité.</td></tr>
    <tr><td><strong>Flux</strong></td><td>Tendance sur la période, temps passé dans chaque état,
      vieillissement du stock, taux de réouverture.</td></tr>
    <tr><td><strong>Charge</strong></td><td>Volume et délais par gestionnaire, avec une fiche
      individuelle. Répartition entre les niveaux de support.</td></tr>
    <tr><td><strong>Concentration</strong></td><td>Les catégories qui produisent le plus de volume.</td></tr>
    <tr><td><strong>Risques</strong></td><td>Matrice probabilité × impact, telle qu'on la présente en
      comité.</td></tr>
    <tr><td><strong>Patrimoine</strong></td><td>Composition du parc, état constaté, valeur nette après
      amortissement.</td></tr>
    <tr><td><strong>Comparaison</strong></td><td>Matrice mensuelle, pour comparer des périodes plutôt
      que des instants.</td></tr>
  </tbody>
</table>`,
        },
        {
            titre: 'Les formats d\'export',
            corps: `
<table>
  <thead><tr><th>Format</th><th>Produit par</th><th>Disponible sur</th></tr></thead>
  <tbody>
    <tr><td><strong>Tableur</strong> (classeur)</td><td>Le serveur</td>
        <td>Listes d'activités de chaque module, inventaire, journal, discussion d'un dossier.
        En-têtes mis en forme, largeurs de colonnes ajustées.</td></tr>
    <tr><td><strong>CSV</strong></td><td>Le serveur</td>
        <td>Mêmes périmètres. Séparateur point-virgule et marque d'encodage, pour s'ouvrir
        correctement dans un tableur sans manipulation.</td></tr>
    <tr><td><strong>PDF</strong></td><td>Le navigateur</td>
        <td>Tableau de bord et espace personnel : la page telle qu'elle est affichée, avec
        l'identité de la plateforme et un pied de page.</td></tr>
    <tr><td><strong>Image</strong></td><td>Le navigateur</td>
        <td>Un visuel isolé — une carte d'indicateur, un graphique — à coller dans un support.</td></tr>
  </tbody>
</table>

<div class="note attention">
  <b>Le PDF vient du navigateur, pas du serveur</b>
  <p>Il reproduit ce qui est affiché : il dépend donc de la page ouverte et de la période
  sélectionnée. Deux conséquences pratiques — il n'existe pas d'export PDF pour les listes
  d'activités (utilisez le tableur), et un PDF ne peut pas être produit par une tâche
  planifiée.</p>
</div>

<div class="note danger">
  <b>Un export est une extraction de données</b>
  <p>Un classeur exporté sort du périmètre de la plateforme : il perd le cloisonnement, la
  traçabilité et le contrôle d'accès. Traitez-le comme un document sensible, et rappelez-le aux
  utilisateurs qui exportent — c'est par là que fuient la plupart des données, jamais par
  l'application.</p>
</div>`,
        },
        {
            titre: 'Lire les indicateurs sans se tromper',
            corps: `
<p>Quelques pièges qui reviennent systématiquement, et la lecture correcte.</p>

<div class="defs">
  <div><dt>La moyenne cache l'essentiel</dt>
       <dd>Un délai moyen de résolution acceptable peut recouvrir une majorité de dossiers traités
       en une heure et une minorité qui traîne des semaines. Lisez la <strong>distribution</strong>
       et le <strong>vieillissement</strong>, pas la moyenne.</dd></div>
  <div><dt>Un bon taux de respect peut venir d'un mauvais paramétrage</dt>
       <dd>Des engagements trop larges produisent un taux flatteur. Croisez-le toujours avec les
       délais réels : si tout est « à l'heure » et que les demandeurs se plaignent, ce sont les
       cibles qu'il faut revoir, pas les équipes.</dd></div>
  <div><dt>Le volume par gestionnaire n'est pas une évaluation</dt>
       <dd>Il dépend de la nature des dossiers, de leur difficulté et de leur affectation. Utilisé
       comme mesure de performance individuelle, il produit exactement ce qu'on mesure : des
       dossiers découpés pour faire du nombre.</dd></div>
  <div><dt>Le taux de réouverture est le meilleur indicateur de qualité</dt>
       <dd>Il est difficile à truquer et dit ce qu'aucun délai ne dit : le problème avait-il
       vraiment été réglé ? Une baisse des délais accompagnée d'une hausse des réouvertures est
       une dégradation, pas un progrès.</dd></div>
  <div><dt>Les dossiers sans responsable faussent tout</dt>
       <dd>Ils n'apparaissent dans aucune charge individuelle et pèsent pourtant sur les délais
       globaux. Surveillez leur nombre en priorité — souvent, il vient d'un import dont les
       gestionnaires n'ont pas de compte.</dd></div>
</div>

<div class="note ok">
  <b>Trois chiffres suffisent à une revue mensuelle</b>
  <ul>
    <li>Le <strong>stock</strong> : combien de dossiers ouverts, et depuis quand pour les plus vieux.</li>
    <li>Le <strong>respect des engagements</strong>, avec le nombre de dépassements — pas seulement
        le pourcentage.</li>
    <li>La <strong>concentration</strong> : les trois catégories qui font le plus de volume.</li>
  </ul>
  <p>Le reste sert à comprendre <em>pourquoi</em>, une fois qu'on sait <em>quoi</em> regarder.</p>
</div>`,
        },
        {
            titre: 'Préparer une revue de direction',
            corps: `
<ol class="etapes">
  <li><b>Fixer la période</b>
      Le mois écoulé, comparé au précédent. Une période trop courte fait du bruit, une période trop
      longue masque les inflexions.</li>
  <li><b>Partir du tableau de bord</b>
      Il donne l'état du moment et les signaux. Exportez-le en PDF : c'est le support lui-même.</li>
  <li><b>Aller chercher les causes dans les analyses</b>
      Vieillissement, concentration par catégorie, durées par état. Une variation sans explication
      ne se présente pas.</li>
  <li><b>Extraire les cas à décision</b>
      Dépassements, dossiers sans responsable, recommandations en retard, risques critiques. Une
      liste courte, exportée en tableur, chacun avec un nom.</li>
  <li><b>Transformer les décisions en activités</b>
      Une décision de comité qui ne devient pas une activité avec un responsable et une échéance ne
      sera pas exécutée. C'est l'objet du module de gouvernance.</li>
</ol>`,
        },
    ],
};
