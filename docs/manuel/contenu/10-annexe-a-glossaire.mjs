export const chapitre = {
    annexe: true,
    titre: 'Glossaire',
    intro:
        'Les termes qui ont un sens précis dans la plateforme. Un mot du manuel désigne '
        + 'toujours la même chose ; en cas de doute, c\'est ici que la définition fait foi.',
    sections: [
        {
            titre: 'Termes du domaine',
            corps: `
<div class="defs">
  <div><dt>Activité</dt><dd>Toute chose suivie de bout en bout : incident, demande, projet,
    changement, recommandation, risque, sujet de sécurité ou de gouvernance. C'est l'entité pivot
    de la plateforme.</dd></div>
  <div><dt>Référence</dt><dd>Identifiant lisible et unique d'une activité, préfixé par son type et
    daté. C'est ce qu'on cite à l'oral et dans un courriel.</dd></div>
  <div><dt>Type / module</dt><dd>La famille dont relève une activité. Il détermine son cycle de vie,
    ses catégories et ses écrans.</dd></div>
  <div><dt>Demandeur</dt><dd>La personne à l'origine de l'activité. Informée, sans pouvoir de
    décision sur le traitement.</dd></div>
  <div><dt>Responsable principal</dt><dd>La personne — une seule — comptable du résultat et du
    délai.</dd></div>
  <div><dt>Contributeur</dt><dd>Une personne qui exécute une partie du travail.</dd></div>
  <div><dt>Valideur</dt><dd>Une personne dont l'accord conditionne une transition. La liste se fige
    dès la première décision rendue.</dd></div>
  <div><dt>Entité</dt><dd>Le découpage organisationnel — service, direction, site — qui porte le
    cloisonnement.</dd></div>
  <div><dt>Catégorie</dt><dd>Classement paramétrable d'une activité, propre à son type.</dd></div>
  <div><dt>Impact</dt><dd>L'étendue de ce qui est touché.</dd></div>
  <div><dt>Urgence</dt><dd>La vitesse à laquelle la situation se dégrade.</dd></div>
  <div><dt>Priorité</dt><dd>De P1 à P5. Elle n'est pas saisie : elle est <em>dérivée</em> de l'impact
    et de l'urgence par une matrice paramétrable.</dd></div>
  <div><dt>Criticité</dt><dd>Pour un risque : probabilité × impact.</dd></div>
  <div><dt>Engagement de service</dt><dd>La promesse de délai, en deux temps : prise en charge et
    résolution.</dd></div>
  <div><dt>Échéance</dt><dd>La date-limite calculée à partir de l'engagement et de l'heure de
    départ.</dd></div>
  <div><dt>Cycle de vie</dt><dd>La suite d'états d'un type d'activité et les transitions
    autorisées entre eux.</dd></div>
  <div><dt>Transition</dt><dd>Le passage d'un état au suivant. Seules celles prévues sont
    possibles.</dd></div>
  <div><dt>Phase</dt><dd>Le regroupement d'états qui indique si une activité est en cours, en
    attente ou terminée. Une activité en phase terminale ne court plus après son délai.</dd></div>
  <div><dt>Revue périodique</dt><dd>Le rendez-vous de réexamen d'une activité qui ne se « résout »
    pas — un risque, un sujet de gouvernance. Elle déclenche ses propres rappels.</dd></div>
  <div><dt>Niveau de support</dt><dd>Le degré d'expertise qui traite un dossier. Il ne se choisit
    pas : il se déduit du gestionnaire.</dd></div>
</div>`,
        },
        {
            titre: 'Termes d\'administration et de sécurité',
            corps: `
<div class="defs">
  <div><dt>Profil</dt><dd>Un métier, pas une position hiérarchique. Il porte les accès aux modules
    et se crée, se renomme et se supprime.</dd></div>
  <div><dt>Transverse</dt><dd>Se dit d'un profil qui voit toutes les entités. Le profil
    d'administration l'est nécessairement.</dd></div>
  <div><dt>Matrice des accès</dt><dd>Le tableau profil × module qui décide de ce que chaque profil
    voit.</dd></div>
  <div><dt>Capacité</dt><dd>Une action autorisée sur un dossier précis, calculée par le serveur à
    partir du rôle, de l'état et du régime du dossier.</dd></div>
  <div><dt>Régime</dt><dd>Normal, lecture seule (module alimenté par import) ou clos (dossier
    terminé).</dd></div>
  <div><dt>Cloisonnement</dt><dd>La règle qui limite un profil non transverse aux activités de son
    entité. Appliquée au niveau des requêtes, pas de l'affichage.</dd></div>
  <div><dt>Séparation des tâches</dt><dd>Le principe selon lequel organiser un dossier et l'exécuter
    relèvent de personnes distinctes. Il explique pourquoi certaines actions ne sont pas
    paramétrables.</dd></div>
  <div><dt>Journal</dt><dd>Le registre de toutes les actions, en ajout seul et chaîné par empreinte.</dd></div>
  <div><dt>Ajout seul</dt><dd>Propriété d'un registre où l'on n'écrit qu'à la fin : rien ne se
    modifie, rien ne s'efface.</dd></div>
  <div><dt>Chaînage par empreinte</dt><dd>Chaque écriture porte la marque de la précédente, de sorte
    qu'une altération rompe la chaîne et devienne détectable.</dd></div>
  <div><dt>Lien d'activation</dt><dd>Le lien à usage unique, expirable, par lequel un agent définit
    lui-même son mot de passe.</dd></div>
  <div><dt>Escalade</dt><dd>L'alerte déclenchée quand un dossier de priorité maximale n'est pas pris
    en charge dans les temps. Une seule par dossier.</dd></div>
  <div><dt>Palier de rappel</dt><dd>Une fraction du délai consommé — 50 %, 80 %, 100 % — à laquelle
    un rappel est émis, une seule fois par destinataire.</dd></div>
  <div><dt>Ordonnanceur</dt><dd>La boucle interne qui balaie les échéances et déclenche rappels et
    escalades. Elle vit dans le processus applicatif.</dd></div>
  <div><dt>Import</dt><dd>Le dépôt d'un classeur qui alimente un module en lecture seule ou
    l'inventaire. Idempotent : deux dépôts identiques ne créent pas de doublon.</dd></div>
  <div><dt>Idempotent</dt><dd>Se dit d'une opération qu'on peut répéter sans changer le résultat.</dd></div>
</div>`,
        },
    ],
};
