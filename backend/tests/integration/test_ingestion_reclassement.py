"""Requalification d'un ticket : le même ticket a changé de module à la source.

SysAid numérote incidents et demandes dans **la même série**. Requalifier un ticket n'en change ni
le numéro ni le contenu — mais notre unicité portait sur `(module, numéro)` : le ticket entrait une
seconde fois sous l'autre module, et deux fiches vivaient côte à côte pour une seule activité
réelle. L'ancienne restait figée au dernier état connu, la nouvelle n'avait ni commentaires ni
historique, et les statistiques comptaient deux activités.

Ces tests couvrent les deux situations, dont **celle du parc déjà en production** : les deux fiches
existent déjà, et c'est le prochain import qui doit remettre de l'ordre sans rien perdre.
"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.ingestion import importer_tickets
from dsi360.infrastructure import audit
from tests.integration.conftest import creer_utilisateur
from tests.integration.test_ingestion import _classeur


async def _acteur(session: AsyncSession, email: str) -> dict[str, Any]:
    uid = await creer_utilisateur(session, email=email, profil="ADMIN")
    return {"id": uid, "email": email}


async def _fiches(session: AsyncSession, numero: str) -> list[Any]:
    """Toutes les fiches portant ce numéro de ticket, tous modules confondus."""
    resultat = await session.execute(
        text(
            "SELECT id::text AS id, module, reference, statut, antecedents "
            "FROM core.activite WHERE source_id = :n ORDER BY module"
        ),
        {"n": numero},
    )
    return list(resultat.mappings().all())


async def _commenter(
    session: AsyncSession, activite_id: str, auteur: dict[str, Any], mot: str
) -> None:
    await session.execute(
        text(
            "INSERT INTO core.commentaire (activite_id, auteur_id, auteur_email, texte) "
            "VALUES (cast(:a as uuid), cast(:u as uuid), :e, :t)"
        ),
        {"a": activite_id, "u": auteur["id"], "e": auteur["email"], "t": mot},
    )


# --- Le cas nominal ------------------------------------------------------------------------------


async def test_un_incident_requalifie_en_demande_deplace_sa_fiche(session: AsyncSession) -> None:
    acteur = await _acteur(session, "admin.recl1@afgbank.ml")
    await importer_tickets(session, _classeur([{"numero": "20001", "type": "Incident"}]), acteur)
    avant = await _fiches(session, "20001")
    assert [f["reference"] for f in avant] == ["INC-20001"]

    rapport = await importer_tickets(
        session, _classeur([{"numero": "20001", "type": "Demande"}]), acteur
    )

    apres = await _fiches(session, "20001")
    # UNE seule fiche, du bon côté : le ticket n'a pas été dupliqué.
    assert [(f["module"], f["reference"]) for f in apres] == [("demande", "DEM-20001")]
    # Et c'est bien la MÊME fiche : son identifiant n'a pas changé, rien n'a été recréé.
    assert apres[0]["id"] == avant[0]["id"]
    assert rapport["reclasses"] == 1
    assert rapport["doublons_fusionnes"] == 0


async def test_la_fiche_requalifiee_garde_ce_qu_on_y_avait_ecrit(session: AsyncSession) -> None:
    acteur = await _acteur(session, "admin.recl2@afgbank.ml")
    await importer_tickets(session, _classeur([{"numero": "20002", "type": "Incident"}]), acteur)
    fiche = (await _fiches(session, "20002"))[0]
    await _commenter(session, fiche["id"], acteur, "Relancé le prestataire")
    await session.commit()

    await importer_tickets(
        session, _classeur([{"numero": "20002", "type": "Demande"}]), acteur
    )

    apres = (await _fiches(session, "20002"))[0]
    reste = await session.scalar(
        text("SELECT count(*) FROM core.commentaire WHERE activite_id = cast(:a as uuid)"),
        {"a": apres["id"]},
    )
    assert reste == 1, "le commentaire doit suivre la fiche déplacée"
    # L'identité précédente est mémorisée : le journal est append-only, ses écritures d'avant
    # portent encore INC-20002.
    antecedents = apres["antecedents"]
    assert len(antecedents) == 1
    assert antecedents[0]["module"] == "incident"
    assert antecedents[0]["reference"] == "INC-20002"


async def test_l_historique_survit_a_la_requalification(session: AsyncSession) -> None:
    acteur = await _acteur(session, "admin.recl3@afgbank.ml")
    await importer_tickets(session, _classeur([{"numero": "20003", "type": "Incident"}]), acteur)
    await importer_tickets(
        session, _classeur([{"numero": "20003", "type": "Demande"}]), acteur
    )
    fiche = (await _fiches(session, "20003"))[0]

    # Sans les antécédents, la création (journalisée sous « incident / INC-20003 ») serait perdue :
    # la fiche paraîtrait née le jour de sa requalification.
    sans = await audit.historique_statuts(session, "demande", "DEM-20003")
    avec = await audit.historique_statuts(
        session, "demande", "DEM-20003", antecedents=fiche["antecedents"]
    )
    # L'entrée manquante est la création, écrite sous l'ancienne identité : sans les antécédents,
    # la fiche paraîtrait née le jour où elle a changé de module.
    assert len(avec) == len(sans) + 1
    assert avec[0]["horodatage"] <= sans[0]["horodatage"]

    journal = await audit.journal_complet(
        session, "demande", "DEM-20003", antecedents=fiche["antecedents"]
    )
    assert any(e["action"] == "RECLASSEMENT" for e in journal)
    assert any(e["cible_id"] == "INC-20003" for e in journal), "l'avant doit rester visible"


# --- Le cas du parc en production ----------------------------------------------------------------


async def test_le_doublon_deja_en_base_est_fusionne_et_non_duplique(session: AsyncSession) -> None:
    """Les deux fiches existent déjà : c'est l'état du serveur aujourd'hui."""
    acteur = await _acteur(session, "admin.recl4@afgbank.ml")
    # Jour 1 : le ticket arrive en incident, et quelqu'un l'annote.
    await importer_tickets(session, _classeur([{"numero": "20004", "type": "Incident"}]), acteur)
    origine = (await _fiches(session, "20004"))[0]
    await _commenter(session, origine["id"], acteur, "Analyse initiale")
    # Jour 2, AVANT le correctif : l'import créait une seconde fiche en demande. On la fabrique à
    # la main pour reproduire exactement ce qu'il y a en base.
    doublon = await session.scalar(
        text(
            "INSERT INTO core.activite (reference, module, titre, statut, source, source_id) "
            "VALUES ('DEM-20004', 'demande', 'Panne de test', 'Nouveau', 'IMPORT_SD', '20004') "
            "RETURNING id::text"
        )
    )
    await _commenter(session, str(doublon), acteur, "Vu avec le métier")
    await session.commit()
    assert len(await _fiches(session, "20004")) == 2

    # Jour 3 : l'import suivant remet de l'ordre, tout seul.
    rapport = await importer_tickets(
        session, _classeur([{"numero": "20004", "type": "Demande"}]), acteur
    )

    apres = await _fiches(session, "20004")
    assert [(f["module"], f["reference"]) for f in apres] == [("demande", "DEM-20004")]
    assert apres[0]["id"] == origine["id"], "la fiche d'origine est celle que l'on garde"
    assert rapport["reclasses"] == 1
    assert rapport["doublons_fusionnes"] == 1
    assert rapport["doublons_restants"] == 0
    # Les DEUX commentaires sont là : la suppression en cascade n'a rien emporté.
    contenus = list(
        (
            await session.execute(
                text(
                    "SELECT texte FROM core.commentaire "
                    "WHERE activite_id = cast(:a as uuid) ORDER BY texte"
                ),
                {"a": apres[0]["id"]},
            )
        ).scalars()
    )
    assert contenus == ["Analyse initiale", "Vu avec le métier"]


async def test_un_doublon_absent_du_rapport_est_compte_pas_devine(session: AsyncSession) -> None:
    """Sans le ticket dans le rapport, rien ne dit lequel des deux modules est le bon."""
    acteur = await _acteur(session, "admin.recl7@afgbank.ml")
    await importer_tickets(session, _classeur([{"numero": "20007", "type": "Incident"}]), acteur)
    await session.execute(
        text(
            "INSERT INTO core.activite (reference, module, titre, statut, source, source_id) "
            "VALUES ('DEM-20007', 'demande', 'Panne de test', 'Nouveau', 'IMPORT_SD', '20007')"
        )
    )
    await session.commit()

    # Un rapport qui parle d'un AUTRE ticket : le doublon reste, et doit être signalé.
    rapport = await importer_tickets(
        session, _classeur([{"numero": "20008", "type": "Incident"}]), acteur
    )

    assert rapport["reclasses"] == 0
    assert rapport["doublons_restants"] >= 1
    assert len(await _fiches(session, "20007")) == 2, "on ne tranche pas au hasard"


# --- Ce qui ne doit surtout pas se déclencher -----------------------------------------------------


async def test_le_ticket_requalifie_reprend_les_donnees_du_rapport(session: AsyncSession) -> None:
    """Déplacer ne suffit pas : la fiche porte l'état du jour, et une catégorie du bon module."""
    acteur = await _acteur(session, "admin.recl5@afgbank.ml")
    await importer_tickets(
        session,
        _classeur([{"numero": "20005", "type": "Incident", "categorie": "Réseau"}]),
        acteur,
    )
    await importer_tickets(
        session,
        _classeur(
            [
                {
                    "numero": "20005",
                    "type": "Demande",
                    "categorie": "Habilitation",
                    "statut": "Closed",
                    "date_fermeture": "05-07-2026 10:00",
                }
            ]
        ),
        acteur,
    )

    ligne = (
        await session.execute(
            text(
                "SELECT a.statut, a.module, a.cloture_le, c.libelle AS categorie, "
                "       c.module AS module_categorie "
                "FROM core.activite a LEFT JOIN core.categorie c ON c.id = a.categorie_id "
                "WHERE a.source_id = '20005'"
            )
        )
    ).mappings().one()
    assert ligne["module"] == "demande"
    assert ligne["categorie"] == "Habilitation"
    # La catégorie appartient à un module (core.categorie est indexée sur (module, code)) : garder
    # celle de l'incident ferait pointer une demande vers une catégorie qui n'est pas la sienne.
    assert ligne["module_categorie"] == "demande"
    assert ligne["cloture_le"] is not None, "l'état du rapport doit être repris"


async def test_un_ticket_qui_ne_bouge_pas_n_est_pas_requalifie(session: AsyncSession) -> None:
    """Le rapport est rechargé chaque jour : le cas courant ne doit rien déclencher."""
    acteur = await _acteur(session, "admin.recl6@afgbank.ml")
    await importer_tickets(session, _classeur([{"numero": "20006", "type": "Incident"}]), acteur)
    rapport = await importer_tickets(
        session, _classeur([{"numero": "20006", "type": "Incident"}]), acteur
    )
    assert rapport["reclasses"] == 0
    assert rapport["doublons_fusionnes"] == 0
    assert [f["reference"] for f in await _fiches(session, "20006")] == ["INC-20006"]


async def test_un_aller_retour_ne_multiplie_pas_les_fiches(session: AsyncSession) -> None:
    """Incident -> demande -> incident : toujours une seule fiche, et deux antécédents."""
    acteur = await _acteur(session, "admin.recl8@afgbank.ml")
    await importer_tickets(session, _classeur([{"numero": "20009", "type": "Incident"}]), acteur)
    origine = (await _fiches(session, "20009"))[0]
    await importer_tickets(
        session, _classeur([{"numero": "20009", "type": "Demande"}]), acteur
    )
    await importer_tickets(session, _classeur([{"numero": "20009", "type": "Incident"}]), acteur)

    fiches = await _fiches(session, "20009")
    assert [(f["module"], f["reference"]) for f in fiches] == [("incident", "INC-20009")]
    assert fiches[0]["id"] == origine["id"]
    assert [a["reference"] for a in fiches[0]["antecedents"]] == ["INC-20009", "DEM-20009"]


async def test_le_doublon_du_mauvais_cote_est_absorbe_sans_perdre_l_originale(
    session: AsyncSession,
) -> None:
    """Le doublon est dans l'AUTRE module, et le rapport confirme le module d'origine.

    Ce cas a piégé une première version : la règle « garder la fiche qui n'est pas dans le module
    cible » conservait alors le doublon et supprimait l'originale. Rien n'était perdu, mais
    l'identifiant de l'activité changeait — le journal, les notifications déjà parties et les liens
    partagés pointaient dans le vide. On garde la PLUS ANCIENNE, quel que soit son module.
    """
    acteur = await _acteur(session, "admin.recl9@afgbank.ml")
    await importer_tickets(session, _classeur([{"numero": "20010", "type": "Incident"}]), acteur)
    origine = (await _fiches(session, "20010"))[0]
    await _commenter(session, origine["id"], acteur, "note d'origine")
    # Un import d'avant le correctif avait créé une demande en double pour ce même numéro.
    doublon = await session.scalar(
        text(
            "INSERT INTO core.activite (reference, module, titre, statut, source, source_id) "
            "VALUES ('DEM-20010', 'demande', 'Doublon', 'Nouveau', 'IMPORT_SD', '20010') "
            "RETURNING id::text"
        )
    )
    await _commenter(session, str(doublon), acteur, "note du doublon")
    await session.commit()

    # Le rapport dit : c'est toujours un incident.
    rapport = await importer_tickets(
        session, _classeur([{"numero": "20010", "type": "Incident"}]), acteur
    )

    apres = await _fiches(session, "20010")
    assert [(f["module"], f["reference"]) for f in apres] == [("incident", "INC-20010")]
    assert apres[0]["id"] == origine["id"], "l'originale est conservée, pas le doublon"
    # Pas de requalification : la fiche n'a pas changé de module, seul le doublon a été absorbé.
    assert rapport["reclasses"] == 0
    assert rapport["doublons_fusionnes"] == 1
    assert apres[0]["antecedents"] == []
    textes = list(
        (
            await session.execute(
                text(
                    "SELECT texte FROM core.commentaire "
                    "WHERE activite_id = cast(:a as uuid) ORDER BY texte"
                ),
                {"a": apres[0]["id"]},
            )
        ).scalars()
    )
    assert textes == ["note d'origine", "note du doublon"]
