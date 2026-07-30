/**
 * DOSSIER DE PRÉSENTATION — la plateforme de pilotage et de gouvernance.
 *
 * RÈGLE DE RÉDACTION, à tenir à chaque modification :
 *
 * 1. Aucun métier, aucun secteur, aucune entreprise n'est nommé. On dit
 *    « une organisation », « une direction », « une entité », « des
 *    activités ». Ce dossier doit pouvoir être remis à un service qualité,
 *    à une direction des opérations ou à un cabinet d'audit sans qu'une
 *    seule phrase sonne comme si elle avait été écrite pour un autre.
 *
 * 2. On vend le RÉSULTAT, pas la fonctionnalité. Chaque page part d'une
 *    scène que le lecteur reconnaît, puis montre ce que la plateforme en
 *    fait.
 *
 * 3. Rien n'est promis qui n'existe pas. Le contenu est adossé à
 *    l'inventaire du code, pas aux documents de conception.
 */
import { IDENTITE } from '../identite.mjs';

export const deck = {
    ...IDENTITE,

    pages: [
        // ── OUVERTURE ────────────────────────────────────────────────────
        {
            type: 'cover',
            size: '34pt',
            title: 'Ce que fait votre<br>direction, enfin<br><span class="accent">visible.</span>',
            hook: 'Une plateforme unique pour piloter les activités d\'une organisation : '
                + 'des responsables désignés, des délais tenus, une trace de chaque décision — '
                + 'et des chiffres que la direction générale peut lire sans les reconstituer.',
        },

        {
            type: 'constat',
            note: 'le constat',
            kicker: 'Aujourd\'hui, dans la plupart des directions',
            title: 'Le travail se fait.<br>C\'est de le prouver<br>qui coûte cher.',
            cards: [
                { t: 'Le suivi vit dans des classeurs', d: 'Un onglet par sujet, un fichier par personne, une couleur par état. Cela tient — jusqu\'à un certain volume.' },
                { t: 'Les engagements n\'ont pas d\'horloge', d: 'Une promesse de délai vit dans un courriel. On découvre qu\'elle est dépassée quand le demandeur relance.' },
                { t: 'Les modifications n\'ont pas d\'auteur', d: 'Une date a changé. Personne ne sait par qui, ni quand, ni depuis quelle valeur.' },
                { t: 'Le rapport coûte deux jours', d: 'Consolider un état pour la direction demande un travail de copier-coller — et le résultat est périmé le jour où on le présente.' },
                { t: 'Le contrôle demande des preuves', d: 'La question n\'est jamais « avez-vous corrigé ? » mais « prouvez-le, et montrez quand ».' },
                { t: 'Un départ emporte la mémoire', d: 'Ce que savait la personne qui traitait le dossier s\'en va avec elle.' },
            ],
        },

        {
            type: 'reponse',
            note: 'la réponse',
            kicker: 'La réponse',
            title: 'Un endroit unique où<br>une chose à faire existe.',
            lead: 'Avec un responsable, une échéance, un état et un historique. Tout le reste — '
                + 'les rappels, les indicateurs, les preuves — en découle sans saisie supplémentaire.',
            shot: 'Le tableau de bord : l\'état de la direction en un écran',
            steps: [
                'Une activité est ouverte, ou importée.',
                'Elle reçoit un responsable et une échéance.',
                'Les rappels partent seuls, l\'historique s\'écrit.',
                'Les indicateurs sont là, sans les recalculer.',
            ],
        },

        {
            type: 'avantApres',
            note: 'avant/après',
            kicker: 'Le changement',
            title: 'La même direction,<br>vue de la direction générale.',
            before: [
                'On demande où en est un dossier.',
                'Les retards se découvrent à la relance.',
                'La priorité dépend de qui parle le plus fort.',
                'Une modification n\'a ni auteur ni date.',
                'Le rapport mensuel se fabrique à la main.',
                'Répondre à un contrôle mobilise une semaine.',
            ],
            after: [
                'Son état est à l\'écran, avec son responsable.',
                'L\'approche de l\'échéance se signale d\'elle-même.',
                'Elle se déduit de l\'impact et de l\'urgence.',
                'Chaque changement porte les deux, et l\'ancienne valeur.',
                'Il est déjà là, et s\'exporte.',
                'Les preuves sont rangées avec le dossier.',
            ],
        },

        {
            type: 'manifeste',
            note: 'manifeste 1',
            phrase: 'Ce qui n\'est pas<br>tracé n\'a pas<br><span class="accent">eu lieu.</span>',
        },

        // ── LE SOCLE ─────────────────────────────────────────────────────
        {
            type: 'capacite',
            note: 'socle',
            kicker: 'Le socle',
            title: 'Tout ce que vous suivez<br>obéit aux mêmes règles.',
            body: 'Un incident, une demande, un projet, un changement, une recommandation, un risque : '
                + 'ce sont des <b>types</b> d\'une même chose — une activité. Responsabilités, délais, '
                + 'validations, historique, recherche et indicateurs sont donc écrits une fois et valent '
                + 'partout. C\'est ce qui permet à la plateforme de s\'étendre sans jamais se refondre.',
            shot: 'La fiche d\'une activité : responsabilités, état, échéance, historique',
            result: {
                t: 'Ce que ça change',
                d: 'Ajouter un domaine à suivre relève du paramétrage, pas d\'un projet informatique.',
            },
        },

        {
            type: 'capacite',
            note: 'responsabilités',
            kicker: 'Les responsabilités',
            title: 'Un seul responsable.<br>Jamais deux.',
            body: 'Chaque activité porte un demandeur, <b>un</b> responsable principal, des contributeurs '
                + 'et, quand le circuit l\'exige, des valideurs. Le champ « responsable » n\'accepte qu\'un '
                + 'nom : une responsabilité partagée entre deux personnes est une responsabilité que '
                + 'personne n\'assume. Le travail, lui, se partage — c\'est le rôle des contributeurs.',
            shot: 'La désignation des acteurs sur un dossier',
            large: false,
        },

        {
            type: 'capacite',
            note: 'priorité',
            kicker: 'La priorité',
            title: 'Elle ne se réclame pas.<br>Elle se déduit.',
            body: 'On renseigne deux faits observables — l\'étendue de ce qui est touché, la vitesse à '
                + 'laquelle la situation se dégrade — et une matrice en tire la priorité. Quand chacun '
                + 'choisit librement, tout devient prioritaire et le mot perd son sens. Ici, on ne débat '
                + 'plus d\'un ressenti : on débat de l\'impact ou de l\'urgence, chacun argumentable.',
            shot: 'La matrice de priorité, paramétrable',
            result: {
                t: 'Ce que ça change',
                d: 'Les arbitrages cessent d\'être des rapports de force. Ils redeviennent des décisions.',
            },
        },

        {
            type: 'capacite',
            note: 'engagements',
            kicker: 'Les délais',
            title: 'Une promesse de délai<br>qui se surveille toute seule.',
            body: 'Chaque activité reçoit à son ouverture deux échéances — être prise en charge, être '
                + 'résolue — calculées depuis une grille que vous fixez. La plateforme surveille ensuite '
                + 'leur consommation et prévient <b>trois fois</b> avant l\'échéance, à mesure que le '
                + 'temps s\'épuise. Une priorité maximale non prise en charge déclenche une escalade.',
            shot: 'Une liste d\'activités avec l\'état des engagements',
            result: {
                t: 'Ce que ça change',
                d: 'Un retard se voit avant d\'en être un. Personne n\'a plus à surveiller un calendrier.',
            },
        },

        {
            type: 'capacite',
            note: 'cycles',
            kicker: 'Les circuits',
            title: 'Votre processus,<br>pas celui d\'un éditeur.',
            body: 'Chaque type d\'activité suit sa propre suite d\'états, et n\'autorise que les passages '
                + 'que vous avez prévus. Là où un accord est requis, la plateforme le bloque tant qu\'il '
                + 'n\'est pas donné — et la liste des valideurs se fige dès la première décision rendue, '
                + 'pour qu\'on ne change pas le jury en cours de vote.',
            shot: 'Un circuit de validation en cours',
        },

        {
            type: 'manifeste',
            note: 'manifeste 2',
            phrase: 'Un indicateur ne<br>vaut que par la<br><span class="accent">discipline qu\'il mesure.</span>',
        },

        // ── LES DOMAINES ────────────────────────────────────────────────
        {
            type: 'benefices',
            note: 'domaines',
            kicker: 'Le périmètre',
            title: 'Ce que la plateforme<br>sait déjà suivre.',
            items: [
                { t: 'Incidents et demandes', d: 'Ce qui interrompt un service, et ce que les collaborateurs sollicitent. Alimentés automatiquement depuis votre outil existant.' },
                { t: 'Projets', d: 'Types, jalons types, tâches, budget de suivi, avancement, documents et décisions.' },
                { t: 'Changements', d: 'Demande, évaluation d\'impact et de risque, comité de validation, planification, mise en œuvre, revue.' },
                { t: 'Audit et recommandations', d: 'Sources paramétrables, plan d\'action, justificatifs, validation de clôture.' },
                { t: 'Risques', d: 'Probabilité × impact, plan de traitement, revue périodique, matrice restituée telle quelle.' },
                { t: 'Conformité et gouvernance', d: 'Sujets de contrôle, comités, décisions et engagements pris — rattachés à un responsable et une échéance.' },
                { t: 'Patrimoine', d: 'Registre des biens, état constaté, valeur nette après amortissement.' },
            ],
        },

        {
            type: 'capacite',
            note: 'import',
            kicker: 'L\'existant',
            title: 'Vos outils actuels<br>alimentent la plateforme.',
            body: 'Un classeur déposé chaque jour suffit : la plateforme reconnaît les colonnes par leur '
                + 'intitulé — pas par leur position —, rapproche les dossiers déjà connus, met leur état à '
                + 'jour et signale ce qu\'elle n\'a pas su lire. Déposer deux fois le même fichier ne crée '
                + 'aucun doublon. Ce que vos équipes ont écrit dans la plateforme n\'est jamais écrasé.',
            shot: 'L\'écran d\'import et son compte rendu',
            result: {
                t: 'Ce que ça change',
                d: 'Aucun outil à remplacer, aucune double saisie : le pilotage se pose au-dessus de l\'existant.',
            },
        },

        {
            type: 'capacite',
            note: 'tableau de bord',
            kicker: 'Le pilotage',
            title: 'Trois questions,<br>dans le bon ordre.',
            body: 'Où en est-on, qu\'est-ce qui dérape, par quoi commencer. Le tableau de bord répond aux '
                + 'trois sur la période de votre choix, avec ses indicateurs, ses signaux et une liste '
                + 'courte ordonnée par urgence réelle plutôt que par date. Il s\'exporte tel quel : le '
                + 'support de comité n\'est plus à fabriquer.',
            shot: 'Le tableau de bord et ses indicateurs',
        },

        {
            type: 'capacite',
            note: 'analyses',
            kicker: 'Les analyses',
            title: 'Comprendre, et pas<br>seulement constater.',
            body: 'Répartitions, respect des délais par domaine et par priorité, temps passé dans chaque '
                + 'état, vieillissement du stock, taux de réouverture, charge par personne, concentration '
                + 'par catégorie, comparaison mois par mois. Deux vues font agir plus que toutes les '
                + 'autres : ce qui vieillit, et ce qui revient sans cesse.',
            shot: 'L\'écran d\'analyses',
            result: {
                t: 'Ce que ça change',
                d: 'On traite les causes une fois, au lieu de traiter les conséquences chaque semaine.',
            },
        },

        // ── LA CONFIANCE ────────────────────────────────────────────────
        {
            type: 'capacite',
            note: 'traçabilité',
            kicker: 'La preuve',
            title: 'Un registre que personne<br>ne peut réécrire.',
            body: 'Chaque création, modification, affectation, validation et clôture est inscrite avec son '
                + 'auteur, l\'heure, l\'ancienne et la nouvelle valeur. Le registre n\'accepte que des '
                + 'ajouts — la base de données elle-même refuse toute modification — et chaque écriture '
                + 'porte l\'empreinte de la précédente : une altération rompt la chaîne et se voit.',
            shot: 'Le journal d\'activité, filtrable et exportable',
            result: {
                t: 'Ce que ça change',
                d: 'Répondre à un contrôle devient une impression, pas une enquête.',
            },
        },

        {
            type: 'capacite',
            note: 'droits',
            kicker: 'Les accès',
            title: 'Déléguer sans ouvrir<br>ses chiffres à tout le monde.',
            body: 'Les profils décrivent des métiers, pas une hiérarchie : ils se créent, se renomment et '
                + 'se suppriment. Chacun n\'accède qu\'à ce qu\'on lui a ouvert, et ne voit que le périmètre '
                + 'qui le concerne. Organiser un dossier et l\'exécuter restent deux choses distinctes — '
                + 'cette frontière est tenue par le serveur, pas par l\'écran.',
            shot: 'La matrice des accès par profil',
            large: false,
        },

        {
            type: 'capacite',
            note: 'sécurité',
            kicker: 'La sécurité',
            title: 'Vérifiée, pas déclarée.',
            body: 'Mots de passe jamais lisibles, frein automatique sur les tentatives, session courte, '
                + 'coupure d\'accès immédiate, cloisonnement appliqué à la source. Plusieurs centaines de '
                + 'contrôles automatisés le vérifient à chaque livraison, et un scénario d\'intrusion '
                + 'rejouable tente, en une commande, de franchir une vingtaine de gardes.',
            shot: 'L\'administration des comptes',
            result: {
                t: 'Ce que ça change',
                d: 'La recette de sécurité se démontre en quelques minutes, au lieu de se promettre.',
            },
        },

        {
            type: 'capacite',
            note: 'résilience',
            kicker: 'La continuité',
            title: 'Elle reste consultable<br>quand tout vacille.',
            body: 'Une base qui redémarre, un serveur de messagerie en panne, une requête qui s\'éternise : '
                + 'chacun de ces incidents est prévu et contenu. La plateforme se rétablit seule, ne perd '
                + 'rien, et affiche un message compréhensible plutôt qu\'une erreur technique. C\'est '
                + 'précisément quand l\'infrastructure vacille qu\'on a besoin de savoir où en sont les choses.',
            shot: 'L\'écran de sauvegarde et de supervision',
            large: false,
        },

        {
            type: 'manifeste',
            note: 'manifeste 3',
            phrase: 'La confiance<br>ne se demande pas.<br><span class="accent">Elle se vérifie.</span>',
        },

        // ── PREUVES & ADOPTION ──────────────────────────────────────────
        {
            type: 'preuves',
            note: 'preuves',
            kicker: 'Concrètement',
            title: 'Ce que ça vaut,<br>chiffres en main.',
            figs: [
                { n: '1', u: ' écran', k: 'pour savoir ce qui est en retard, chez qui, et depuis combien de temps.' },
                { n: '3', u: ' rappels', k: 'avant chaque échéance, envoyés seuls, à mesure que le délai se consomme.' },
                { n: '0', u: ' ligne', k: 'de code pour ajouter une catégorie, un profil, une entité ou un délai.' },
                { n: '100', u: ' %', k: 'des actions inscrites dans un registre que personne ne peut réécrire.' },
            ],
        },

        {
            type: 'capacite',
            note: 'universalité',
            kicker: 'Votre organisation',
            title: 'Elle se règle sur vous,<br>pas l\'inverse.',
            body: 'Types d\'activité, catégories, états, circuits de validation, délais, profils, entités : '
                + 'rien de tout cela n\'est figé dans le logiciel. Une direction des opérations, un service '
                + 'qualité, une direction juridique ou des services généraux y retrouvent le même socle — '
                + 'une chose à faire, un responsable, un délai, une validation, une preuve — avec leur '
                + 'vocabulaire et leurs circuits.',
            shot: 'Le paramétrage des référentiels',
            result: {
                t: 'Ce que ça change',
                d: 'Le logiciel n\'impose pas son organisation. C\'est votre organisation qui reste la référence.',
            },
        },

        {
            type: 'benefices',
            note: 'bénéfices',
            kicker: 'Ce que vous récupérez',
            title: 'Du temps. De la clarté.<br>De quoi répondre.',
            items: [
                { t: 'Le temps', d: 'Fini les classeurs, les relances pour savoir où en est un dossier, les rapports fabriqués à la main. Ce temps-là revient au travail réel.' },
                { t: 'La clarté', d: 'Ce qui est ouvert, ce qui est en retard, chez qui, et pourquoi. Des chiffres calculés, pas des impressions rassemblées.' },
                { t: 'La sérénité', d: 'Vous déléguez sans perdre la main : chaque geste est tracé, chaque périmètre est cadré, chaque validation est exigée.' },
                { t: 'La capacité à répondre', d: 'À un contrôle, à un comité, à une direction générale — avec des preuves déjà rangées, à la date où elles ont été produites.' },
            ],
        },

        {
            type: 'benefices',
            note: 'mise en place',
            kicker: 'La mise en place',
            title: 'Quelques semaines,<br>pas un an.',
            items: [
                { t: 'On installe', d: 'Sur vos serveurs. Aucune donnée ne sort de chez vous, aucun abonnement à un service tiers pour ouvrir la plateforme.' },
                { t: 'On règle avec vous', d: 'Vos catégories, vos circuits, vos délais et vos profils. Ces décisions vous appartiennent : elles sont l\'essentiel du déploiement.' },
                { t: 'On raccorde l\'existant', d: 'Vos outils actuels continuent de tourner et alimentent la plateforme. Rien à remplacer le premier jour.' },
                { t: 'On mesure avant de promettre', d: 'Quelques semaines sans engagement de délai, pour fixer des cibles que vos équipes peuvent réellement tenir.' },
                { t: 'On vérifie', d: 'Recette fonctionnelle, puis scénario d\'intrusion rejouable avant la mise en service.' },
            ],
        },

        {
            type: 'dos',
            note: '4e de couverture',
            kicker: 'La suite',
            title: 'Voyons-la sur<br><span class="accent">vos dossiers.</span>',
            hook: 'Une démonstration prend trente minutes. On y ouvre une activité réelle, on la fait '
                + 'avancer, on regarde le tableau de bord bouger et on ouvre le registre. C\'est la façon '
                + 'la plus courte de savoir si cela répond à votre besoin.',
        },
    ],
};
