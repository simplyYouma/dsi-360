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
from dsi360.domain.etats import GATES_VALIDATION
from dsi360.domain.sla import CiblesSla, echeances
from dsi360.infrastructure.securite import hacher_mot_de_passe

random.seed(42)

# Tous les utilisateurs du système sont de la DSI (les autres noms des fichiers importés — DBS —
# ne deviennent pas des comptes).
UTILISATEURS = [
    ("a.toure@afgbank.ml", "Touré", "Aïcha", "DSI", "DSI"),
    ("m.diallo@afgbank.ml", "Diallo", "Moussa", "GESTIONNAIRE", "DSI"),
    ("f.keita@afgbank.ml", "Keïta", "Fanta", "GESTIONNAIRE", "DSI"),
    ("o.sanogo@afgbank.ml", "Sanogo", "Oumar", "GESTIONNAIRE", "DSI"),
    ("k.coulibaly@afgbank.ml", "Coulibaly", "Kadia", "GESTIONNAIRE", "DSI"),
    ("s.traore@afgbank.ml", "Traoré", "Salif", "DG", "DSI"),
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
COMMENTAIRES = [
    "Prise en charge, analyse en cours.", "En attente d'un retour du prestataire.",
    "Point d'avancement fait en réunion d'équipe.", "Correctif appliqué, à confirmer côté métier.",
    "Escaladé au support niveau 2.", "Validé par le responsable, on peut clôturer.",
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


async def _reset(conn: asyncpg.Connection) -> None:
    """Vide toutes les données transactionnelles + utilisateurs de démo (dev only)."""
    await conn.execute("DELETE FROM core.activite")  # cascade : tache, document, commentaire, acteur
    await conn.execute("DELETE FROM core.notification")
    await conn.execute("DELETE FROM core.demandeur")
    await conn.execute("DELETE FROM core.utilisateur WHERE email = ANY($1::text[])", EMAILS_DEMO)


async def _assurer_utilisateurs(conn: asyncpg.Connection) -> list[str]:
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
    # Uniquement les comptes de démo : le compte admin (et tout autre compte réel) ne doit jamais
    # devenir acteur des données fictives, sinon l'ordonnanceur lui envoie de vrais e-mails.
    return [
        r["id"]
        for r in await conn.fetch(
            "SELECT id FROM core.utilisateur WHERE email = ANY($1::text[])", EMAILS_DEMO
        )
    ]


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
    conn: asyncpg.Connection, activite_id: str, utilisateurs: list[str], cree_le: datetime, nb: int
) -> None:
    for _ in range(nb):
        uid = random.choice(utilisateurs)
        email = await conn.fetchval("SELECT email FROM core.utilisateur WHERE id=$1", uid)
        await conn.execute(
            "INSERT INTO core.commentaire (activite_id, auteur_id, auteur_email, texte, cree_le) "
            "VALUES ($1,$2,$3,$4,$5)",
            activite_id, uid, email, random.choice(COMMENTAIRES),
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
            "VALUES ($1,$2,'CONTRIBUTEUR') ON CONFLICT DO NOTHING",
            activite_id, uid,
        )
    if len(autres) > 2:
        await conn.execute(
            "INSERT INTO core.activite_acteur (activite_id, utilisateur_id, role, decision) "
            "VALUES ($1,$2,'VALIDEUR',$3) ON CONFLICT DO NOTHING",
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
    """Affecte un niveau de support (N1/N2/N3) à quelques gestionnaires de démo, pour illustrer la
    réaffectation à l'escalade (le niveau est désormais porté par le gestionnaire)."""
    # Seuls les gestionnaires portent un niveau (les profils DSI/DG n'en ont pas).
    # indices GESTIONNAIRE : m.diallo/f.keita N1, o.sanogo N2, k.coulibaly N3.
    niveaux = {1: 1, 2: 1, 3: 2, 4: 3}
    for i, niveau in niveaux.items():
        if i < len(utilisateurs):
            await conn.execute(
                "UPDATE core.utilisateur SET niveau_support=$2 WHERE id=$1",
                utilisateurs[i], niveau,
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
                responsable = random.choice(utilisateurs)
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

                # Incidents/Demandes : simulés « importés » (source SD) avec TTR mesuré.
                if module in MODULES_IMPORTES:
                    source = "IMPORT_SD"
                    source_id = f"{seq:06d}"
                    cible = matrice.get(priorite or 3, CiblesSla(30, 480)).resolution_minutes
                    ttr = int(cible * random.choice([0.4, 0.7, 0.9, 1.3, 1.8]))  # sous/dépassement
                    donnees.update({"ttr_minutes": ttr, "gestionnaire": "Support DSI",
                                    "demandeur": "Agent AFG"})
                    if statut in TERMINAUX:
                        resolu = cree_le + timedelta(minutes=ttr)
                        cloture = resolu if statut.startswith("Clôtur") else None
                    # Escalade fonctionnelle N1→N2/N3 sur une partie des incidents (SI-12.01).
                    if module == "incident" and random.random() < 0.3:
                        donnees["niveau_support"] = random.choice([2, 2, 3])

                # Revue périodique (cybersécurité, gouvernance, risques) sur un échantillon.
                if module in MODULES_REVUE and random.random() < 0.6:
                    donnees["periodicite"] = random.choice(PERIODICITES)
                    donnees["prochaine_revue"] = (
                        maintenant + timedelta(days=random.randint(15, 120))
                    ).date().isoformat()

                # Échéances SLA depuis la matrice du module (activités « fiche »).
                if priorite is not None and module not in MODULES_IMPORTES:
                    ech = echeances(priorite, cree_le, matrice)
                    sla_pc, sla_res = ech.prise_en_charge_le, ech.resolution_le
                    if statut in TERMINAUX:
                        resolu = cree_le + timedelta(days=random.randint(1, 5))
                        cloture = resolu

                activite_id = await conn.fetchval(
                    "INSERT INTO core.activite"
                    "(reference, module, titre, description, direction_id, categorie_id, "
                    " responsable_id, impact, urgence, priorite, statut, source, source_id, "
                    " sla_prise_en_charge_le, sla_resolution_le, cree_le, resolu_le, cloture_le, donnees)"
                    " VALUES ($1,$2,$3,$4,"
                    " (SELECT id FROM core.direction WHERE code=$5),"
                    " $6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19::jsonb) RETURNING id",
                    reference, module, titre, "Donnée de démonstration.",
                    random.choice(directions),
                    random.choice(cats) if cats and module != "projet" else None,
                    responsable,
                    impact if module != "projet" else None,
                    urgence if module != "projet" else None,
                    priorite, statut, source, source_id,
                    sla_pc, sla_res, cree_le, resolu, cloture, json.dumps(donnees),
                )
                total += 1

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
                    await _commentaires(conn, activite_id, utilisateurs, cree_le, random.randint(1, 3))
                if random.random() < 0.5:
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
