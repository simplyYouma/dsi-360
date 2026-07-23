"""Le contrôle de terrain : ce qu'on a vu du matériel, daté et signé.

L'état constaté vit sur l'équipement, pas dans une campagne : bon, rebut ou cassé disent
déjà ce qu'il en est, et la date du dernier contrôle dit ce qu'il reste à faire — « non
contrôlé depuis douze mois » remplace tout l'avancement d'un recensement.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_utilisateur, entetes


async def _equipement(client: AsyncClient, uid: str, designation: str) -> dict[str, Any]:
    r = await client.post("/inventaire", json={"designation": designation}, headers=entetes(uid))
    assert r.status_code == 201, r.text
    return dict(r.json())


async def test_constater_est_un_travail_de_terrain(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Tout agent du module constate, alors que le reste de la fiche est réservé à l'admin.

    Contrôler le parc, c'est aller voir ; ce n'est pas un privilège d'administrateur (ADR-0003).
    Ce que l'agent écrit reste une observation — sortir le matériel du parc, lui, décide.
    """
    admin = await creer_utilisateur(session, email="admin.cst1@afgbank.ml", profil="ADMIN")
    agent = await creer_utilisateur(session, email="agent.cst1@afgbank.ml")
    e = await _equipement(client, admin, "Poste contrôlé")

    r = await client.put(
        f"/inventaire/{e['id']}/constat",
        json={"etat": "CASSE", "justification": "Écran fêlé, ne démarre plus"},
        headers=entetes(agent),
    )

    assert r.status_code == 200, r.text
    d = r.json()
    assert d["etat_constate"] == "CASSE"
    assert d["constat_motif"] == "Écran fêlé, ne démarre plus"
    assert d["constate_par"] is not None and d["constate_le"] is not None
    # Constater ne sort pas le matériel du parc : observer n'est pas décider.
    assert d["actif"] is True

    # …mais l'agent ne modifie toujours pas la fiche.
    refus = await client.patch(
        f"/inventaire/{e['id']}", json={"modele": "Pirate"}, headers=entetes(agent)
    )
    assert refus.status_code == 403, refus.text


async def test_un_constat_sans_motif_est_refuse(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Cliquer « Rebut » engage : sans un mot sur ce qui a été vu, le constat ne prouve rien."""
    admin = await creer_utilisateur(session, email="admin.cst2@afgbank.ml", profil="ADMIN")
    e = await _equipement(client, admin, "Serveur à justifier")

    sans = await client.put(
        f"/inventaire/{e['id']}/constat", json={"etat": "REBUT"}, headers=entetes(admin)
    )
    assert sans.status_code == 422, sans.text

    avec = await client.put(
        f"/inventaire/{e['id']}/constat",
        json={"etat": "REBUT", "justification": "Obsolète, pièces introuvables"},
        headers=entetes(admin),
    )
    assert avec.status_code == 200, avec.text


async def test_le_constat_se_remplace_et_s_efface(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Se raviser, c'est aussi dire pourquoi ; effacer, non — ce n'est pas une observation."""
    admin = await creer_utilisateur(session, email="admin.cst3@afgbank.ml", profil="ADMIN")
    e = await _equipement(client, admin, "Matériel revu")

    await client.put(
        f"/inventaire/{e['id']}/constat",
        json={"etat": "BON", "justification": "Vu au bureau 214"},
        headers=entetes(admin),
    )
    remplace = await client.put(
        f"/inventaire/{e['id']}/constat",
        json={"etat": "REBUT", "justification": "Finalement hors service"},
        headers=entetes(admin),
    )
    assert remplace.json()["etat_constate"] == "REBUT"
    assert remplace.json()["constat_motif"] == "Finalement hors service"

    efface = await client.delete(f"/inventaire/{e['id']}/constat", headers=entetes(admin))
    assert efface.status_code == 200, efface.text
    assert efface.json()["etat_constate"] is None
    assert efface.json()["constate_le"] is None, "le matériel redevient « à contrôler »"


async def test_a_controler_repose_sur_la_date_du_dernier_controle(
    client: AsyncClient, session: AsyncSession
) -> None:
    """« À contrôler » n'est pas un état du matériel : c'est l'absence de contrôle récent.

    C'est ce que la campagne d'inventaire apportait — et cette information tient dans une date.
    """
    admin = await creer_utilisateur(session, email="admin.cst4@afgbank.ml", profil="ADMIN")
    jamais = await _equipement(client, admin, "Jamais contrôlé")
    ancien = await _equipement(client, admin, "Contrôlé il y a longtemps")
    recent = await _equipement(client, admin, "Contrôlé la semaine dernière")

    for e in (ancien, recent):
        await client.put(
            f"/inventaire/{e['id']}/constat",
            json={"etat": "BON", "justification": "Vu sur site"},
            headers=entetes(admin),
        )
    # On vieillit le contrôle de l'un : treize mois, c'est au-delà du délai.
    await session.execute(
        text("UPDATE core.equipement SET constate_le = :quand WHERE id = cast(:i as uuid)"),
        {"quand": datetime.now(UTC) - timedelta(days=395), "i": ancien["id"]},
    )
    await session.commit()

    r = await client.get("/inventaire?a_controler=true", headers=entetes(admin))

    assert r.status_code == 200, r.text
    ids = {e["id"] for e in r.json()["elements"]}
    assert jamais["id"] in ids, "jamais contrôlé : à voir en priorité"
    assert ancien["id"] in ids, "contrôlé il y a plus d'un an : à revoir"
    assert recent["id"] not in ids, "contrôlé récemment : rien à faire"


async def test_les_compteurs_disent_l_etat_du_parc(
    client: AsyncClient, session: AsyncSession
) -> None:
    """L'en-tête compte ce qui est constaté et ce qu'il reste à contrôler."""
    admin = await creer_utilisateur(session, email="admin.cst5@afgbank.ml", profil="ADMIN")
    e = await _equipement(client, admin, "Matériel compté")
    await client.put(
        f"/inventaire/{e['id']}/constat",
        json={"etat": "CASSE", "justification": "Boîtier écrasé"},
        headers=entetes(admin),
    )

    r = await client.get("/inventaire/stats", headers=entetes(admin))

    assert r.status_code == 200, r.text
    s = r.json()
    assert s["casses"] >= 1
    assert s["a_controler"] >= 0
