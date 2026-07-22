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


async def test_une_seule_campagne_ouverte_a_la_fois(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Deux campagnes ouvertes sèmeraient la confusion : où irait le constat ?"""
    admin = await _admin(session, "admin.camp1@afgbank.ml")
    await _ouvrir(client, admin, "Inventaire 2026")

    refus = await client.post(
        "/inventaire/campagnes", json={"libelle": "Doublon"}, headers=entetes(admin)
    )
    assert refus.status_code == 409, refus.text
    assert "déjà ouverte" in refus.json()["detail"]

    # On nettoie pour les autres tests : la contrainte est globale à la base.
    campagne = (await client.get("/inventaire/campagnes", headers=entetes(admin))).json()
    ouverte = next(c for c in campagne["campagnes"] if c["statut"] == "OUVERTE")
    await client.post(f"/inventaire/campagnes/{ouverte['id']}/cloture", headers=entetes(admin))


async def test_le_recensement_est_un_travail_d_equipe(
    client: AsyncClient, session: AsyncSession
) -> None:
    """L'admin ouvre et clôture ; **tout agent du module** pose des constats (ADR-0003)."""
    admin = await _admin(session, "admin.camp2@afgbank.ml")
    agent = await creer_utilisateur(session, email="agent.camp2@afgbank.ml")
    equipement = await _equipement(client, admin, "Poste recensé")
    campagne = await _ouvrir(client, admin, "Recensement partagé")

    # L'agent ne peut pas ouvrir…
    refus = await client.post(
        "/inventaire/campagnes", json={"libelle": "Tentative"}, headers=entetes(agent)
    )
    assert refus.status_code == 403

    # …mais il constate, et peut se raviser (re-poser remplace, retirer efface).
    ok = await client.put(
        f"/inventaire/campagnes/{campagne['id']}/constats/{equipement}",
        json={"etat": "BON"},
        headers=entetes(agent),
    )
    assert ok.status_code == 204, ok.text
    change = await client.put(
        f"/inventaire/campagnes/{campagne['id']}/constats/{equipement}",
        json={"etat": "CASSE"},
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

    retire = await client.delete(
        f"/inventaire/campagnes/{campagne['id']}/constats/{equipement}",
        headers=entetes(agent),
    )
    assert retire.status_code == 204
    await client.post(f"/inventaire/campagnes/{campagne['id']}/cloture", headers=entetes(admin))


async def test_non_retrouve_ne_se_saisit_pas(client: AsyncClient, session: AsyncSession) -> None:
    """« Non retrouvé » se déduit à la clôture : en campagne, c'est juste « pas encore vu »."""
    admin = await _admin(session, "admin.camp3@afgbank.ml")
    equipement = await _equipement(client, admin, "Matériel discret")
    campagne = await _ouvrir(client, admin, "Constats stricts")

    refus = await client.put(
        f"/inventaire/campagnes/{campagne['id']}/constats/{equipement}",
        json={"etat": "NON_RETROUVE"},
        headers=entetes(admin),
    )
    assert refus.status_code == 422, refus.text
    await client.post(f"/inventaire/campagnes/{campagne['id']}/cloture", headers=entetes(admin))


async def test_la_cloture_releve_les_non_retrouves(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Clôturer fige la campagne et marque « non retrouvé » tout actif jamais recensé."""
    admin = await _admin(session, "admin.camp4@afgbank.ml")
    vu = await _equipement(client, admin, "Serveur vu")
    disparu = await _equipement(client, admin, "Écran disparu")
    campagne = await _ouvrir(client, admin, "Clôture 2026")
    await client.put(
        f"/inventaire/campagnes/{campagne['id']}/constats/{vu}",
        json={"etat": "BON"},
        headers=entetes(admin),
    )

    cloture = await client.post(
        f"/inventaire/campagnes/{campagne['id']}/cloture", headers=entetes(admin)
    )

    assert cloture.status_code == 200, cloture.text
    r = cloture.json()
    assert r["non_retrouves"] >= 1, "l'écran disparu doit être relevé"
    assert r["campagne"]["statut"] == "CLOTUREE"
    lignes = (
        await client.get(
            f"/inventaire/campagnes/{campagne['id']}/recensement", headers=entetes(admin)
        )
    ).json()
    assert next(x for x in lignes if x["id"] == disparu)["etat"] == "NON_RETROUVE"
    assert next(x for x in lignes if x["id"] == vu)["etat"] == "BON"

    # Campagne figée : plus aucun constat n'y entre.
    fige = await client.put(
        f"/inventaire/campagnes/{campagne['id']}/constats/{vu}",
        json={"etat": "REBUT"},
        headers=entetes(admin),
    )
    assert fige.status_code == 409


async def test_l_import_alimente_la_campagne_ouverte(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Les croix bon/rebut/casse du fichier deviennent des constats si une campagne est ouverte."""
    admin_id = await _admin(session, "admin.camp5@afgbank.ml")
    acteur = {"id": admin_id, "email": "admin.camp5@afgbank.ml"}
    campagne = await _ouvrir(client, admin_id, "Campagne alimentée par import")

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
    await client.post(f"/inventaire/campagnes/{campagne['id']}/cloture", headers=entetes(admin_id))
