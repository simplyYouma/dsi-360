"""Création, modification et suppression de profils depuis l'administration (ADR-0003 §1).

Les profils sont un paramétrage, pas un vocabulaire figé. Deux garde-fous, tous deux **côté
serveur** : on ne supprime pas un profil auquel des comptes sont rattachés, et on ne touche pas à
`ADMIN` — le supprimer, ou lui retirer son caractère transverse, fermerait la porte à clé de
l'intérieur.
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_utilisateur, entetes


async def _admin(session: AsyncSession, email: str) -> dict[str, str]:
    uid = await creer_utilisateur(session, email=email, profil="ADMIN")
    return entetes(uid)


# --- Création ------------------------------------------------------------------------------------


async def test_creer_un_profil(client: AsyncClient, session: AsyncSession) -> None:
    h = await _admin(session, "admin.creer@afgbank.ml")

    r = await client.post("/admin/profils", headers=h, json={"libelle": "Sécurité opérationnelle"})

    assert r.status_code == 201, r.text
    cree = r.json()
    assert cree["code"] == "SECURITE_OPERATIONNELLE"
    assert cree["libelle"] == "Sécurité opérationnelle"
    assert cree["transverse"] is False

    liste = await client.get("/admin/profils", headers=h)
    assert "SECURITE_OPERATIONNELLE" in {p["code"] for p in liste.json()}


async def test_creer_un_profil_transverse(client: AsyncClient, session: AsyncSession) -> None:
    h = await _admin(session, "admin.creertr@afgbank.ml")

    r = await client.post(
        "/admin/profils", headers=h, json={"libelle": "Pilotage", "transverse": True}
    )

    assert r.status_code == 201, r.text
    assert r.json()["transverse"] is True


async def test_creer_un_profil_au_libelle_deja_pris_refuse(
    client: AsyncClient, session: AsyncSession
) -> None:
    """« Administrateur » donnerait le code ADMINISTRATEUR, distinct d'ADMIN : deux profils au
    libellé identique dans la liste. Le libellé compte autant que le code."""
    h = await _admin(session, "admin.doublon@afgbank.ml")

    r = await client.post("/admin/profils", headers=h, json={"libelle": "Administrateur"})

    assert r.status_code == 409, r.text


async def test_creer_deux_fois_le_meme_profil_refuse(
    client: AsyncClient, session: AsyncSession
) -> None:
    h = await _admin(session, "admin.doublon2@afgbank.ml")
    assert (
        await client.post("/admin/profils", headers=h, json={"libelle": "Poste de travail"})
    ).status_code == 201

    r = await client.post("/admin/profils", headers=h, json={"libelle": "Poste de travail"})

    assert r.status_code == 409, r.text


async def test_renommer_vers_un_libelle_deja_pris_refuse(
    client: AsyncClient, session: AsyncSession
) -> None:
    h = await _admin(session, "admin.doublon3@afgbank.ml")

    r = await client.patch(
        "/admin/profils/SUPPORT_APP", headers=h, json={"libelle": "Réseau télécom"}
    )

    assert r.status_code == 409, r.text


async def test_renommer_un_profil_sans_changer_son_libelle_reste_permis(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le profil ne doit pas entrer en conflit avec lui-même (ex. bascule du seul `transverse`)."""
    h = await _admin(session, "admin.idem@afgbank.ml")

    r = await client.patch(
        "/admin/profils/SUPPORT_APP",
        headers=h,
        json={"libelle": "IT Support Applicatif", "transverse": True},
    )

    assert r.status_code == 200, r.text
    assert r.json()["transverse"] is True


async def test_creer_un_profil_au_libelle_vide_refuse(
    client: AsyncClient, session: AsyncSession
) -> None:
    h = await _admin(session, "admin.vide@afgbank.ml")

    r = await client.post("/admin/profils", headers=h, json={"libelle": "   "})

    assert r.status_code == 422, r.text


async def test_un_profil_cree_n_a_aucun_acces_par_defaut(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Sécurité par défaut : un nouveau profil n'ouvre rien tant qu'on ne lui a rien donné."""
    h = await _admin(session, "admin.acces@afgbank.ml")
    await client.post("/admin/profils", headers=h, json={"libelle": "Observateur"})

    matrice = (await client.get("/admin/acces", headers=h)).json()
    observateur = next(r for r in matrice["roles"] if r["profil"] == "OBSERVATEUR")

    assert observateur["acces"] == []


# --- Modification --------------------------------------------------------------------------------


async def test_renommer_un_profil(client: AsyncClient, session: AsyncSession) -> None:
    h = await _admin(session, "admin.renommer@afgbank.ml")

    r = await client.patch(
        "/admin/profils/RESEAU_TELECOM", headers=h, json={"libelle": "Réseau et télécoms"}
    )

    assert r.status_code == 200, r.text
    assert r.json()["libelle"] == "Réseau et télécoms"
    assert r.json()["code"] == "RESEAU_TELECOM", "le code technique ne bouge pas avec le libellé"


async def test_modifier_un_profil_inconnu(client: AsyncClient, session: AsyncSession) -> None:
    h = await _admin(session, "admin.inconnu@afgbank.ml")

    r = await client.patch("/admin/profils/FANTOME", headers=h, json={"libelle": "Fantôme"})

    assert r.status_code == 404


async def test_retirer_le_transverse_a_l_administrateur_refuse(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Anti-verrouillage : l'administrateur doit rester transverse."""
    h = await _admin(session, "admin.transv@afgbank.ml")

    r = await client.patch(
        "/admin/profils/ADMIN", headers=h, json={"libelle": "Administrateur", "transverse": False}
    )

    assert r.status_code == 409, r.text


# --- Suppression ---------------------------------------------------------------------------------


async def test_supprimer_un_profil_inutilise(client: AsyncClient, session: AsyncSession) -> None:
    h = await _admin(session, "admin.supp@afgbank.ml")
    await client.post("/admin/profils", headers=h, json={"libelle": "Temporaire"})

    r = await client.delete("/admin/profils/TEMPORAIRE", headers=h)

    assert r.status_code == 204, r.text
    liste = await client.get("/admin/profils", headers=h)
    assert "TEMPORAIRE" not in {p["code"] for p in liste.json()}


async def test_supprimer_un_profil_avec_des_comptes_refuse(
    client: AsyncClient, session: AsyncSession
) -> None:
    h = await _admin(session, "admin.supp2@afgbank.ml")
    await creer_utilisateur(session, email="agent.rattache@afgbank.ml", profil="SUPPORT_APP")

    r = await client.delete("/admin/profils/SUPPORT_APP", headers=h)

    assert r.status_code == 409, r.text
    assert "compte" in r.json()["detail"].lower()


async def test_supprimer_le_profil_administrateur_refuse(
    client: AsyncClient, session: AsyncSession
) -> None:
    h = await _admin(session, "admin.suppadmin@afgbank.ml")

    r = await client.delete("/admin/profils/ADMIN", headers=h)

    assert r.status_code == 409, r.text


async def test_supprimer_un_profil_inconnu(client: AsyncClient, session: AsyncSession) -> None:
    h = await _admin(session, "admin.suppinconnu@afgbank.ml")

    assert (await client.delete("/admin/profils/FANTOME", headers=h)).status_code == 404


async def test_supprimer_un_profil_emporte_ses_acces(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Aucun accès orphelin ne subsiste après suppression."""
    h = await _admin(session, "admin.suppacces@afgbank.ml")
    await client.post("/admin/profils", headers=h, json={"libelle": "Ephemere"})
    await client.put("/admin/acces", headers=h, json={"profil": "EPHEMERE", "acces": ["incidents"]})

    await client.delete("/admin/profils/EPHEMERE", headers=h)

    matrice = (await client.get("/admin/acces", headers=h)).json()
    assert all(r["profil"] != "EPHEMERE" for r in matrice["roles"])


# --- Contrôle d'accès ----------------------------------------------------------------------------


async def test_un_agent_metier_ne_peut_pas_gerer_les_profils(
    client: AsyncClient, session: AsyncSession
) -> None:
    uid = await creer_utilisateur(session, email="agent.profils@afgbank.ml")
    h = entetes(uid)
    corps = {"libelle": "X"}

    assert (await client.post("/admin/profils", headers=h, json=corps)).status_code == 403
    assert (await client.patch("/admin/profils/ADMIN", headers=h, json=corps)).status_code == 403
    assert (await client.delete("/admin/profils/SUPPORT_APP", headers=h)).status_code == 403
