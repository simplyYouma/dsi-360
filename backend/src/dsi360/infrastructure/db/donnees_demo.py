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
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg

from dsi360.config import get_settings
from dsi360.domain.activite import PREFIXE_REFERENCE, calculer_criticite, calculer_priorite
from dsi360.domain.etats import GATES_VALIDATION, ordre_etats, transitions_possibles
from dsi360.domain.sla import CiblesSla, echeances
from dsi360.infrastructure.audit import _empreinte, _serialiser
from dsi360.infrastructure.securite import hacher_mot_de_passe

random.seed(42)

# Tous les utilisateurs du système sont de la DSI (les autres noms des fichiers importés — DBS —
# ne deviennent pas des comptes). Profils métier : cf. docs/adr/0003.
UTILISATEURS = [
    ("a.toure@afgbank.ml", "Touré", "Aïcha", "ADMIN", "DSI"),
    ("m.diallo@afgbank.ml", "Diallo", "Moussa", "SUPPORT_APP_HELPDESK", "DSI"),
    ("f.keita@afgbank.ml", "Keïta", "Fanta", "SUPPORT_APP_HELPDESK", "DSI"),
    ("o.sanogo@afgbank.ml", "Sanogo", "Oumar", "RESEAU_TELECOM", "DSI"),
    ("k.coulibaly@afgbank.ml", "Coulibaly", "Kadia", "SYSTEME_RESEAU_TELECOM", "DSI"),
    ("s.traore@afgbank.ml", "Traoré", "Salif", "SUPPORT_APP", "DSI"),
]
EMAILS_DEMO = [u[0] for u in UTILISATEURS]

TITRES: dict[str, list[str]] = {
    "incident": [
        "Panne messagerie Exchange", "Lenteur application OAS", "Coupure réseau agence Niaréla",
        "Échec sauvegarde nocturne", "Imprimante guichet HS", "Saturation disque serveur SI",
        "Erreur batch interbancaire", "Accès VPN instable", "Téléphonie IP en panne",
        "Indisponibilité Payway",
    ],
    "demande": [
        "Création compte agent", "Habilitation module crédit", "Installation antivirus poste",
        "Ouverture VPN prestataire", "Nouveau poste de travail", "Assistance Excel reporting",
        "Réinitialisation mot de passe", "Accès partage RH",
    ],
    "changement": [
        "Mise à jour pare-feu", "Migration base PostgreSQL", "Déploiement correctif core banking",
        "Bascule lien opérateur", "Montée de version OAS", "Changement certificat TLS",
    ],
    "audit": [
        "Renforcer la revue des accès", "Tracer les opérations sensibles", "Plan reprise à formaliser",
        "Cloisonner les environnements", "Chiffrer les sauvegardes", "Revue des comptes dormants",
    ],
    "risque": [
        "Indisponibilité datacenter", "Fuite de données clients", "Dépendance fournisseur unique",
        "Obsolescence d'un applicatif", "Cyberattaque par rançongiciel", "Perte de compétence clé",
    ],
    "cybersecurite": [
        "Revue des comptes administrateurs", "Vulnérabilité critique serveur web", "Activation MFA agences",
        "Habilitation sensible à valider", "Correctif système d'exploitation", "Contrôle IAM trimestriel",
    ],
    "gouvernance": [
        "COPIL trimestriel DSI", "Comité sécurité mensuel", "Décision DG budget cloud",
        "Engagement sur les SLA", "Plan d'actions audit BCEAO",
    ],
    "projet": [
        "Migration cœur bancaire", "Refonte du portail agences", "Déploiement MFA groupe",
        "Datacenter de secours (PRA)", "Dématérialisation des dossiers crédit",
        "Mise en conformité BCEAO", "Modernisation du réseau interagences",
        "Nouveau SI décisionnel", "Migration messagerie cloud", "Refonte du site institutionnel",
        "Centralisation de la sauvegarde", "Automatisation des rapprochements",
    ],
}

# Description réelle par activité (clé = titre). Donne du corps aux fiches de démonstration :
# une description crédible, dans le contexte d'AFG Bank Mali, plutôt qu'un texte générique.
DESCRIPTIONS: dict[str, str] = {
    # Incidents
    "Panne messagerie Exchange": "Les utilisateurs du siège ne reçoivent plus leurs e-mails "
    "depuis ce matin. Le service de transport Exchange ne redémarre pas après la bascule de nuit ; "
    "les files d'attente saturent.",
    "Lenteur application OAS": "Temps de réponse dégradés sur l'applicatif OAS aux heures de "
    "pointe (10h–12h). Les agents de crédit signalent des écrans figés à la validation des dossiers.",
    "Coupure réseau agence Niaréla": "L'agence de Niaréla est isolée du SI central. Le lien "
    "opérateur principal est tombé et la bascule sur le lien de secours n'a pas été automatique.",
    "Échec sauvegarde nocturne": "La sauvegarde planifiée de 2h a échoué sur le serveur de "
    "fichiers. Espace insuffisant sur le volume de destination signalé dans les journaux.",
    "Imprimante guichet HS": "L'imprimante du guichet 3 n'imprime plus les reçus clients. Voyant "
    "d'erreur allumé, redémarrage sans effet.",
    "Saturation disque serveur SI": "Le volume système du serveur applicatif atteint 96 %. "
    "Risque d'arrêt des services si le seuil n'est pas résorbé rapidement.",
    "Erreur batch interbancaire": "Le traitement batch des virements interbancaires s'est arrêté "
    "en erreur cette nuit : un fichier d'entrée présente un format non conforme.",
    "Accès VPN instable": "Déconnexions répétées du VPN pour les agents en télétravail ; les "
    "sessions tombent toutes les quinze minutes environ.",
    "Téléphonie IP en panne": "La téléphonie sur IP est muette au siège. Aucun appel entrant ni "
    "sortant ; le serveur de communication ne répond plus aux terminaux.",
    "Indisponibilité Payway": "La plateforme Payway est inaccessible depuis les agences ; les "
    "opérations de paiement par carte sont bloquées.",
    # Demandes
    "Création compte agent": "Ouverture d'un compte pour un agent recruté à la direction crédit : "
    "messagerie, poste de travail et applicatifs métier selon la fiche de poste.",
    "Habilitation module crédit": "Demande d'habilitation au module d'octroi de crédit pour un "
    "analyste : profil consultation et saisie, sans droit de validation.",
    "Installation antivirus poste": "Poste de travail neuf à équiper de l'antivirus d'entreprise "
    "avant mise en service.",
    "Ouverture VPN prestataire": "Accès VPN temporaire pour un prestataire chargé de la "
    "maintenance de l'applicatif décisionnel ; durée limitée à l'intervention.",
    "Nouveau poste de travail": "Fourniture et configuration d'un poste complet pour un agent "
    "muté au service des opérations.",
    "Assistance Excel reporting": "Aide à la mise en place d'un tableau de reporting mensuel : "
    "formules, tableau croisé et mise en forme.",
    "Réinitialisation mot de passe": "Compte verrouillé après plusieurs tentatives. L'agent "
    "demande la réinitialisation de son mot de passe.",
    "Accès partage RH": "Demande d'accès au dossier partagé des ressources humaines pour un "
    "gestionnaire de paie.",
    # Changements
    "Mise à jour pare-feu": "Application des dernières règles et du correctif de sécurité sur le "
    "pare-feu périmétrique. Fenêtre de maintenance nocturne, plan de retour arrière prévu.",
    "Migration base PostgreSQL": "Montée de version majeure de la base PostgreSQL de l'applicatif "
    "décisionnel : migration des données, tests de non-régression et bascule le week-end.",
    "Déploiement correctif core banking": "Déploiement du correctif éditeur sur le cœur bancaire "
    "pour corriger une anomalie de calcul d'intérêts. Recette validée par le métier.",
    "Bascule lien opérateur": "Changement de l'opérateur du lien principal inter-agences : "
    "bascule progressive site par site avec surveillance renforcée.",
    "Montée de version OAS": "Passage de l'applicatif OAS à la version supérieure apportant des "
    "corrections de performance, en coordination avec l'éditeur.",
    "Changement certificat TLS": "Renouvellement du certificat TLS du portail agences arrivant à "
    "expiration, sans interruption de service.",
    # Audit & recommandations
    "Renforcer la revue des accès": "Recommandation de l'audit groupe : instaurer une revue "
    "trimestrielle formalisée des droits d'accès aux applicatifs sensibles.",
    "Tracer les opérations sensibles": "Mettre en place une journalisation exhaustive des "
    "opérations à risque et son archivage inviolable, conformément aux exigences BCEAO.",
    "Plan reprise à formaliser": "Formaliser et tester le plan de reprise d'activité "
    "informatique, aujourd'hui documenté partiellement.",
    "Cloisonner les environnements": "Séparer strictement les environnements de production, de "
    "recette et de développement, actuellement partiellement mutualisés.",
    "Chiffrer les sauvegardes": "Chiffrer les sauvegardes contenant des données clients, au repos "
    "comme lors des transferts.",
    "Revue des comptes dormants": "Identifier et désactiver les comptes inactifs depuis plus de "
    "quatre-vingt-dix jours.",
    # Risques IT
    "Indisponibilité datacenter": "Un incident majeur sur l'unique datacenter interromprait "
    "l'ensemble des services ; absence de site de secours opérationnel.",
    "Fuite de données clients": "Exposition possible de données clients en cas de compromission "
    "d'un poste ou d'un compte à privilèges.",
    "Dépendance fournisseur unique": "Le cœur bancaire repose sur un éditeur unique sans clause "
    "de réversibilité, exposant la banque à un blocage contractuel.",
    "Obsolescence d'un applicatif": "Un applicatif métier n'est plus maintenu par son éditeur ; "
    "les correctifs de sécurité ne sont plus fournis.",
    "Cyberattaque par rançongiciel": "Un rançongiciel chiffrant les serveurs paralyserait "
    "l'activité. Sensibilisation et sauvegardes hors ligne à renforcer.",
    "Perte de compétence clé": "Le départ de l'unique expert d'un applicatif critique laisserait "
    "la banque sans compétence interne.",
    # Cybersécurité
    "Revue des comptes administrateurs": "Passer en revue tous les comptes à privilèges, "
    "justifier chaque accès et retirer les droits non nécessaires.",
    "Vulnérabilité critique serveur web": "Une vulnérabilité critique a été détectée sur le "
    "serveur web exposé : correctif éditeur à appliquer en urgence.",
    "Activation MFA agences": "Déployer l'authentification à deux facteurs pour tous les agents "
    "des agences.",
    "Habilitation sensible à valider": "Demande d'accès à une fonction sensible en attente de "
    "validation par le RSSI.",
    "Correctif système d'exploitation": "Appliquer le lot mensuel de correctifs de sécurité sur "
    "l'ensemble du parc serveur.",
    "Contrôle IAM trimestriel": "Contrôle périodique de la gestion des identités et des accès : "
    "cohérence des profils avec les fiches de poste.",
    # Gouvernance
    "COPIL trimestriel DSI": "Comité de pilotage trimestriel : avancement des projets, respect "
    "des SLA, arbitrages budgétaires.",
    "Comité sécurité mensuel": "Revue mensuelle de la posture de sécurité : incidents, "
    "vulnérabilités et plan d'actions.",
    "Décision DG budget cloud": "Arbitrage de la Direction Générale sur l'enveloppe budgétaire "
    "allouée à la migration cloud.",
    "Engagement sur les SLA": "Formalisation des engagements de niveau de service entre la DSI et "
    "les directions métier.",
    "Plan d'actions audit BCEAO": "Suivi du plan d'actions issu de la mission BCEAO : échéances, "
    "responsables et preuves de mise en œuvre.",
    # Projets (cadrage plus étoffé)
    "Migration cœur bancaire": "Remplacement du système central de la banque par une solution "
    "moderne. Le projet couvre la reprise des données, l'intégration aux applicatifs périphériques "
    "et la formation des équipes, avec une bascule en une seule fenêtre pour limiter l'indisponibilité.",
    "Refonte du portail agences": "Modernisation du portail utilisé quotidiennement par les "
    "agences : ergonomie repensée, performances améliorées et nouveaux services en libre-service "
    "pour réduire les sollicitations du support.",
    "Déploiement MFA groupe": "Généralisation de l'authentification à deux facteurs à l'ensemble "
    "du groupe, afin de sécuriser les accès distants et les comptes sensibles selon les standards "
    "groupe.",
    "Datacenter de secours (PRA)": "Mise en place d'un site de secours et d'un plan de reprise "
    "d'activité éprouvé. Objectif : garantir la continuité des services critiques en cas de "
    "sinistre du site principal.",
    "Dématérialisation des dossiers crédit": "Passage au dossier de crédit entièrement numérique, "
    "de la constitution à l'archivage. Gains attendus sur les délais d'octroi et la traçabilité "
    "réglementaire.",
    "Mise en conformité BCEAO": "Programme de mise en conformité aux exigences de la BCEAO : "
    "traçabilité, sécurité des données et reporting réglementaire, en plusieurs chantiers "
    "coordonnés sur l'année.",
    "Modernisation du réseau interagences": "Refonte des liens réseau entre le siège et les "
    "agences pour plus de débit et de résilience, avec redondance automatique des liens opérateurs.",
    "Nouveau SI décisionnel": "Construction d'un système décisionnel consolidant les données de "
    "la banque pour le pilotage : tableaux de bord directionnels et indicateurs réglementaires.",
    "Migration messagerie cloud": "Migration de la messagerie interne vers une solution cloud du "
    "groupe : reprise des boîtes, des archives et des listes de diffusion, sans coupure pour les "
    "utilisateurs.",
    "Refonte du site institutionnel": "Refonte du site public de la banque : nouvelle identité "
    "visuelle, contenus actualisés et conformité aux exigences d'accessibilité.",
    "Centralisation de la sauvegarde": "Unification des sauvegardes disparates en une plateforme "
    "centralisée et chiffrée, avec politique de rétention et tests de restauration réguliers.",
    "Automatisation des rapprochements": "Automatisation des rapprochements comptables "
    "interbancaires aujourd'hui manuels : réduction des délais de clôture et fiabilisation des "
    "écritures.",
}

# Modules dont les tickets proviennent de l'import (incidents/demandes = import-only).
MODULES_IMPORTES = {"incident", "demande"}

# Gestionnaires du rapport quotidien qui ne sont pas des nôtres : leurs tickets sont chez DBS.
GESTIONNAIRES_DBS = ["Issa Konaté", "Awa Camara", "Prestataire DBS", "Cheick Oumar Sissoko"]
# Agents de la banque qui ouvrent les tickets (rapprochés dans core.demandeur, sans compte).
DEMANDEURS_DEMO = [
    "Mariam Doumbia", "Sékou Touré", "Rokia Sangaré", "Boubacar Cissé", "Nana Kouyaté",
    "Adama Dembélé", "Fatou Diakité", "Modibo Keïta", "Assitan Traoré", "Youssouf Maïga",
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
SPONSORS = ["Direction Générale", "DSI", "Direction des Risques", "Direction Métier"]

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
        "Contournement en place, les guichets peuvent travailler.",
        "Escaladé au support niveau 2, l'éditeur est sollicité.",
        "Correctif appliqué, à confirmer côté métier avant clôture.",
    ],
    "demande": [
        "Demande qualifiée, il manque l'accord du responsable hiérarchique.",
        "Compte créé, habilitations positionnées selon la fiche de poste.",
        "En attente de la validation du propriétaire de l'application.",
        "Matériel commandé, livraison annoncée sous dix jours.",
        "Accès VPN ouvert et testé avec l'agent.",
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
        "Passage en CAB demandé pour la fenêtre de samedi soir.",
        "Le CAB approuve sous réserve d'une communication préalable aux agences.",
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
        "MFA activé pour les agences, quelques agents restent à enrôler.",
        "Vulnérabilité confirmée par le scan, correctif éditeur attendu.",
    ],
    "gouvernance": [
        "Décision entérinée en COPIL, la DG en est informée.",
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
        ("Compte rendu COPIL.txt", "Compte rendu du comité de pilotage\n\nAvancement par lot, "
         "points bloquants, décisions prises et prochaines échéances. Budget consommé et reste à "
         "faire."),
        ("Planning previsionnel.txt", "Planning prévisionnel\n\nPhases : cadrage, conception, "
         "réalisation, recette, déploiement. Dates clés et dépendances entre les lots."),
    ],
    "changement": [
        ("Analyse d'impact.txt", "Analyse d'impact\n\nApplications et agences concernées, fenêtre "
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
    "analyse_impact": "Impact sur le core banking et les agences ; interruption planifiée hors "
    "heures ouvrées ; utilisateurs concernés : back-office et guichets.",
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
            [precedent or "", horodatage.isoformat(), "demo@afgbank.ml", module, action,
             module, reference, av or "", nv or "", ""]
        )
        await conn.execute(
            "INSERT INTO audit.journal (horodatage, acteur_email, module, action, cible_type, "
            " cible_id, ancienne_valeur, nouvelle_valeur, hash_precedent, hash_courant) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8::jsonb,$9,$10)",
            horodatage, "demo@afgbank.ml", module, action, module, reference,
            av, nv, precedent, hash_courant,
        )
        # Séjours vraisemblables : parts inégales du parcours, jamais nulles.
        horodatage = horodatage + timedelta(
            seconds=duree / len(chemin) * random.uniform(0.4, 1.6)
        )


async def _reset(conn: asyncpg.Connection) -> None:
    """Vide toutes les données transactionnelles + utilisateurs de démo (dev only)."""
    await conn.execute("DELETE FROM core.activite")  # cascade : tache, document, commentaire, acteur
    await conn.execute("DELETE FROM core.notification")
    await conn.execute("DELETE FROM core.demandeur")
    await conn.execute("DELETE FROM core.utilisateur WHERE email = ANY($1::text[])", EMAILS_DEMO)
    # Le journal réel est append-only (déclencheur) ; les entrées de démo, elles, se régénèrent
    # avec le reste — on suspend le déclencheur le temps de la purge, ce que seul cet outil de
    # dev se permet. La chaîne d'empreintes garde alors des trous — assumé : base de dev, la
    # démo est la seule à écrire sous cet acteur.
    await conn.execute("ALTER TABLE audit.journal DISABLE TRIGGER trg_journal_pas_de_delete")
    try:
        await conn.execute("DELETE FROM audit.journal WHERE acteur_email = 'demo@afgbank.ml'")
    finally:
        await conn.execute("ALTER TABLE audit.journal ENABLE TRIGGER trg_journal_pas_de_delete")


async def _assurer_utilisateurs(conn: asyncpg.Connection) -> list[str]:
    """L'équipe de la démo : les agents réels s'ils existent, des personnages sinon.

    Une démo à la DSI parle mieux avec les vrais noms de l'équipe. Mais les notifications
    partent aussi par e-mail : on **coupe le canal e-mail** de chaque agent embarqué —
    préférence par utilisateur, réversible depuis son profil — pour que les données fictives
    ne remplissent aucune boîte réelle. L'administrateur, lui, n'est jamais acteur de la démo.
    """
    equipe = [
        r["id"]
        for r in await conn.fetch(
            "SELECT u.id FROM core.utilisateur u JOIN core.profil p ON p.id = u.profil_id "
            "WHERE u.actif AND p.code <> 'ADMIN' ORDER BY u.nom, u.prenom"
        )
    ]
    if len(equipe) < 3:
        # Pas assez d'agents réels : on complète avec les personnages historiques.
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
        equipe = [
            r["id"]
            for r in await conn.fetch(
                "SELECT u.id FROM core.utilisateur u JOIN core.profil p ON p.id = u.profil_id "
                "WHERE u.actif AND p.code <> 'ADMIN' ORDER BY u.nom, u.prenom"
            )
        ]
    for uid in equipe:
        await conn.execute(
            "INSERT INTO core.preference_notification (utilisateur_id, email) "
            "VALUES ($1, false) ON CONFLICT (utilisateur_id) DO UPDATE SET email = false",
            uid,
        )
    return equipe


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
                        gestionnaire_nom = "Support DSI"
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
              f"commentaires, acteurs, notifications).")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(creer_donnees())
