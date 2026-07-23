"""Campagnes d'inventaire (lot 3) : recenser, constater, clôturer.

Ce que la clôture doit garantir : tout matériel actif jamais recensé ressort en « non
retrouvé » — c'est le résultat le plus précieux de l'exercice, celui que la Direction lit.
"""

from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.import_equipements import importer_classeur
from tests.integration.conftest import creer_utilisateur, entetes
from tests.integration.test_import_equipements import _classeur, _ligne


async def _admin(session: AsyncSession, email: str) -> str:
    return await creer_utilisateur(session, email=email, profil="ADMIN")


async def _equipement(client: AsyncClient, uid: str, designation: str) -> str:
    r = await client.post("/inventaire", json={"designation": designation}, headers=entetes(uid))
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def _ouvrir(client: AsyncClient, uid: str, libelle: str) -> dict[str, Any]:
    r = await client.post("/inventaire/campagnes", json={"libelle": libelle}, headers=entetes(uid))
    assert r.status_code == 201, r.text
    return dict(r.json())


async def test_plusieurs_inventaires_cohabitent(
    client: AsyncClient, session: AsyncSession
) -> None:
    """On lance un inventaire sans avoir à clore le précédent : les deux se relisent.

    L'ancienne règle (une seule campagne ouverte, à clôturer avant la suivante) ajoutait un
    cycle de vie que le besoin ne réclamait pas — relever l'état du parc, c'est tout.
    """
    admin = await _admin(session, "admin.camp1@afgbank.ml")

    premier = await _ouvrir(client, admin, "Inventaire camp1 A")
    second = await _ouvrir(client, admin, "Inventaire camp1 B")

    liste = (await client.get("/inventaire/campagnes", headers=entetes(admin))).json()
    ids = [c["id"] for c in liste["campagnes"]]
    assert premier["id"] in ids and second["id"] in ids
    # La liste arrive du plus récent au plus ancien : le dernier lancé se remplit.
    assert ids.index(second["id"]) < ids.index(premier["id"])


async def test_le_recensement_est_un_travail_d_equipe(
    client: AsyncClient, session: AsyncSession
) -> None:
    """L'admin lance l'inventaire ; **tout agent du module** y pose des constats (ADR-0003)."""
    admin = await _admin(session, "admin.camp2@afgbank.ml")
    agent = await creer_utilisateur(session, email="agent.camp2@afgbank.ml")
    equipement = await _equipement(client, admin, "Poste recensé")
    campagne = await _ouvrir(client, admin, "Recensement partagé")

    # L'agent ne lance pas d'inventaire…
    refus = await client.post(
        "/inventaire/campagnes", json={"libelle": "Tentative"}, headers=entetes(agent)
    )
    assert refus.status_code == 403

    # …mais il constate, et peut se raviser (re-poser remplace, retirer efface).
    ok = await client.put(
        f"/inventaire/campagnes/{campagne['id']}/constats/{equipement}",
        json={"etat": "BON", "justification": "Vu au bureau 214, en service"},
        headers=entetes(agent),
    )
    assert ok.status_code == 204, ok.text
    change = await client.put(
        f"/inventaire/campagnes/{campagne['id']}/constats/{equipement}",
        json={"etat": "CASSE", "justification": "Écran fêlé, ne démarre plus"},
        headers=entetes(agent),
    )
    assert change.status_code == 204

    lignes = (
        await client.get(
            f"/inventaire/campagnes/{campagne['id']}/recensement", headers=entetes(agent)
        )
    ).json()
    constate = next(x for x in lignes if x["id"] == equipement)
    assert constate["etat"] == "CASSE", "le dernier constat remplace le précédent"
    assert constate["constate_par"] is not None
    # Se raviser, c'est aussi dire pourquoi : le motif suit le constat.
    assert constate["justification"] == "Écran fêlé, ne démarre plus"

    retire = await client.delete(
        f"/inventaire/campagnes/{campagne['id']}/constats/{equipement}",
        headers=entetes(agent),
    )
    assert retire.status_code == 204


async def test_seuls_les_trois_constats_du_terrain_se_saisissent(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Bon, rebut, cassé : ce qu'un agent voit. « Non retrouvé » ne se coche pas.

    Un matériel qu'on n'a pas vu n'est pas un constat, c'est une absence de constat — la
    ligne reste vide, et le compteur « à recenser » la porte.
    """
    admin = await _admin(session, "admin.camp3@afgbank.ml")
    equipement = await _equipement(client, admin, "Matériel discret")
    campagne = await _ouvrir(client, admin, "Constats stricts")

    refus = await client.put(
        f"/inventaire/campagnes/{campagne['id']}/constats/{equipement}",
        json={"etat": "NON_RETROUVE", "justification": "Introuvable"},
        headers=entetes(admin),
    )
    assert refus.status_code == 422, refus.text


async def test_un_constat_sans_motif_est_refuse(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Cliquer « Rebut » engage : sans un mot sur ce qui a été vu, le constat ne prouve rien."""
    admin = await _admin(session, "admin.camp4@afgbank.ml")
    equipement = await _equipement(client, admin, "Serveur à justifier")
    campagne = await _ouvrir(client, admin, "Inventaire motivé")

    sans_motif = await client.put(
        f"/inventaire/campagnes/{campagne['id']}/constats/{equipement}",
        json={"etat": "REBUT"},
        headers=entetes(admin),
    )
    assert sans_motif.status_code == 422, sans_motif.text

    avec_motif = await client.put(
        f"/inventaire/campagnes/{campagne['id']}/constats/{equipement}",
        json={"etat": "REBUT", "justification": "Obsolète, pièces introuvables"},
        headers=entetes(admin),
    )
    assert avec_motif.status_code == 204, avec_motif.text


async def test_l_import_alimente_le_dernier_inventaire(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Les croix bon/rebut/casse du fichier rejoignent le dernier inventaire lancé."""
    admin_id = await _admin(session, "admin.camp5@afgbank.ml")
    acteur = {"id": admin_id, "email": "admin.camp5@afgbank.ml"}
    campagne = await _ouvrir(client, admin_id, "Inventaire alimenté par import")

    contenu = _classeur(
        [
            _ligne(**{"CODE IMMO": "INF90001", "Designtion": "GAB constaté", "Etat bon": "X"}),
            _ligne(**{"CODE IMMO": "INF90002", "Designtion": "Onduleur cassé", "Casse": "X"}),
            _ligne(**{"CODE IMMO": "INF90003", "Designtion": "Switch sans état"}),
        ]
    )
    rapport = await importer_classeur(session, contenu, acteur)

    assert rapport["constats_enregistres"] == 2
    lignes = (
        await client.get(
            f"/inventaire/campagnes/{campagne['id']}/recensement", headers=entetes(admin_id)
        )
    ).json()
    par_code = {x["code_immo"]: x["etat"] for x in lignes if x["code_immo"]}
    assert par_code["INF90001"] == "BON"
    assert par_code["INF90002"] == "CASSE"
    assert par_code["INF90003"] is None, "sans croix, pas de constat inventé"
    # Personne n'a cliqué : le motif dit d'où vient le constat, plutôt que d'imiter le terrain.
    motifs = {x["code_immo"]: x["justification"] for x in lignes if x["code_immo"]}
    assert motifs["INF90001"] == "Coché dans le fichier d'inventaire importé"
