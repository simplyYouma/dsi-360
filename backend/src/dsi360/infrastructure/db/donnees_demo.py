"""Jeu de données de démonstration réaliste — DÉVELOPPEMENT UNIQUEMENT.

Refuse de s'exécuter hors ``environnement == "dev"``. À chaque lancement : **remet à zéro** les
activités/tâches/documents/commentaires/acteurs/notifications et les utilisateurs de démo, puis
recrée un jeu cohérent et stable (graine fixe) couvrant tous les modules et toutes les
fonctionnalités : tâches qui pilotent l'avancement, documents, commentaires, contributeurs et
valideurs, incidents/demandes « importés » simulés (pour les analyses SLA), SLA par module.

Le compte administrateur du seed et les référentiels (profils, directions, catégories, règles SLA)
ne sont jamais touchés.

Lancement : ``python -m dsi360.infrastructure.db.donnees_demo``.
"""

import asyncio
import json
import os
import random
import sys
from datetime import UTC, date, datetime, timedelta
from typing import Any

import asyncpg

from dsi360.config import get_settings
from dsi360.domain.activite import PREFIXE_REFERENCE, calculer_criticite, calculer_priorite
from dsi360.domain.etats import GATES_VALIDATION, ordre_etats, transitions_possibles
from dsi360.domain.sla import CiblesSla, echeances
from dsi360.infrastructure.audit import _empreinte, _serialiser
from dsi360.infrastructure.securite import hacher_mot_de_passe

random.seed(42)

#: Domaine des comptes de démonstration. Neutre à dessein : une démonstration se montre aussi
#: hors de la maison, et n'a alors à exposer ni l'identité de collaborateurs réels, ni le
#: domaine de l'entreprise. Il n'a pas à figurer dans `domaines_email_autorises` : le seed
#: écrit directement en base, il ne passe pas par la validation de l'administration.
DOMAINE_DEMO = "gmail.com"

# Équipe fictive de la démonstration. Profils métier : cf. docs/adr/0003.
UTILISATEURS = [
    (f"b.sissoko@{DOMAINE_DEMO}", "Sissoko", "Bakary", "ADMIN", "DSI"),
    (f"a.cisse@{DOMAINE_DEMO}", "Cissé", "Awa", "SUPPORT_APP_HELPDESK", "DSI"),
    (f"i.doumbia@{DOMAINE_DEMO}", "Doumbia", "Ibrahim", "SUPPORT_APP_HELPDESK", "DSI"),
    (f"n.bah@{DOMAINE_DEMO}", "Bah", "Nafissatou", "RESEAU_TELECOM", "DSI"),
    (f"m.camara@{DOMAINE_DEMO}", "Camara", "Modibo", "SYSTEME_RESEAU_TELECOM", "DSI"),
    (f"r.sylla@{DOMAINE_DEMO}", "Sylla", "Rokia", "SUPPORT_APP", "DSI"),
]
EMAILS_DEMO = [u[0] for u in UTILISATEURS]

#: Auteur des écritures de journal fabriquées par la démonstration.
EMAIL_JOURNAL_DEMO = f"demo@{DOMAINE_DEMO}"
#: Valeurs à purger au reset : la nouvelle **et** les anciennes, sinon une base déjà semée
#: garderait des lignes de journal orphelines que plus rien ne nettoierait.
EMAILS_JOURNAL_A_PURGER = (EMAIL_JOURNAL_DEMO, "demo@afgbank.ml")

# Sujets de démonstration. Volontairement **neutres** : ces titres s'affichent dans chaque liste
# et finissent dans les captures d'écran d'une plaquette commerciale. Ils doivent parler à une
# banque comme à une industrie ou à une administration — donc aucun nom de produit maison,
# aucune ville, aucun régulateur, aucun terme propre à un métier.
TITRES: dict[str, list[str]] = {
    "incident": [
        "Messagerie inaccessible depuis le siège", "Lenteurs sur l'application de gestion",
        "Coupure réseau sur le site secondaire", "Échec de la sauvegarde nocturne",
        "Imprimante de l'accueil hors service", "Saturation du disque serveur",
        "Traitement de nuit interrompu", "Connexion à distance instable",
        "Téléphonie interne muette", "Portail client inaccessible",
        "Poste de travail bloqué au démarrage", "Partage de fichiers inaccessible",
        "Certificat expiré sur l'intranet", "Salle de réunion sans affichage",
    ],
    "demande": [
        "Compte pour un nouvel arrivant", "Habilitation à l'outil de gestion",
        "Installation d'un poste de travail", "Accès distant pour un prestataire",
        "Remplacement d'un ordinateur portable", "Assistance sur un tableau de reporting",
        "Réinitialisation de mot de passe", "Accès au dossier partagé des ressources humaines",
        "Adresse de messagerie partagée", "Téléphone mobile professionnel",
        "Licence logicielle supplémentaire", "Départ d'un collaborateur : clôture des accès",
    ],
    "changement": [
        "Mise à jour du pare-feu", "Montée de version de la base de données",
        "Correctif éditeur sur l'application métier", "Changement d'opérateur du lien principal",
        "Renouvellement du certificat du portail", "Bascule vers le nouveau serveur de fichiers",
        "Ouverture d'un flux vers un partenaire", "Campagne de mise à jour des postes",
    ],
    "audit": [
        "Formaliser la revue des accès", "Tracer les opérations sensibles",
        "Formaliser et tester le plan de reprise", "Cloisonner les environnements",
        "Chiffrer les sauvegardes", "Désactiver les comptes dormants",
        "Documenter les procédures d'exploitation", "Encadrer les accès des prestataires",
    ],
    "risque": [
        "Indisponibilité du centre de données", "Fuite de données personnelles",
        "Dépendance à un fournisseur unique", "Obsolescence d'une application métier",
        "Attaque par rançongiciel", "Perte d'une compétence clé",
        "Défaillance de la chaîne de sauvegarde", "Non-conformité réglementaire",
    ],
    "cybersecurite": [
        "Revue des comptes à privilèges", "Vulnérabilité critique sur un serveur exposé",
        "Généralisation de la double authentification", "Habilitation sensible à valider",
        "Campagne de correctifs de sécurité", "Contrôle trimestriel des habilitations",
        "Sensibilisation à l'hameçonnage", "Revue des règles du pare-feu",
    ],
    "gouvernance": [
        "Comité de pilotage trimestriel", "Comité sécurité mensuel",
        "Arbitrage budgétaire sur l'hébergement", "Engagement sur les délais de service",
        "Plan d'actions issu du dernier audit", "Revue annuelle des contrats fournisseurs",
        "Feuille de route à douze mois",
    ],
    "projet": [
        "Refonte du portail interne", "Déploiement de la double authentification",
        "Site de secours informatique", "Dématérialisation des dossiers",
        "Mise en conformité réglementaire", "Modernisation du réseau inter-sites",
        "Nouvel outil décisionnel", "Migration de la messagerie",
        "Refonte du site institutionnel", "Centralisation des sauvegardes",
        "Automatisation des rapprochements", "Renouvellement du parc informatique",
    ],
}

# Description de chaque sujet (clé = titre). Donne du corps aux fiches : un texte crédible
# plutôt qu'une ligne générique. Neutre à dessein — ces fiches se montrent en démonstration.
DESCRIPTIONS: dict[str, str] = {
    # Incidents
    "Messagerie inaccessible depuis le siège": "Les collaborateurs du siège ne reçoivent plus "
    "leurs messages depuis ce matin. Le service de transport ne redémarre pas après la bascule "
    "de nuit et les files d'attente saturent.",
    "Lenteurs sur l'application de gestion": "Temps de réponse dégradés aux heures de pointe "
    "(10 h – 12 h). Les utilisateurs signalent des écrans figés au moment de valider un dossier.",
    "Coupure réseau sur le site secondaire": "Le site secondaire est isolé du système central. "
    "Le lien principal est tombé et la bascule sur le lien de secours ne s'est pas faite "
    "automatiquement.",
    "Échec de la sauvegarde nocturne": "La sauvegarde planifiée de 2 h a échoué sur le serveur "
    "de fichiers : espace insuffisant sur le volume de destination, signalé dans les journaux.",
    "Imprimante de l'accueil hors service": "L'imprimante de l'accueil n'imprime plus. Voyant "
    "d'erreur allumé, redémarrage sans effet, file d'impression bloquée.",
    "Saturation du disque serveur": "Le volume système du serveur applicatif atteint 96 %. "
    "Risque d'arrêt des services si le seuil n'est pas résorbé rapidement.",
    "Traitement de nuit interrompu": "Le traitement automatique de la nuit s'est arrêté en "
    "erreur : un fichier d'entrée présente un format non conforme.",
    "Connexion à distance instable": "Déconnexions répétées pour les collaborateurs en "
    "télétravail ; les sessions tombent toutes les quinze minutes environ.",
    "Téléphonie interne muette": "Plus aucun appel entrant ni sortant depuis le siège. Le "
    "serveur de communication ne répond plus aux terminaux.",
    "Portail client inaccessible": "Le portail est injoignable depuis l'extérieur. Les demandes "
    "en ligne ne parviennent plus aux équipes.",
    "Poste de travail bloqué au démarrage": "Un poste ne dépasse plus l'écran de démarrage "
    "depuis la dernière mise à jour. L'utilisateur travaille sur un poste de prêt.",
    "Partage de fichiers inaccessible": "Le dossier partagé d'un service n'est plus accessible : "
    "les droits semblent avoir été perdus lors de la dernière opération de maintenance.",
    "Certificat expiré sur l'intranet": "Le navigateur affiche un avertissement de sécurité à "
    "l'ouverture de l'intranet : le certificat a expiré ce week-end.",
    "Salle de réunion sans affichage": "L'écran de la salle du conseil ne reçoit plus le signal. "
    "Réunion de direction prévue en fin de matinée.",
    # Demandes
    "Compte pour un nouvel arrivant": "Ouverture d'un compte pour une personne recrutée : "
    "messagerie, poste de travail et applications métier selon la fiche de poste.",
    "Habilitation à l'outil de gestion": "Demande d'accès à l'outil de gestion pour un analyste : "
    "profil consultation et saisie, sans droit de validation.",
    "Installation d'un poste de travail": "Poste neuf à préparer avant mise en service : "
    "système, applications standard, sécurisation et raccordement au domaine.",
    "Accès distant pour un prestataire": "Accès temporaire pour un prestataire chargé d'une "
    "opération de maintenance ; durée limitée à la durée de l'intervention.",
    "Remplacement d'un ordinateur portable": "Portable en fin de vie à remplacer : reprise des "
    "données, configuration à l'identique et restitution de l'ancien matériel.",
    "Assistance sur un tableau de reporting": "Aide à la mise en place d'un tableau de suivi "
    "mensuel : formules, tableau croisé et mise en forme.",
    "Réinitialisation de mot de passe": "Compte verrouillé après plusieurs tentatives. "
    "L'utilisateur demande la réinitialisation de son mot de passe.",
    "Accès au dossier partagé des ressources humaines": "Demande d'accès au dossier partagé des "
    "ressources humaines pour un gestionnaire nouvellement affecté.",
    "Adresse de messagerie partagée": "Création d'une boîte partagée pour un service, avec les "
    "droits de lecture et d'envoi pour les membres de l'équipe.",
    "Téléphone mobile professionnel": "Attribution d'un mobile à un cadre : ligne, terminal et "
    "configuration de la messagerie professionnelle.",
    "Licence logicielle supplémentaire": "Un poste supplémentaire nécessite une licence de "
    "l'outil métier ; commande et affectation à faire.",
    "Départ d'un collaborateur : clôture des accès": "Fin de contrat : désactivation des comptes, "
    "restitution du matériel et transfert des dossiers en cours à son remplaçant.",
    # Changements
    "Mise à jour du pare-feu": "Application des dernières règles et du correctif de sécurité sur "
    "le pare-feu. Fenêtre de maintenance nocturne, plan de retour arrière prévu.",
    "Montée de version de la base de données": "Montée de version majeure de la base : migration "
    "des données, tests de non-régression et bascule le week-end.",
    "Correctif éditeur sur l'application métier": "Déploiement du correctif éditeur corrigeant "
    "une anomalie de calcul. Recette validée par les utilisateurs métier.",
    "Changement d'opérateur du lien principal": "Bascule progressive site par site vers le "
    "nouvel opérateur, avec surveillance renforcée pendant la période de recouvrement.",
    "Renouvellement du certificat du portail": "Renouvellement du certificat arrivant à "
    "expiration, sans interruption de service pour les utilisateurs.",
    "Bascule vers le nouveau serveur de fichiers": "Migration des partages vers le nouveau "
    "serveur : copie des données, reprise des droits et bascule des accès un samedi.",
    "Ouverture d'un flux vers un partenaire": "Ouverture d'un flux sécurisé vers un partenaire "
    "externe : règles de filtrage, chiffrement et tests de bout en bout.",
    "Campagne de mise à jour des postes": "Déploiement du lot de mises à jour sur l'ensemble du "
    "parc, par vagues successives pour limiter le risque.",
    # Audit & recommandations
    "Formaliser la revue des accès": "Recommandation de l'audit : instaurer une revue "
    "trimestrielle formalisée des droits d'accès aux applications sensibles.",
    "Tracer les opérations sensibles": "Mettre en place une journalisation exhaustive des "
    "opérations à risque et son archivage inviolable.",
    "Formaliser et tester le plan de reprise": "Formaliser le plan de reprise d'activité, "
    "aujourd'hui documenté partiellement, et l'éprouver par un test annuel.",
    "Cloisonner les environnements": "Séparer strictement les environnements de production, de "
    "recette et de développement, actuellement partiellement mutualisés.",
    "Chiffrer les sauvegardes": "Chiffrer les sauvegardes contenant des données personnelles, "
    "au repos comme lors des transferts.",
    "Désactiver les comptes dormants": "Identifier et désactiver les comptes inactifs depuis "
    "plus de quatre-vingt-dix jours, puis instaurer un contrôle périodique.",
    "Documenter les procédures d'exploitation": "Rédiger les procédures d'exploitation "
    "courantes, aujourd'hui transmises oralement, et les rendre accessibles à l'équipe.",
    "Encadrer les accès des prestataires": "Formaliser l'octroi, la durée et la revue des accès "
    "accordés aux intervenants extérieurs.",
    # Risques
    "Indisponibilité du centre de données": "Un incident majeur sur l'unique centre de données "
    "interromprait l'ensemble des services ; aucun site de secours n'est opérationnel.",
    "Fuite de données personnelles": "Exposition possible de données personnelles en cas de "
    "compromission d'un poste ou d'un compte à privilèges.",
    "Dépendance à un fournisseur unique": "Une application critique repose sur un éditeur unique "
    "sans clause de réversibilité, exposant l'organisation à un blocage contractuel.",
    "Obsolescence d'une application métier": "Une application métier n'est plus maintenue par "
    "son éditeur ; les correctifs de sécurité ne sont plus fournis.",
    "Attaque par rançongiciel": "Un rançongiciel chiffrant les serveurs paralyserait l'activité. "
    "Sensibilisation et sauvegardes hors ligne à renforcer.",
    "Perte d'une compétence clé": "Le départ de l'unique spécialiste d'une application critique "
    "laisserait l'organisation sans compétence interne.",
    "Défaillance de la chaîne de sauvegarde": "Les sauvegardes sont exécutées mais rarement "
    "testées : une restauration pourrait échouer au moment où elle serait vitale.",
    "Non-conformité réglementaire": "Certaines obligations ne sont pas encore couvertes par une "
    "procédure écrite, exposant l'organisation en cas de contrôle.",
    # Cybersécurité
    "Revue des comptes à privilèges": "Passer en revue tous les comptes à privilèges, justifier "
    "chaque accès et retirer les droits qui ne sont plus nécessaires.",
    "Vulnérabilité critique sur un serveur exposé": "Une vulnérabilité critique a été détectée "
    "sur un serveur accessible depuis l'extérieur : correctif à appliquer en urgence.",
    "Généralisation de la double authentification": "Déployer l'authentification à deux facteurs "
    "pour l'ensemble des collaborateurs, en commençant par les accès distants.",
    "Habilitation sensible à valider": "Demande d'accès à une fonction sensible, en attente de "
    "validation par le responsable de la sécurité.",
    "Campagne de correctifs de sécurité": "Appliquer le lot mensuel de correctifs sur "
    "l'ensemble du parc serveur, par vagues et avec fenêtre de retour arrière.",
    "Contrôle trimestriel des habilitations": "Contrôle périodique des identités et des accès : "
    "cohérence des profils avec les fiches de poste réelles.",
    "Sensibilisation à l'hameçonnage": "Campagne de sensibilisation et simulation d'hameçonnage "
    "auprès de l'ensemble des collaborateurs, avec mesure du taux de clic.",
    "Revue des règles du pare-feu": "Revue des règles accumulées au fil des années : "
    "suppression des règles obsolètes et documentation de celles qui restent.",
    # Gouvernance
    "Comité de pilotage trimestriel": "Comité de pilotage : avancement des projets, respect des "
    "engagements de service, arbitrages budgétaires.",
    "Comité sécurité mensuel": "Revue mensuelle de la sécurité : incidents survenus, "
    "vulnérabilités ouvertes et avancement du plan d'actions.",
    "Arbitrage budgétaire sur l'hébergement": "Arbitrage de la direction sur l'enveloppe allouée "
    "à l'hébergement : maintien interne ou externalisation partielle.",
    "Engagement sur les délais de service": "Formalisation des engagements de délai entre "
    "l'équipe informatique et les directions métier.",
    "Plan d'actions issu du dernier audit": "Suivi du plan d'actions issu de la dernière "
    "mission d'audit : échéances, responsables et preuves de mise en œuvre.",
    "Revue annuelle des contrats fournisseurs": "Passage en revue des contrats arrivant à "
    "échéance : niveaux de service obtenus, coûts et opportunités de renégociation.",
    "Feuille de route à douze mois": "Construction de la feuille de route de l'année : projets "
    "retenus, priorités, ressources nécessaires et jalons de décision.",
    # Projets
    "Refonte du portail interne": "Modernisation du portail utilisé quotidiennement par les "
    "équipes : ergonomie repensée, performances améliorées et nouveaux services en libre-service "
    "pour réduire les sollicitations du support.",
    "Déploiement de la double authentification": "Généralisation de l'authentification à deux "
    "facteurs à l'ensemble de l'organisation, afin de sécuriser les accès distants et les "
    "comptes sensibles.",
    "Site de secours informatique": "Mise en place d'un site de secours et d'un plan de reprise "
    "éprouvé. Objectif : garantir la continuité des services critiques en cas de sinistre du "
    "site principal.",
    "Dématérialisation des dossiers": "Passage au dossier entièrement numérique, de la "
    "constitution à l'archivage. Gains attendus sur les délais de traitement et la traçabilité.",
    "Mise en conformité réglementaire": "Programme de mise en conformité : traçabilité, sécurité "
    "des données et production des états réglementaires, en plusieurs chantiers coordonnés sur "
    "l'année.",
    "Modernisation du réseau inter-sites": "Refonte des liens réseau entre le siège et les "
    "sites : plus de débit, plus de résilience, et redondance automatique des liens opérateurs.",
    "Nouvel outil décisionnel": "Construction d'un outil décisionnel consolidant les données de "
    "l'organisation pour le pilotage : tableaux de bord de direction et indicateurs de suivi.",
    "Migration de la messagerie": "Migration de la messagerie interne vers une solution "
    "moderne : reprise des boîtes, des archives et des listes de diffusion, sans coupure pour "
    "les utilisateurs.",
    "Refonte du site institutionnel": "Refonte du site public : nouvelle identité visuelle, "
    "contenus actualisés et conformité aux exigences d'accessibilité.",
    "Centralisation des sauvegardes": "Unification des sauvegardes disparates en une plateforme "
    "centralisée et chiffrée, avec politique de rétention et tests de restauration réguliers.",
    "Automatisation des rapprochements": "Automatisation de rapprochements aujourd'hui manuels : "
    "réduction des délais de clôture et fiabilisation des écritures.",
    "Renouvellement du parc informatique": "Remplacement des postes de travail les plus anciens, "
    "avec reprise des données, recyclage du matériel sorti et mise à jour de l'inventaire.",
}

# Modules dont les tickets proviennent de l'import (incidents/demandes = import-only).
MODULES_IMPORTES = {"incident", "demande"}

# Intervenants extérieurs cités par le rapport importé : ils n'ont pas de compte chez nous,
# leurs dossiers sont donc suivis au niveau « prestataire ».
GESTIONNAIRES_DBS = [
    "Prestataire infogérance", "Support éditeur", "Hervé Lantier", "Aminata Barry",
]
# Collaborateurs qui ouvrent les dossiers (rapprochés dans core.demandeur, sans compte).
DEMANDEURS_DEMO = [
    "Mariam Doumbia", "Sékou Diarra", "Rokia Sangaré", "Boubacar Fofana", "Nana Kouyaté",
    "Adama Dembélé", "Fatou Diakité", "Salif Berthé", "Assitan Coulibaly", "Youssouf Maïga",
]
# Modules « fiche » à statuts génériques.
STATUTS: dict[str, list[str]] = {
    "incident": ["Nouveau", "Ouvert", "Ouvert", "Résolu", "Clôturé", "Réouvert"],
    "demande": ["Nouvelle", "Qualifiée", "En cours", "En validation", "Résolue", "Clôturée"],
    "audit": ["Ouverte", "Plan d'action", "En cours", "En cours", "En validation de clôture", "Clôturée"],
    "risque": ["Identifié", "Évalué", "Traitement", "Maîtrisé", "Accepté", "Revue"],
    "cybersecurite": ["Ouvert", "En traitement", "En traitement", "Corrigé", "Clôturé", "Accepté"],
    "gouvernance": ["À engager", "En cours", "En cours", "Réalisé", "Reporté"],
}
TERMINAUX = {"Clôturé", "Clôturée", "Résolu", "Résolue", "Annulé", "Rejeté", "Réalisé", "Implémenté"}
SPONSORS = [
    "Direction générale", "Systèmes d'information", "Direction des risques", "Direction métier",
]

TACHES_TITRES = [
    "Cadrer le besoin", "Analyser l'existant", "Rédiger la spécification", "Développer",
    "Tester en recette", "Préparer le déploiement", "Déployer en production", "Documenter",
    "Former les utilisateurs", "Clôturer et bilan",
]
# Fil de discussion, par module : un projet ne se commente pas comme un incident. Un commentaire
# hors sujet (« escaladé au N2 » sur un projet) rendrait les écrans de démonstration trompeurs.
COMMENTAIRES: dict[str, list[str]] = {
    "incident": [
        "Prise en charge, analyse des journaux en cours.",
        "Reproduit en recette : le service ne redémarre pas après la bascule.",
        "Contournement en place, les équipes peuvent travailler.",
        "Escaladé au support niveau 2, l'éditeur est sollicité.",
        "Correctif appliqué, à confirmer côté métier avant clôture.",
    ],
    "demande": [
        "Demande qualifiée, il manque l'accord du responsable hiérarchique.",
        "Compte créé, habilitations positionnées selon la fiche de poste.",
        "En attente de la validation du propriétaire de l'application.",
        "Matériel commandé, livraison annoncée sous dix jours.",
        "Accès distant ouvert et testé avec l'utilisateur.",
    ],
    "projet": [
        "Comité de pilotage tenu : le périmètre de la phase 1 est validé.",
        "Le prestataire a livré la recette ; deux anomalies bloquantes restent ouvertes.",
        "Décalage d'une semaine sur le jalon de recette, sans impact sur le go-live.",
        "Budget consommé à 60 % pour 55 % d'avancement, à surveiller.",
        "Formation des utilisateurs planifiée avant la bascule en production.",
        "Point d'avancement hebdomadaire : aucun point bloquant remonté.",
    ],
    "changement": [
        "Analyse d'impact complétée, le plan de retour arrière est testé.",
        "Validation demandée pour la fenêtre de samedi soir.",
        "Approuvé sous réserve d'une communication préalable aux utilisateurs.",
        "Bascule réalisée dans la fenêtre ; surveillance renforcée pendant 48 h.",
        "Bilan post-implémentation rédigé, aucun incident consécutif.",
    ],
    "audit": [
        "Plan d'action rédigé avec le contrôle permanent.",
        "Justificatifs déposés, en attente de la validation de clôture.",
        "Échéance renégociée avec l'auditeur : fin du trimestre.",
        "Recommandation traitée, la preuve de mise en œuvre est jointe.",
    ],
    "risque": [
        "Criticité réévaluée après la mise en place du plan de traitement.",
        "Risque accepté par la Direction, revue programmée dans six mois.",
        "Le contrat fournisseur prévoit désormais une clause de réversibilité.",
        "Revue périodique effectuée : la probabilité baisse, l'impact reste élevé.",
    ],
    "cybersecurite": [
        "Revue des comptes administrateurs terminée, trois comptes dormants désactivés.",
        "Correctif de sécurité déployé sur l'ensemble du parc serveur.",
        "Double authentification activée sur les sites, quelques comptes restent à enrôler.",
        "Vulnérabilité confirmée par le scan, correctif éditeur attendu.",
    ],
    "gouvernance": [
        "Décision entérinée en comité, la direction en est informée.",
        "Engagement reporté au prochain comité faute de quorum.",
        "Plan d'actions mis à jour, deux actions soldées sur cinq.",
        "Compte rendu diffusé aux membres du comité.",
    ],
}
# Repli pour un module sans texte dédié : volontairement neutre, jamais trompeur.
COMMENTAIRES_DEFAUT = [
    "Prise en charge, analyse en cours.",
    "Point d'avancement fait en réunion d'équipe.",
    "Validé par le responsable, on peut clôturer.",
]
# Documents réalistes par module (nom + contenu) : un extrait crédible plutôt qu'un blob neutre.
DOCS_MODULE: dict[str, list[tuple[str, str]]] = {
    "projet": [
        ("Note de cadrage.txt", "Note de cadrage\n\nContexte, objectifs, périmètre et livrables du "
         "projet. Jalons principaux, budget prévisionnel, risques identifiés et gouvernance "
         "(comité de pilotage mensuel)."),
        ("Compte rendu du comite.txt", "Compte rendu du comité de pilotage\n\nAvancement par lot, "
         "points bloquants, décisions prises et prochaines échéances. Budget consommé et reste à "
         "faire."),
        ("Planning previsionnel.txt", "Planning prévisionnel\n\nPhases : cadrage, conception, "
         "réalisation, recette, déploiement. Dates clés et dépendances entre les lots."),
    ],
    "changement": [
        ("Analyse d'impact.txt", "Analyse d'impact\n\nApplications et sites concernés, fenêtre "
         "de maintenance, indisponibilité attendue et populations impactées."),
        ("Plan de retour arriere.txt", "Plan de retour arrière\n\nProcédure de restauration en cas "
         "d'échec, points de contrôle et critères de décision de rollback."),
        ("Plan de deploiement.txt", "Plan de déploiement\n\nÉtapes ordonnées, prérequis, "
         "responsables et vérifications post-bascule."),
    ],
    "audit": [
        ("Plan d'action.txt", "Plan d'action\n\nRecommandation, actions correctives, responsables, "
         "échéances et indicateurs de suivi."),
        ("Justificatif de mise en oeuvre.txt", "Justificatif de mise en œuvre\n\nPreuves de "
         "réalisation jointes pour la validation de clôture de la recommandation."),
    ],
    "cybersecurite": [
        ("Rapport de scan.txt", "Rapport de scan de vulnérabilités\n\nVulnérabilités détectées par "
         "criticité, systèmes concernés et correctifs recommandés."),
        ("Procedure de remediation.txt", "Procédure de remédiation\n\nÉtapes d'application du "
         "correctif, fenêtre d'intervention et vérification post-correctif."),
    ],
    "gouvernance": [
        ("Compte rendu de comite.txt", "Compte rendu de comité\n\nOrdre du jour, décisions, "
         "engagements pris et responsables, date de la prochaine réunion."),
    ],
}

# Jalons de projet (dates clés) — cf. module Projets.
JALONS_TITRES = [
    "Cadrage validé", "Lancement officiel", "Fin de la conception", "Fin de la recette",
    "Go-live", "Bilan de clôture",
]
# Champs RFC (SI-12.04) pour les changements.
RFC_TEXTES = {
    "analyse_impact": "Impact sur l'application métier et les sites distants ; interruption "
    "planifiée hors heures ouvrées ; utilisateurs concernés : équipes support et accueil.",
    "analyse_risque": "Risque de régression maîtrisé ; environnement de pré-production validé ; "
    "fenêtre de repli identifiée.",
    "plan_deploiement": "1) Sauvegarde complète. 2) Bascule progressive. 3) Contrôles post-bascule. "
    "4) Communication aux métiers.",
    "plan_retour_arriere": "Restauration de la sauvegarde N-1 et bascule sur le lien secondaire ; "
    "délai de retour arrière estimé à 30 minutes.",
    "bilan_post_implementation": "Déploiement conforme au plan ; aucun incident majeur ; "
    "surveillance renforcée 48 h.",
}
# Revue périodique (cybersécurité, gouvernance, risques).
PERIODICITES = ["Mensuelle", "Trimestrielle", "Semestrielle", "Annuelle"]
MODULES_REVUE = {"cybersecurite", "gouvernance", "risque"}


def _dsn() -> str:
    return get_settings().database_url.replace("+asyncpg", "")


async def _matrice(conn: asyncpg.Connection, module: str) -> dict[int, CiblesSla]:
    lignes = await conn.fetch(
        "SELECT priorite, prise_en_charge_minutes, resolution_minutes "
        "FROM core.sla_regle WHERE module=$1",
        module,
    )
    if not lignes:
        return {
            p: CiblesSla(30, 480) for p in range(1, 6)
        }
    return {
        int(r["priorite"]): CiblesSla(int(r["prise_en_charge_minutes"]), int(r["resolution_minutes"]))
        for r in lignes
    }


def _chemin_vers(module: str, statut: str) -> list[str]:
    """Plus court chemin de l'état initial vers `statut`, sur la machine à états réelle."""
    depart = ordre_etats(module)[0]
    if statut == depart:
        return [depart]
    file, vus = [[depart]], {depart}
    while file:
        chemin = file.pop(0)
        for suivant in transitions_possibles(module, chemin[-1]):
            if suivant in vus:
                continue
            if suivant == statut:
                return [*chemin, suivant]
            vus.add(suivant)
            file.append([*chemin, suivant])
    return [statut]  # état hors machine : on le pose tel quel


async def _journal_cycle_de_vie(
    conn: asyncpg.Connection,
    module: str,
    reference: str,
    statut: str,
    debut: datetime,
    fin: datetime | None,
) -> None:
    """Écrit dans le journal le parcours qui mène l'activité à son statut courant.

    Sans lui, les fiches de démo n'ont aucun cycle de vie et les analyses de flux (durée par
    statut, réouvertures) n'ont rien à lire. La chaîne d'empreintes est respectée : ces entrées
    sont indistinguables de vraies.
    """
    chemin = _chemin_vers(module, statut)
    # Une résolution sur six ne tient pas : le ticket rebondit par « Réouvert ». C'est cette
    # trace que mesure le taux de réouverture — sans elle, l'indicateur semblerait mort.
    if "Résolu" in chemin and "Réouvert" in transitions_possibles(module, "Résolu"):
        if random.random() < 0.18:
            i = chemin.index("Résolu")
            chemin = [*chemin[: i + 1], "Réouvert", *chemin[i:]]
    borne = fin or datetime.now(UTC)
    duree = max((borne - debut).total_seconds(), 3600 * len(chemin))
    horodatage = debut
    for i, etat in enumerate(chemin):
        precedent = await conn.fetchval(
            "SELECT hash_courant FROM audit.journal ORDER BY id DESC LIMIT 1"
        )
        action = "CREATION" if i == 0 else "TRANSITION"
        ancienne = None if i == 0 else {"statut": chemin[i - 1]}
        nouvelle = {"statut": etat, "source": "IMPORT_SD"}
        av, nv = _serialiser(ancienne), _serialiser(nouvelle)
        hash_courant = _empreinte(
            [precedent or "", horodatage.isoformat(), EMAIL_JOURNAL_DEMO, module, action,
             module, reference, av or "", nv or "", ""]
        )
        await conn.execute(
            "INSERT INTO audit.journal (horodatage, acteur_email, module, action, cible_type, "
            " cible_id, ancienne_valeur, nouvelle_valeur, hash_precedent, hash_courant) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8::jsonb,$9,$10)",
            horodatage, EMAIL_JOURNAL_DEMO, module, action, module, reference,
            av, nv, precedent, hash_courant,
        )
        # Séjours vraisemblables : parts inégales du parcours, jamais nulles.
        horodatage = horodatage + timedelta(
            seconds=duree / len(chemin) * random.uniform(0.4, 1.6)
        )


async def _reset(conn: asyncpg.Connection) -> None:
    """Vide toutes les données transactionnelles + utilisateurs de démo (dev only)."""
    # cascade : tache, document, commentaire, acteur, note, lien, jalon
    await conn.execute("DELETE FROM core.activite")
    await conn.execute("DELETE FROM core.notification")
    await conn.execute("DELETE FROM core.demandeur")
    await conn.execute("DELETE FROM core.equipement")
    await conn.execute("DELETE FROM core.utilisateur WHERE email = ANY($1::text[])", EMAILS_DEMO)
    # Le journal réel est append-only (déclencheur) ; les entrées de démo, elles, se régénèrent
    # avec le reste — on suspend le déclencheur le temps de la purge, ce que seul cet outil de
    # dev se permet. La chaîne d'empreintes garde alors des trous — assumé : base de dev, la
    # démo est la seule à écrire sous cet acteur.
    await conn.execute("ALTER TABLE audit.journal DISABLE TRIGGER trg_journal_pas_de_delete")
    try:
        await conn.execute(
            "DELETE FROM audit.journal WHERE acteur_email = ANY($1::text[])",
            list(EMAILS_JOURNAL_A_PURGER),
        )
    finally:
        await conn.execute("ALTER TABLE audit.journal ENABLE TRIGGER trg_journal_pas_de_delete")


async def _creer_personnages(conn: asyncpg.Connection) -> None:
    """Crée l'équipe fictive. Idempotent : relancer la démo ne duplique rien."""
    empreinte = hacher_mot_de_passe("changez-moi")
    for email, nom, prenom, profil, direction in UTILISATEURS:
        await conn.execute(
            "INSERT INTO core.utilisateur"
            "(email, nom, prenom, profil_id, direction_id, source_auth, mot_de_passe_hash, "
            " doit_changer_mdp) VALUES ($1,$2,$3,"
            " (SELECT id FROM core.profil WHERE code=$4),"
            " (SELECT id FROM core.direction WHERE code=$5),'LOCAL',$6,false) "
            "ON CONFLICT (email) DO NOTHING",
            email, nom, prenom, profil, direction, empreinte,
        )


async def _assurer_utilisateurs(conn: asyncpg.Connection) -> list[str]:
    """L'équipe qui joue la démonstration.

    **Par défaut : des personnages fictifs.** Une démonstration se montre aussi à l'extérieur,
    et les noms des collaborateurs n'ont pas à y figurer — ni sur un écran partagé, ni dans une
    capture qui finira dans une plaquette commerciale.

    `DSI360_DEMO_EQUIPE_REELLE=1` rétablit l'ancien comportement — les vrais agents, plus
    parlants pour une démonstration interne. Le canal e-mail de chaque acteur est alors coupé
    (préférence réversible depuis son profil) pour qu'aucune donnée fictive ne remplisse une
    boîte réelle. L'administrateur, lui, n'est jamais acteur de la démonstration.
    """
    reelle = os.environ.get("DSI360_DEMO_EQUIPE_REELLE") == "1"
    lecture = (
        "SELECT u.id FROM core.utilisateur u JOIN core.profil p ON p.id = u.profil_id "
        "WHERE u.actif AND p.code <> 'ADMIN' AND u.email {} ORDER BY u.nom, u.prenom"
    )

    if not reelle:
        await _creer_personnages(conn)
        equipe = [r["id"] for r in await conn.fetch(lecture.format("= ANY($1::text[])"), EMAILS_DEMO)]
        if equipe:
            return equipe
        # Aucun personnage créé (profils absents d'une base neuve) : mieux vaut une démonstration
        # peuplée que vide — on retombe sur les comptes existants, en le disant.
        print("Personnages de démonstration indisponibles : repli sur les comptes existants.")

    equipe = [r["id"] for r in await conn.fetch(lecture.format("IS NOT NULL"))]
    if len(equipe) < 3:
        await _creer_personnages(conn)
        equipe = [r["id"] for r in await conn.fetch(lecture.format("IS NOT NULL"))]
    for uid in equipe:
        await conn.execute(
            "INSERT INTO core.preference_notification (utilisateur_id, email) "
            "VALUES ($1, false) ON CONFLICT (utilisateur_id) DO UPDATE SET email = false",
            uid,
        )
    return equipe


# --- Inventaire : un parc plausible, pour éprouver l'amortissement et les rattachements ---

# Emplacements et rattachements observés dans le fichier réel d'AFG.
# Sites et rattachements : neutres, comme le reste de la démonstration.
_EMPLACEMENTS = (
    "Siège — Direction générale",
    "Siège — Salle serveurs",
    "Siège — Open space",
    "Site Nord",
    "Site Sud",
    "Site Est",
    "Entrepôt logistique",
)
_DEPARTEMENTS = (
    "Direction générale",
    "Systèmes d'information",
    "Exploitation",
    "Réseau & télécoms",
    "Finances & comptabilité",
    "Ressources humaines",
    "Accueil & services généraux",
)

# (désignation, modèle, valeur mini, valeur maxi, taux, durée) — matériel d'entreprise courant.
_TYPES_MATERIEL: tuple[tuple[str, str, int, int, int, int], ...] = (
    ("Serveur lame", "HPE ProLiant DL380", 8_000_000, 15_000_000, 20, 5),
    ("Baie de stockage", "Dell EMC Unity", 18_000_000, 30_000_000, 20, 5),
    ("Onduleur", "APC Smart-UPS 10kVA", 2_500_000, 6_000_000, 20, 5),
    ("Commutateur cœur", "Cisco Catalyst 9300", 3_000_000, 7_500_000, 20, 5),
    ("Pare-feu", "Fortinet FortiGate 200F", 4_000_000, 9_000_000, 20, 5),
    ("Borne Wi-Fi", "Ubiquiti UniFi U6", 180_000, 420_000, 25, 4),
    ("Poste de travail", "Dell Latitude 5540", 450_000, 950_000, 25, 4),
    ("Poste de travail", "HP EliteBook 840", 500_000, 1_100_000, 25, 4),
    ("Poste fixe", "Lenovo ThinkCentre M70", 380_000, 760_000, 25, 4),
    ("Imprimante réseau", "HP LaserJet M507", 350_000, 800_000, 25, 4),
    ("Copieur multifonction", "Ricoh IM C3000", 1_800_000, 3_400_000, 20, 5),
    ("Scanner de production", "Kodak i3450", 1_200_000, 2_600_000, 25, 4),
    ("Vidéoprojecteur", "Epson EB-L200", 600_000, 1_300_000, 25, 4),
    ("Écran de salle", "Samsung QM65R", 900_000, 1_900_000, 25, 4),
)


async def _inventaire(conn: asyncpg.Connection, utilisateurs: list[str]) -> int:
    """Parc matériel de démonstration, échelonné sur vingt ans.

    L'étalement des dates d'acquisition est ce qui compte : il produit des équipements neufs,
    à mi-vie et totalement amortis — sans quoi on ne verrait jamais la valeur nette bouger.
    """
    emplacements = {
        libelle: await conn.fetchval(
            "INSERT INTO core.emplacement (libelle) VALUES ($1) "
            "ON CONFLICT (upper(btrim(libelle))) DO UPDATE SET libelle = excluded.libelle "
            "RETURNING id",
            libelle,
        )
        for libelle in _EMPLACEMENTS
    }
    departements = {
        libelle: await conn.fetchval(
            "INSERT INTO core.departement_equipement (libelle) VALUES ($1) "
            "ON CONFLICT (upper(btrim(libelle))) DO UPDATE SET libelle = excluded.libelle "
            "RETURNING id",
            libelle,
        )
        for libelle in _DEPARTEMENTS
    }

    # Matricules sur les comptes : sans eux, aucun équipement ne trouverait son détenteur.
    # On ne réattribue jamais un matricule déjà porté — une base déjà semée en garde d'anciens,
    # et le matricule est unique en base : une collision faisait échouer toute la génération.
    pris = {
        r["matricule"]
        for r in await conn.fetch(
            "SELECT upper(btrim(matricule)) AS matricule FROM core.utilisateur "
            "WHERE matricule IS NOT NULL"
        )
    }
    numero = 4501
    for uid in utilisateurs:
        if await conn.fetchval("SELECT matricule FROM core.utilisateur WHERE id = $1", uid):
            continue
        while f"MAT-{numero:04d}" in pris:
            numero += 1
        matricule = f"MAT-{numero:04d}"
        await conn.execute(
            "UPDATE core.utilisateur SET matricule = $2 WHERE id = $1", uid, matricule
        )
        pris.add(matricule)
        numero += 1

    aujourdhui = date.today()
    cree = 0
    for i in range(1, 121):
        designation, modele, mini, maxi, taux, duree = random.choice(_TYPES_MATERIEL)
        # Ancienneté pondérée vers le récent : un parc se renouvelle. Tirer uniformément sur
        # vingt ans donnerait un parc amorti à 80 %, où la valeur nette ne dirait plus rien —
        # alors que c'est précisément ce qu'on vient lire. Les vieux GAB restent la minorité.
        tranche = random.choices(
            [(90, 365 * 3), (365 * 3, 365 * 6), (365 * 6, 365 * 20)],
            weights=[50, 30, 20],
        )[0]
        acquisition = aujourdhui - timedelta(days=random.randint(*tranche))
        # Un dixième du parc n'a pas encore de détenteur : le compteur « sans détenteur » a
        # alors quelque chose à signaler, comme dans la vraie vie après un import.
        detenteur = None if random.random() < 0.1 else random.choice(utilisateurs)
        # Quelques matériels sortis du parc (cédés, détruits) pour éprouver la vue « Sortis ».
        actif = random.random() > 0.08
        await conn.execute(
            "INSERT INTO core.equipement (code_immo, designation, modele, numero_serie, "
            " emplacement_id, departement_id, detenteur_id, taux, date_acquisition, "
            " duree_annees, valeur_acquisition, source, actif) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,'IMPORT_IMMO',$12) "
            "ON CONFLICT DO NOTHING",
            f"INF{i:05d}",
            designation,
            modele,
            f"SN-{random.randint(100000, 999999)}",
            emplacements[random.choice(_EMPLACEMENTS)],
            departements[random.choice(_DEPARTEMENTS)],
            detenteur,
            taux,
            acquisition,
            duree,
            random.randint(mini, maxi),
            actif,
        )
        cree += 1
    return cree


#: Motifs de constat plausibles, par état : ce qu'un agent écrit vraiment sur le terrain.
_MOTIFS_CONSTAT: dict[str, tuple[str, ...]] = {
    "BON": (
        "Vu sur site, en service",
        "Retrouvé au poste de son détenteur",
        "En fonctionnement, aucun défaut apparent",
        "Contrôlé en salle serveurs",
    ),
    "REBUT": (
        "Obsolète, ne répond plus aux besoins",
        "Hors service depuis plusieurs mois",
        "Pièces détachées introuvables",
    ),
    "CASSE": (
        "Écran fêlé, inutilisable",
        "Ne démarre plus après surtension",
        "Boîtier endommagé lors du transport",
    ),
}


async def _constats(conn: asyncpg.Connection, utilisateurs: list[str]) -> int:
    """Contrôles de terrain sur le parc : les uns récents, les autres vieux d'un an.

    Le mélange est ce qui fait vivre l'écran : une part contrôlée ces dernières semaines, une
    part contrôlée il y a plus d'un an (donc « à contrôler » de nouveau), et une part jamais
    vue. Sans ces trois cas, le compteur de contrôle n'aurait rien à raconter.
    """
    actifs = [r["id"] for r in await conn.fetch("SELECT id FROM core.equipement WHERE actif")]
    aujourdhui = datetime.now(UTC)
    poses = 0

    # 55 % du parc contrôlé récemment, 20 % contrôlé il y a plus d'un an, le reste jamais.
    recents = random.sample(actifs, k=int(len(actifs) * 0.55))
    restants = [i for i in actifs if i not in set(recents)]
    anciens = random.sample(restants, k=int(len(restants) * 0.45))

    for identifiants, borne_min, borne_max in (
        (recents, 1, 60),
        (anciens, 380, 700),
    ):
        for ident in identifiants:
            etat = random.choices(["BON", "REBUT", "CASSE"], weights=[90, 6, 4])[0]
            await conn.execute(
                "UPDATE core.equipement SET etat_constate = $2, constate_le = $3, "
                "constate_par = $4, constat_motif = $5 WHERE id = $1",
                ident, etat,
                aujourdhui - timedelta(days=random.uniform(borne_min, borne_max)),
                random.choice(utilisateurs),
                random.choice(_MOTIFS_CONSTAT[etat]),
            )
            poses += 1
    return poses


#: Notes du journal de bord (projets, changements) : ce qu'on écrit en marge d'un dossier,
#: distinct de la discussion — un constat daté plutôt qu'un échange.
NOTES_MODULE: dict[str, list[tuple[str, str]]] = {
    "projet": [
        ("Réunion de lancement tenue avec les référents métier ; périmètre confirmé.", "Cadrage"),
        ("Budget révisé après consultation : enveloppe complémentaire à arbitrer.", "En cours"),
        ("Décalage de deux semaines sur la recette, sans impact sur la date de bascule.", "En cours"),
        ("Bilan de fin de projet rédigé : objectifs atteints, deux réserves mineures.", "Clôturé"),
    ],
    "changement": [
        ("Fenêtre de maintenance retenue : samedi 22 h – 2 h, communication faite la veille.", "Planifié"),
        ("Retour arrière testé à blanc sur l'environnement de recette : concluant.", "Planifié"),
        ("Opération réalisée dans la fenêtre, surveillance renforcée pendant 48 h.", "Implémenté"),
    ],
}

#: Liens utiles rattachés aux dossiers : documentation, procédures, sources externes. Les URL
#: pointent volontairement vers un intranet fictif — une démonstration ne doit ouvrir aucun site.
LIENS_MODULE: dict[str, list[tuple[str, str]]] = {
    "projet": [
        ("Espace projet", "https://intranet.exemple/projets/espace"),
        ("Planning partagé", "https://intranet.exemple/projets/planning"),
        ("Fiche budgétaire", "https://intranet.exemple/finances/budget"),
    ],
    "risque": [
        ("Cartographie des risques", "https://intranet.exemple/risques/cartographie"),
        ("Procédure de traitement", "https://intranet.exemple/risques/procedure"),
    ],
    "audit": [
        ("Rapport d'audit complet", "https://intranet.exemple/audit/rapport"),
        ("Suivi du plan d'actions", "https://intranet.exemple/audit/suivi"),
    ],
    "cybersecurite": [
        ("Bulletin de sécurité", "https://intranet.exemple/securite/bulletin"),
        ("Politique de sécurité", "https://intranet.exemple/securite/politique"),
    ],
    "gouvernance": [
        ("Compte rendu du comité", "https://intranet.exemple/comites/compte-rendu"),
        ("Tableau de bord de direction", "https://intranet.exemple/pilotage/tableau-de-bord"),
    ],
}


async def _notes(
    conn: asyncpg.Connection, activite_id: str, module: str, cree_le: datetime, auteur: str
) -> None:
    """Journal de bord du dossier. Sans lui, l'onglet « Notes » paraît mort en démonstration."""
    modeles = NOTES_MODULE.get(module)
    if not modeles:
        return
    for texte, contexte in random.sample(modeles, k=random.randint(1, min(2, len(modeles)))):
        await conn.execute(
            "INSERT INTO core.note (activite_id, texte, contexte, auteur_email, cree_le) "
            "VALUES ($1,$2,$3,$4,$5)",
            activite_id, texte, contexte, auteur,
            cree_le + timedelta(days=random.uniform(1, 20)),
        )


async def _liens(
    conn: asyncpg.Connection, activite_id: str, module: str, cree_le: datetime, auteur: str
) -> None:
    """Liens utiles du dossier : la documentation vit ailleurs, le dossier sait où."""
    modeles = LIENS_MODULE.get(module)
    if not modeles:
        return
    for libelle, url in random.sample(modeles, k=random.randint(1, len(modeles))):
        await conn.execute(
            "INSERT INTO core.lien (activite_id, libelle, url, cree_par, cree_le) "
            "VALUES ($1,$2,$3,$4,$5)",
            activite_id, libelle, url, auteur,
            cree_le + timedelta(days=random.uniform(0.5, 12)),
        )


async def _categories(conn: asyncpg.Connection, module: str) -> list[str]:
    return [r["id"] for r in await conn.fetch(
        "SELECT id FROM core.categorie WHERE module=$1", module
    )]


async def _creer_taches(
    conn: asyncpg.Connection, activite_id: str, cree_le: datetime, utilisateurs: list[str],
    nb: int, part_terminees: float,
) -> int:
    """Crée nb tâches, dont ~part_terminees terminées. Renvoie l'avancement (%)."""
    terminees = 0
    for i in range(nb):
        finie = random.random() < part_terminees
        statut = "Terminée" if finie else random.choice(["À faire", "En cours"])
        if finie:
            terminees += 1
        await conn.execute(
            "INSERT INTO core.tache "
            "(activite_id, titre, statut, assigne_id, echeance, ordre, cree_le) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7)",
            activite_id, random.choice(TACHES_TITRES), statut, random.choice(utilisateurs),
            (cree_le + timedelta(days=random.randint(5, 40))).date(), i, cree_le,
        )
    return round(100 * terminees / nb) if nb else 0


async def _pieces_jointes(
    conn: asyncpg.Connection, activite_id: str, email: str, nb: int, module: str
) -> None:
    docs = DOCS_MODULE.get(module, [])
    for nom, texte in random.sample(docs, min(nb, len(docs))):
        contenu = texte.encode("utf-8")
        await conn.execute(
            "INSERT INTO core.document "
            "(activite_id, nom, type_mime, taille, contenu, depose_par) "
            "VALUES ($1,$2,'text/plain',$3,$4,$5)",
            activite_id, nom, len(contenu), contenu, email,
        )


async def _commentaires(
    conn: asyncpg.Connection,
    activite_id: str,
    utilisateurs: list[str],
    cree_le: datetime,
    nb: int,
    module: str,
) -> None:
    textes = COMMENTAIRES.get(module, COMMENTAIRES_DEFAUT)
    # Sans tirage sans remise, un fil de trois messages répète souvent deux fois la même phrase.
    choisis = random.sample(textes, min(nb, len(textes)))
    for texte in choisis:
        uid = random.choice(utilisateurs)
        email = await conn.fetchval("SELECT email FROM core.utilisateur WHERE id=$1", uid)
        await conn.execute(
            "INSERT INTO core.commentaire (activite_id, auteur_id, auteur_email, texte, cree_le) "
            "VALUES ($1,$2,$3,$4,$5)",
            activite_id, uid, email, texte,
            cree_le + timedelta(hours=random.randint(1, 72)),
        )


def _decision_valideur(module: str, statut: str) -> str | None:
    """Décision cohérente avec l'état atteint.

    Une décision de valideur **fait basculer** l'activité (approbation unanime → état validé,
    un rejet → état de rejet). Le jeu de démo ne doit donc jamais poser une décision qui
    contredirait le statut : une activité encore *en attente de validation* n'a pas de décision.
    """
    gate = GATES_VALIDATION.get(module)
    if gate is None:
        return None  # module sans porte de validation : la décision n'aurait aucun effet
    en_attente, cible_ok, cible_ko = gate
    if statut in en_attente:
        return None  # décision encore attendue — cohérent avec l'état affiché
    if statut == cible_ko and statut in TERMINAUX:
        return "REJETE"
    if statut in TERMINAUX or statut == cible_ok:
        return "APPROUVE"
    return None


async def _acteurs(
    conn: asyncpg.Connection, activite_id: str, utilisateurs: list[str], responsable_id: str,
    statut: str, module: str,
) -> None:
    autres = [u for u in utilisateurs if u != responsable_id]
    random.shuffle(autres)
    for uid in autres[:2]:
        await conn.execute(
            "INSERT INTO core.activite_acteur (activite_id, utilisateur_id, role) "
            "VALUES ($1,$2,'CONTRIBUTEUR') ON CONFLICT (activite_id, role) DO NOTHING",
            activite_id, uid,
        )
    if len(autres) > 2:
        await conn.execute(
            "INSERT INTO core.activite_acteur (activite_id, utilisateur_id, role, decision) "
            "VALUES ($1,$2,'VALIDEUR',$3) ON CONFLICT (activite_id, role) DO NOTHING",
            activite_id, autres[2], _decision_valideur(module, statut),
        )


async def _jalons(
    conn: asyncpg.Connection, activite_id: str, debut: datetime, statut: str
) -> None:
    """2–4 jalons par projet ; atteints selon l'avancement / statut."""
    nb = random.randint(2, 4)
    tous_atteints = statut in TERMINAUX
    for i in range(nb):
        atteint = tous_atteints or (i < nb - 1 and random.random() < 0.6)
        echeance = (debut + timedelta(days=30 * (i + 1))).date()
        await conn.execute(
            "INSERT INTO core.jalon (activite_id, titre, echeance, atteint, ordre) "
            "VALUES ($1,$2,$3,$4,$5)",
            activite_id, JALONS_TITRES[i % len(JALONS_TITRES)], echeance, atteint, i,
        )


async def _niveaux_support(conn: asyncpg.Connection, utilisateurs: list[str]) -> None:
    """Affecte un niveau de support (N1/N2) aux agents de démo.

    Le niveau d'un ticket importé se lit sur son gestionnaire (ADR-0005) : sans niveau ici, les
    tickets de démo retomberaient tous au N1."""
    # La DSI n'a pas de N3 : un ticket sans gestionnaire de chez nous est chez DBS, donc N3.
    # On ne touche qu'aux comptes SANS niveau : un niveau posé par l'administrateur fait foi.
    for i, uid in enumerate(utilisateurs):
        await conn.execute(
            "UPDATE core.utilisateur SET niveau_support=$2 "
            "WHERE id=$1 AND niveau_support IS NULL",
            uid, 2 if i % 3 == 2 else 1,  # deux N1 pour un N2 : la forme d'une vraie équipe
        )


async def creer_donnees() -> None:  # noqa: C901 - générateur linéaire de démo
    # Garde-fou *fail-closed* : ce script EFFACE toutes les activités avant de régénérer la démo.
    # `environnement` vaut « dev » par défaut : se fier à cette valeur laisserait le script détruire
    # une base de prod dès qu'il tourne sans configuration chargée (DSN par défaut = base de prod).
    # On exige donc que DSI360_ENVIRONNEMENT soit **explicitement** présent ET égal à « dev ». En
    # dev, env.ps1 le charge depuis .env ; ailleurs, son absence suffit à refuser.
    declare = os.environ.get("DSI360_ENVIRONNEMENT")
    if declare != "dev" or get_settings().environnement != "dev":
        print(
            "REFUS : les données de démonstration ne se créent qu'en 'dev' (elles EFFACENT les\n"
            "activités existantes). DSI360_ENVIRONNEMENT doit valoir explicitement 'dev' — "
            f"trouvé : {declare!r}. En prod, ce script ne doit jamais être lancé."
        )
        sys.exit(1)

    maintenant = datetime.now(UTC)
    annee = maintenant.year
    conn = await asyncpg.connect(_dsn())
    total = 0
    try:
        await _reset(conn)
        utilisateurs = await _assurer_utilisateurs(conn)
        await _niveaux_support(conn, utilisateurs)
        equipements = await _inventaire(conn, utilisateurs)
        await _constats(conn, utilisateurs)
        directions = [r["code"] for r in await conn.fetch("SELECT code FROM core.direction")]

        for module, titres in TITRES.items():
            prefixe = PREFIXE_REFERENCE[module]
            cats = await _categories(conn, module)
            matrice = await _matrice(conn, module)
            seq = 0
            for titre in titres:
                seq += 1
                reference = f"{prefixe}-{annee}-{seq:05d}"
                impact = random.randint(1, 5)
                urgence = random.randint(1, 5)
                cree_le = maintenant - timedelta(days=random.randint(0, 55), hours=random.randint(0, 23))
                responsable: str | None = random.choice(utilisateurs)
                donnees: dict[str, Any] = {}
                priorite: int | None = None
                sla_pc: datetime | None = None
                sla_res: datetime | None = None
                resolu: datetime | None = None
                cloture: datetime | None = None
                pris_en_charge: datetime | None = None
                source = "SAISIE"
                source_id: str | None = None

                if module == "projet":
                    statut = random.choice(["Cadrage", "En cours", "En cours", "Clôturé"])
                    donnees = {
                        "sponsor": random.choice(SPONSORS),
                        "budget": random.choice([5_000_000, 15_000_000, 42_000_000, 90_000_000, 120_000_000]),
                        "date_debut": cree_le.date().isoformat(),
                        "date_fin": (cree_le + timedelta(days=random.randint(60, 240))).date().isoformat(),
                        "avancement": 0,
                    }
                elif module == "risque":
                    statut = random.choice(STATUTS[module])
                    donnees = {"probabilite": impact, "impact": urgence,
                               "criticite": calculer_criticite(impact, urgence)}
                elif module == "changement":
                    statut = random.choice(
                        ["Brouillon", "Soumis", "Évaluation", "CAB", "Validé", "Planifié",
                         "En implémentation", "Implémenté", "Clôturé"]
                    )
                    priorite = calculer_priorite(impact, urgence)
                    donnees = {"avancement": 0, "type_changement": random.choice(
                        ["Standard", "Normal", "Urgent"])}
                    # Champs RFC (SI-12.04) : renseignés dès l'évaluation ; bilan après implémentation.
                    if statut not in ("Brouillon", "Soumis"):
                        donnees.update({c: RFC_TEXTES[c] for c in (
                            "analyse_impact", "analyse_risque", "plan_deploiement",
                            "plan_retour_arriere")})
                    if statut in ("Implémenté", "Clôturé"):
                        donnees["bilan_post_implementation"] = RFC_TEXTES["bilan_post_implementation"]
                else:
                    statut = random.choice(STATUTS[module])
                    priorite = calculer_priorite(impact, urgence)

                demandeur_id = None
                # Incidents/Demandes : simulés « importés » (source SD), TTR et prise en
                # charge mesurés. Un ticket sur quatre est chez DBS : son gestionnaire du
                # rapport n'est personne chez nous (ADR-0005).
                if module in MODULES_IMPORTES:
                    source = "IMPORT_SD"
                    source_id = f"{seq:06d}"
                    cibles = matrice.get(priorite or 3, CiblesSla(30, 480))
                    ttr = int(cibles.resolution_minutes * random.choice([0.4, 0.7, 0.9, 1.3, 1.8]))
                    trep = int(
                        cibles.prise_en_charge_minutes * random.choice([0.3, 0.6, 0.9, 1.4, 2.0])
                    )
                    demandeur_nom = random.choice(DEMANDEURS_DEMO)
                    if random.random() < 0.25:
                        responsable = None  # chez DBS : hors de nos comptes
                        gestionnaire_nom = random.choice(GESTIONNAIRES_DBS)
                    else:
                        gestionnaire_nom = "Support interne"
                    donnees.update({
                        "ttr_minutes": ttr,
                        "ttrespond_minutes": trep,
                        "gestionnaire": gestionnaire_nom,
                        "demandeur": demandeur_nom,
                    })
                    demandeur_id = await conn.fetchval(
                        "INSERT INTO core.demandeur (nom_complet) VALUES ($1) "
                        "ON CONFLICT (lower(nom_complet)) DO UPDATE SET maj_le = now() "
                        "RETURNING id",
                        demandeur_nom,
                    )
                    if statut in TERMINAUX:
                        resolu = cree_le + timedelta(minutes=ttr)
                        cloture = resolu if statut.startswith("Clôtur") else None

                # Revue périodique (cybersécurité, gouvernance, risques) sur un échantillon.
                if module in MODULES_REVUE and random.random() < 0.6:
                    donnees["periodicite"] = random.choice(PERIODICITES)
                    donnees["prochaine_revue"] = (
                        maintenant + timedelta(days=random.randint(15, 120))
                    ).date().isoformat()

                # Échéances SLA depuis la matrice du module. Un ticket importé porte une
                # priorité, donc un engagement : il a des échéances comme les autres (ADR-0005).
                if priorite is not None:
                    ech = echeances(priorite, cree_le, matrice)
                    sla_pc, sla_res = ech.prise_en_charge_le, ech.resolution_le
                    if statut in TERMINAUX and module not in MODULES_IMPORTES:
                        resolu = cree_le + timedelta(days=random.randint(1, 5))
                        cloture = resolu
                    elif resolu is None:
                        # Ticket encore ouvert : échéance répartie autour de maintenant, pour une
                        # démo variée (à l'heure / approche / dépassé). Sinon « créé il y a 0–55 j »
                        # + cible courte = presque tout en dépassé (une mer de rouge).
                        heures = random.choice([96, 72, 48, 120, 36, 24, 12, 6, 2, 1, -4, -24, -72])
                        sla_res = maintenant + timedelta(hours=heures)

                # Prise en charge (première réponse) : mesurée pour l'importé (via trep), sinon
                # posée sur la plupart des activités déjà prises en main ; le reste attend encore.
                if module in MODULES_IMPORTES and trep:
                    pris_en_charge = cree_le + timedelta(minutes=trep)
                elif module not in MODULES_IMPORTES and (resolu is not None or random.random() < 0.7):
                    pris_en_charge = cree_le + timedelta(hours=random.randint(1, 24))

                activite_id = await conn.fetchval(
                    "INSERT INTO core.activite"
                    "(reference, module, titre, description, direction_id, categorie_id, "
                    " responsable_id, demandeur_externe_id, impact, urgence, priorite, statut, "
                    " source, source_id, sla_prise_en_charge_le, sla_resolution_le, cree_le, "
                    " resolu_le, cloture_le, donnees, pris_en_charge_le)"
                    " VALUES ($1,$2,$3,$4,"
                    " (SELECT id FROM core.direction WHERE code=$5),"
                    " $6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20::jsonb,$21) "
                    "RETURNING id",
                    reference, module, titre, DESCRIPTIONS.get(titre, "Donnée de démonstration."),
                    random.choice(directions),
                    random.choice(cats) if cats and module != "projet" else None,
                    responsable, demandeur_id,
                    impact if module != "projet" else None,
                    urgence if module != "projet" else None,
                    priorite, statut, source, source_id,
                    sla_pc, sla_res, cree_le, resolu, cloture, json.dumps(donnees), pris_en_charge,
                )
                total += 1

                # Le journal raconte le parcours du ticket : sans lui, la fiche n'a pas de
                # cycle de vie et les analyses de flux n'ont rien à lire.
                if module in MODULES_IMPORTES:
                    await _journal_cycle_de_vie(
                        conn, module, reference, statut, cree_le, resolu or cloture
                    )

                # Tâches (projets & changements) → avancement + acteurs/docs/commentaires.
                if module in ("projet", "changement") and statut not in ("Cadrage", "Brouillon", "Soumis"):
                    part = 1.0 if statut in ("Clôturé", "Implémenté") else random.choice([0.25, 0.5, 0.75])
                    avancement = await _creer_taches(
                        conn, activite_id, cree_le, utilisateurs, random.randint(3, 5), part
                    )
                    await conn.execute(
                        "UPDATE core.activite SET donnees = donnees || $2::jsonb WHERE id=$1",
                        activite_id, json.dumps({"avancement": avancement}),
                    )
                    await _pieces_jointes(
                        conn, activite_id, EMAILS_DEMO[0], random.randint(1, 2), module
                    )

                # Documents sur audit / cybersécurité / gouvernance (justificatifs, rapports, CR).
                if module in ("audit", "cybersecurite", "gouvernance") and random.random() < 0.7:
                    await _pieces_jointes(
                        conn, activite_id, EMAILS_DEMO[0], random.randint(1, 2), module
                    )

                # Jalons (dates clés) sur les projets.
                if module == "projet":
                    await _jalons(conn, activite_id, cree_le, statut)

                # Notes / fil de discussion : sur la grande majorité des activités, pour que les
                # fiches aient du corps (une fiche sans aucune note paraît morte en démonstration).
                if random.random() < 0.85:
                    await _commentaires(
                        conn, activite_id, utilisateurs, cree_le, random.randint(2, 4), module
                    )
                # Journal de bord et liens utiles : chaque onglet de la fiche doit avoir quelque
                # chose à montrer, sans quoi la démonstration paraît inachevée.
                if random.random() < 0.6:
                    await _notes(conn, activite_id, module, cree_le, EMAILS_DEMO[0])
                if random.random() < 0.65:
                    await _liens(conn, activite_id, module, cree_le, EMAILS_DEMO[0])
                if responsable is not None and random.random() < 0.5:
                    await _acteurs(conn, activite_id, utilisateurs, responsable, statut, module)

        # Quelques notifications réalistes pour peupler la cloche (référence + titre réels).
        activites_recentes = await conn.fetch(
            "SELECT id, reference, titre FROM core.activite ORDER BY cree_le DESC LIMIT 8"
        )
        for r in activites_recentes:
            type_notif = random.choice(["ASSIGNATION", "SLA_APPROCHE", "MENTION", "VALIDATION"])
            titre_notif, message = {
                "ASSIGNATION": (
                    f"Activité assignée — {r['reference']}",
                    f"{r['reference']} « {r['titre']} » vous a été assignée.",
                ),
                "SLA_APPROCHE": (
                    f"SLA en approche — {r['reference']}",
                    f"L'échéance de « {r['titre']} » approche.",
                ),
                "MENTION": (
                    f"Vous êtes mentionné — {r['reference']}",
                    f"Un collègue vous a mentionné sur « {r['titre']} ».",
                ),
                "VALIDATION": (
                    f"Validation demandée — {r['reference']}",
                    f"Votre décision est attendue sur « {r['titre']} ».",
                ),
            }[type_notif]
            await conn.execute(
                "INSERT INTO core.notification (destinataire_id, activite_id, type, titre, message) "
                "VALUES ($1,$2,$3,$4,$5)",
                random.choice(utilisateurs), r["id"], type_notif, titre_notif, message,
            )

        print(f"Données de démonstration recréées : {total} activités (+ tâches, documents, "
              f"commentaires, acteurs, notifications) et {equipements} équipements.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(creer_donnees())
