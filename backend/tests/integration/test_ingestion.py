"""L'import quotidien est la source de vérité des incidents et des demandes.

Ces tickets sont traités dans un autre système. DSI 360 les reflète pour en suivre l'évolution et
en tirer des statistiques — il n'y agit pas. Chaque import réaligne donc le ticket sur le fichier :
statut, priorité, catégorie, et **gestionnaire**.

Le gestionnaire du fichier est rapproché d'un compte DSI par son nom. S'il n'en est pas un, c'est
DBS : le ticket n'a pas de responsable dans notre système, et il est au niveau 3.

Aucun compte n'est jamais créé par l'import.
"""

from io import BytesIO
from typing import Any

from httpx import AsyncClient
from openpyxl import Workbook
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.ingestion import importer_tickets
from tests.integration.conftest import creer_utilisateur

ENTETES = [
    "Type d'enregistrement de service",
    "Statut",
    "#",
    "Catégorie",
    "Sous-catégorie",
    "Titre",
    "Demandeur",
    "Gestionnaire de processus",
    "Priorité",
    "Date de la demande",
    "Date de fermeture",
    "Time to repair",
    "Time to respond",
]


def _classeur(lignes: list[dict[str, Any]]) -> bytes:
    """Un classeur au format du rapport quotidien."""
    wb = Workbook()
    ws = wb.active
    ws.append(ENTETES)
    for ligne in lignes:
        ws.append(
            [
                ligne.get("type", "Incident"),
                ligne.get("statut", "Open"),
                ligne["numero"],
                ligne.get("categorie", "Réseau"),
                ligne.get("sous_categorie", ""),
                ligne.get("titre", "Panne de test"),
                ligne.get("demandeur", "Agent Métier"),
                ligne.get("gestionnaire", ""),
                ligne.get("priorite", "P3"),
                ligne.get("date_demande", "01-07-2026 09:00"),
                ligne.get("date_fermeture", ""),
                ligne.get("ttr", ""),
                ligne.get("ttrespond", ""),
            ]
        )
    tampon = BytesIO()
    wb.save(tampon)
    return tampon.getvalue()


async def _acteur(session: AsyncSession, email: str) -> dict[str, Any]:
    uid = await creer_utilisateur(session, email=email, profil="ADMIN")
    return {"id": uid, "email": email}


async def _activite(session: AsyncSession, reference: str) -> Any:
    return (
        await session.execute(
            text(
                "SELECT statut, priorite, responsable_id::text AS responsable_id, donnees "
                "FROM core.activite WHERE reference = :r"
            ),
            {"r": reference},
        )
    ).mappings().one()


# --- Rapprochement du gestionnaire ---------------------------------------------------------------


async def test_un_gestionnaire_connu_est_rattache_a_son_compte(session: AsyncSession) -> None:
    uid = await creer_utilisateur(session, email="oumar.sanogo@afgbank.ml")
    await session.execute(
        text(
            "UPDATE core.utilisateur SET prenom = 'Oumar', nom = 'Sanogo' "
            "WHERE id = cast(:i as uuid)"
        ),
        {"i": uid},
    )
    await session.commit()
    acteur = await _acteur(session, "admin.ing1@afgbank.ml")

    await importer_tickets(
        session, _classeur([{"numero": "10001", "gestionnaire": "Oumar Sanogo"}]), acteur
    )

    a = await _activite(session, "INC-10001")
    assert a["responsable_id"] == uid


async def test_un_gestionnaire_inconnu_signifie_dbs(session: AsyncSession) -> None:
    """Tout ce qui n'est pas nous est DBS : aucun responsable dans notre système."""
    acteur = await _acteur(session, "admin.ing2@afgbank.ml")

    await importer_tickets(
        session, _classeur([{"numero": "10002", "gestionnaire": "Jean Konaté"}]), acteur
    )

    a = await _activite(session, "INC-10002")
    assert a["responsable_id"] is None
    assert a["donnees"]["gestionnaire"] == "Jean Konaté", "le nom du rapport reste consultable"


async def test_l_import_ne_cree_jamais_de_compte(session: AsyncSession) -> None:
    """Les comptes sont créés par l'administrateur, avec leur niveau. Jamais par un fichier."""
    acteur = await _acteur(session, "admin.ing3@afgbank.ml")
    avant = await session.scalar(text("SELECT count(*) FROM core.utilisateur"))

    await importer_tickets(
        session, _classeur([{"numero": "10003", "gestionnaire": "Personne Inconnue"}]), acteur
    )

    assert await session.scalar(text("SELECT count(*) FROM core.utilisateur")) == avant


async def test_l_import_ne_fabrique_aucune_adresse_email(session: AsyncSession) -> None:
    acteur = await _acteur(session, "admin.ing4@afgbank.ml")

    await importer_tickets(
        session,
        _classeur([{"numero": "10004", "demandeur": "Fatou Diarra", "gestionnaire": "X Y"}]),
        acteur,
    )

    emails = await session.scalar(
        text("SELECT count(*) FROM core.demandeur WHERE email IS NOT NULL")
    )
    assert emails == 0, "un demandeur importé n'a pas d'e-mail inventé"


# --- Le fichier fait autorité --------------------------------------------------------------------


async def test_la_reimportation_realigne_le_gestionnaire(session: AsyncSession) -> None:
    """Le fichier décide. Une assignation faite dans la plateforme ne survit pas à l'import."""
    ancien = await creer_utilisateur(session, email="ancien.gest@afgbank.ml")
    nouveau = await creer_utilisateur(session, email="nouveau.gest@afgbank.ml")
    await session.execute(
        text("UPDATE core.utilisateur SET prenom='Ancien', nom='Gest' WHERE id=cast(:i as uuid)"),
        {"i": ancien},
    )
    await session.execute(
        text("UPDATE core.utilisateur SET prenom='Nouveau', nom='Gest' WHERE id=cast(:i as uuid)"),
        {"i": nouveau},
    )
    await session.commit()
    acteur = await _acteur(session, "admin.ing5@afgbank.ml")

    await importer_tickets(
        session, _classeur([{"numero": "10005", "gestionnaire": "Ancien Gest"}]), acteur
    )
    assert (await _activite(session, "INC-10005"))["responsable_id"] == ancien

    await importer_tickets(
        session, _classeur([{"numero": "10005", "gestionnaire": "Nouveau Gest"}]), acteur
    )
    assert (await _activite(session, "INC-10005"))["responsable_id"] == nouveau


async def test_un_ticket_qui_part_chez_dbs_perd_son_responsable(session: AsyncSession) -> None:
    connu = await creer_utilisateur(session, email="connu.gest@afgbank.ml")
    await session.execute(
        text("UPDATE core.utilisateur SET prenom='Connu', nom='Gest' WHERE id=cast(:i as uuid)"),
        {"i": connu},
    )
    await session.commit()
    acteur = await _acteur(session, "admin.ing6@afgbank.ml")

    await importer_tickets(
        session, _classeur([{"numero": "10006", "gestionnaire": "Connu Gest"}]), acteur
    )
    await importer_tickets(
        session, _classeur([{"numero": "10006", "gestionnaire": "Agent DBS"}]), acteur
    )

    assert (await _activite(session, "INC-10006"))["responsable_id"] is None


async def test_le_statut_suit_le_fichier(session: AsyncSession) -> None:
    acteur = await _acteur(session, "admin.ing7@afgbank.ml")

    await importer_tickets(session, _classeur([{"numero": "10007", "statut": "New"}]), acteur)
    assert (await _activite(session, "INC-10007"))["statut"] == "Nouveau"

    await importer_tickets(session, _classeur([{"numero": "10007", "statut": "Open"}]), acteur)
    assert (await _activite(session, "INC-10007"))["statut"] == "Ouvert"


# --- Le cycle de vie est journalisé --------------------------------------------------------------


async def _transitions(session: AsyncSession, reference: str) -> list[Any]:
    """Le parcours d'états, tel que le reconstruit `audit.historique_statuts`."""
    lignes = (
        await session.execute(
            text(
                "SELECT action, ancienne_valeur, nouvelle_valeur FROM audit.journal "
                "WHERE action IN ('CREATION', 'TRANSITION') AND cible_id = :r ORDER BY id"
            ),
            {"r": reference},
        )
    ).mappings().all()
    return [dict(x) for x in lignes]


async def test_un_changement_d_etat_venu_de_l_import_est_journalise(
    session: AsyncSession,
) -> None:
    """Sans cela, l'historique d'un ticket importé reste vide : son parcours est invisible."""
    acteur = await _acteur(session, "admin.ing8@afgbank.ml")

    await importer_tickets(session, _classeur([{"numero": "10008", "statut": "New"}]), acteur)
    await importer_tickets(session, _classeur([{"numero": "10008", "statut": "Open"}]), acteur)
    await importer_tickets(
        session,
        _classeur(
            [{"numero": "10008", "statut": "Closed", "date_fermeture": "02-07-2026 10:00"}]
        ),
        acteur,
    )

    traces = await _transitions(session, "INC-10008")
    assert len(traces) == 3, "création + deux changements d'état"
    assert traces[0]["nouvelle_valeur"]["statut"] == "Nouveau"
    assert traces[1]["ancienne_valeur"]["statut"] == "Nouveau"
    assert traces[1]["nouvelle_valeur"]["statut"] == "Ouvert"
    assert traces[2]["nouvelle_valeur"]["statut"] == "Clôturé"


async def test_un_import_sans_changement_ne_journalise_rien(session: AsyncSession) -> None:
    """Le rapport est réimporté chaque jour : on ne consigne que ce qui bouge."""
    acteur = await _acteur(session, "admin.ing9@afgbank.ml")

    await importer_tickets(session, _classeur([{"numero": "10009", "statut": "Open"}]), acteur)
    avant = len(await _transitions(session, "INC-10009"))
    await importer_tickets(session, _classeur([{"numero": "10009", "statut": "Open"}]), acteur)

    assert len(await _transitions(session, "INC-10009")) == avant


async def test_l_historique_de_la_fiche_se_remplit(
    client: AsyncClient, session: AsyncSession
) -> None:
    from tests.integration.conftest import entetes

    acteur = await _acteur(session, "admin.ing10@afgbank.ml")
    await importer_tickets(session, _classeur([{"numero": "10010", "statut": "New"}]), acteur)
    await importer_tickets(session, _classeur([{"numero": "10010", "statut": "Open"}]), acteur)
    ident = await session.scalar(
        text("SELECT id::text FROM core.activite WHERE reference = 'INC-10010'")
    )

    r = await client.get(f"/incidents/{ident}", headers=entetes(acteur["id"]))

    assert r.status_code == 200, r.text
    assert [e["statut"] for e in r.json()["historique"]] == ["Nouveau", "Ouvert"]
