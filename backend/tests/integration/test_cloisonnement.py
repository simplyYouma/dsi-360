"""Cloisonnement par direction : un profil non transverse ne voit que son périmètre.

Règle de référence : ``activites_communs._visible`` — un non-transverse voit une activité si elle
n'a pas de direction, ou si c'est la sienne. Les profils transverses (ADMIN, DSI, DG) voient tout.

Ce cloisonnement s'applique en **liste** comme en **détail** : une activité hors périmètre est
introuvable (404), jamais « visible mais interdite ».
"""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_utilisateur, entetes


async def _creer_incident(
    session: AsyncSession, *, reference: str, direction: str | None
) -> str:
    """Insère un incident rattaché (ou non) à une direction ; renvoie son identifiant."""
    params: dict[str, Any] = {"reference": reference, "direction": direction}
    ident = await session.scalar(
        text(
            "INSERT INTO core.activite "
            "(reference, module, titre, statut, priorite, impact, urgence, direction_id) "
            "VALUES (:reference, 'incident', 'Incident de test', 'Nouveau', 3, 3, 3, "
            "        (SELECT id FROM core.direction WHERE code = :direction)) "
            "RETURNING id::text"
        ),
        params,
    )
    await session.commit()
    return str(ident)


async def test_gestionnaire_ne_voit_pas_le_detail_hors_de_sa_direction(
    client: AsyncClient, session: AsyncSession
) -> None:
    incident_dbs = await _creer_incident(session, reference="INC-TEST-0001", direction="DBS")
    uid = await creer_utilisateur(session, email="dsi.cloison@afgbank.ml", direction="DSI")

    r = await client.get(f"/incidents/{incident_dbs}", headers=entetes(uid))

    assert r.status_code == 404, "une activité hors périmètre doit être introuvable, pas interdite"


async def test_gestionnaire_voit_le_detail_de_sa_direction(
    client: AsyncClient, session: AsyncSession
) -> None:
    incident_dsi = await _creer_incident(session, reference="INC-TEST-0002", direction="DSI")
    uid = await creer_utilisateur(session, email="dsi.cloison2@afgbank.ml", direction="DSI")

    r = await client.get(f"/incidents/{incident_dsi}", headers=entetes(uid))

    assert r.status_code == 200, r.text
    assert r.json()["reference"] == "INC-TEST-0002"


async def test_activite_sans_direction_visible_par_tous(
    client: AsyncClient, session: AsyncSession
) -> None:
    orpheline = await _creer_incident(session, reference="INC-TEST-0003", direction=None)
    uid = await creer_utilisateur(session, email="dbs.cloison@afgbank.ml", direction="DBS")

    r = await client.get(f"/incidents/{orpheline}", headers=entetes(uid))

    assert r.status_code == 200, r.text


async def test_profil_transverse_voit_toutes_les_directions(
    client: AsyncClient, session: AsyncSession
) -> None:
    incident_dbs = await _creer_incident(session, reference="INC-TEST-0004", direction="DBS")
    uid = await creer_utilisateur(
        session, email="dsi.transverse@afgbank.ml", profil="DSI", direction="DSI"
    )

    r = await client.get(f"/incidents/{incident_dbs}", headers=entetes(uid))

    assert r.status_code == 200, r.text


async def test_la_liste_masque_les_activites_hors_perimetre(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _creer_incident(session, reference="INC-TEST-0005", direction="DBS")
    await _creer_incident(session, reference="INC-TEST-0006", direction="DSI")
    uid = await creer_utilisateur(session, email="dsi.liste@afgbank.ml", direction="DSI")

    r = await client.get("/incidents", headers=entetes(uid))

    assert r.status_code == 200, r.text
    references = {a["reference"] for a in r.json()["elements"]}
    assert "INC-TEST-0006" in references
    assert "INC-TEST-0005" not in references, "fuite : un incident d'une autre direction est listé"


async def test_la_liste_d_un_transverse_montre_les_deux_directions(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _creer_incident(session, reference="INC-TEST-0007", direction="DBS")
    await _creer_incident(session, reference="INC-TEST-0008", direction="DSI")
    uid = await creer_utilisateur(session, email="admin.liste@afgbank.ml", profil="ADMIN")

    r = await client.get("/incidents", headers=entetes(uid))

    assert r.status_code == 200, r.text
    references = {a["reference"] for a in r.json()["elements"]}
    assert {"INC-TEST-0007", "INC-TEST-0008"} <= references
