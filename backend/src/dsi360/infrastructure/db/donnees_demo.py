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
DOC_TXT = b"Note de demonstration DSI 360.\nContenu simule pour les tests (apercu, renommage).\n"

# Jalons de projet (dates clés) — cf. module Projets.
JALONS_TITRES = [
    "Cadrage validé", "Lancement officiel", "Fin de la recette", "Go-live",
    "Bilan de clôture",
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
    conn: asyncpg.Connection, activite_id: str, email: str, nb: int
) -> None:
    for i in range(nb):
        await conn.execute(
            "INSERT INTO core.document "
            "(activite_id, nom, type_mime, taille, contenu, depose_par) "
            "VALUES ($1,$2,'text/plain',$3,$4,$5)",
            activite_id, f"note-demo-{i + 1}.txt", len(DOC_TXT), DOC_TXT, email,
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
    if get_settings().environnement != "dev":
        print("REFUS : les données de démonstration ne sont créées qu'en environnement 'dev'.")
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

                activite_id = await conn.fetchval(
                    "INSERT INTO core.activite"
                    "(reference, module, titre, description, direction_id, categorie_id, "
                    " responsable_id, demandeur_externe_id, impact, urgence, priorite, statut, "
                    " source, source_id, sla_prise_en_charge_le, sla_resolution_le, cree_le, "
                    " resolu_le, cloture_le, donnees)"
                    " VALUES ($1,$2,$3,$4,"
                    " (SELECT id FROM core.direction WHERE code=$5),"
                    " $6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20::jsonb) "
                    "RETURNING id",
                    reference, module, titre, "Donnée de démonstration.",
                    random.choice(directions),
                    random.choice(cats) if cats and module != "projet" else None,
                    responsable, demandeur_id,
                    impact if module != "projet" else None,
                    urgence if module != "projet" else None,
                    priorite, statut, source, source_id,
                    sla_pc, sla_res, cree_le, resolu, cloture, json.dumps(donnees),
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
                    await _pieces_jointes(conn, activite_id, EMAILS_DEMO[0], random.randint(0, 2))

                # Jalons (dates clés) sur les projets.
                if module == "projet":
                    await _jalons(conn, activite_id, cree_le, statut)

                # Commentaires + contributeurs/valideurs sur un échantillon.
                if random.random() < 0.6:
                    await _commentaires(
                        conn, activite_id, utilisateurs, cree_le, random.randint(1, 3), module
                    )
                if responsable is not None and random.random() < 0.5:
                    await _acteurs(conn, activite_id, utilisateurs, responsable, statut, module)

        # Quelques notifications pour peupler la cloche.
        activites_recentes = await conn.fetch(
            "SELECT id FROM core.activite ORDER BY cree_le DESC LIMIT 8"
        )
        for r in activites_recentes:
            await conn.execute(
                "INSERT INTO core.notification (destinataire_id, activite_id, type, titre, message) "
                "VALUES ($1,$2,$3,$4,$5)",
                random.choice(utilisateurs), r["id"],
                random.choice(["ASSIGNATION", "SLA_APPROCHE"]),
                "Notification de démonstration", "Action requise sur une activité.",
            )

        print(f"Données de démonstration recréées : {total} activités (+ tâches, documents, "
              f"commentaires, acteurs, notifications).")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(creer_donnees())
