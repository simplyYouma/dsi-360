"""Le numéro de série identifie physiquement le matériel : unique, et figé une fois relevé.

Deux fiches au même numéro, c'est un équipement compté deux fois — au parc comme au bilan. Et un
numéro qu'on peut réécrire ne prouve plus rien : s'il ne correspond pas à l'appareil, ce n'est pas
le numéro qui est faux, c'est la fiche qui parle d'autre chose.
"""

from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_utilisateur, entetes


async def _creer(client: AsyncClient, uid: str, **champs: Any) -> dict[str, Any]:
    corps: dict[str, Any] = {"designation": "Poste de travail"} | champs
    r = await client.post("/inventaire", json=corps, headers=entetes(uid))
    assert r.status_code == 201, r.text
    return dict(r.json())


async def test_deux_materiels_ne_partagent_pas_un_numero_de_serie(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await creer_utilisateur(session, email="ns.unique@afgbank.ml", profil="ADMIN")
    await _creer(client, admin, designation="Portable A", numero_serie="SN-UNIQUE-001")

    r = await client.post(
        "/inventaire",
        json={"designation": "Portable B", "numero_serie": "sn-unique-001"},
        headers=entetes(admin),
    )
    assert r.status_code == 409, r.text
    assert "déjà" in r.json()["detail"]


async def test_un_numero_releve_ne_se_modifie_plus(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await creer_utilisateur(session, email="ns.fige@afgbank.ml", profil="ADMIN")
    cree = await _creer(client, admin, designation="Serveur", numero_serie="SN-FIGE-001")

    r = await client.patch(
        f"/inventaire/{cree['id']}",
        json={"numero_serie": "SN-AUTRE-002"},
        headers=entetes(admin),
    )
    assert r.status_code == 409, r.text
    assert "identifie ce matériel" in r.json()["detail"]

    # Le reste de la fiche reste corrigible : c'est le numéro qui est figé, pas l'équipement.
    r = await client.patch(
        f"/inventaire/{cree['id']}", json={"modele": "PowerEdge R650"}, headers=entetes(admin)
    )
    assert r.status_code == 200, r.text
    assert r.json()["modele"] == "PowerEdge R650"
    assert r.json()["numero_serie"] == "SN-FIGE-001"


async def test_un_numero_absent_peut_encore_etre_releve(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Tout le parc n'a pas été inventorié : une case vide se remplit, une case pleine se fige."""
    admin = await creer_utilisateur(session, email="ns.vide@afgbank.ml", profil="ADMIN")
    cree = await _creer(client, admin, designation="Imprimante")
    assert cree["numero_serie"] is None

    r = await client.patch(
        f"/inventaire/{cree['id']}", json={"numero_serie": "SN-TARDIF-003"}, headers=entetes(admin)
    )
    assert r.status_code == 200, r.text
    assert r.json()["numero_serie"] == "SN-TARDIF-003"

    # Une fois relevé, il est figé comme les autres.
    r = await client.patch(
        f"/inventaire/{cree['id']}", json={"numero_serie": "SN-ENCORE-004"}, headers=entetes(admin)
    )
    assert r.status_code == 409, r.text


async def test_reecrire_le_meme_numero_ne_derange_personne(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Renvoyer la valeur inchangée (l'écran le fait) ne doit pas être pris pour un changement."""
    admin = await creer_utilisateur(session, email="ns.idem@afgbank.ml", profil="ADMIN")
    cree = await _creer(client, admin, designation="Switch", numero_serie="SN-IDEM-005")

    r = await client.patch(
        f"/inventaire/{cree['id']}",
        json={"numero_serie": " sn-idem-005 ", "modele": "Catalyst"},
        headers=entetes(admin),
    )
    assert r.status_code == 200, r.text
    assert r.json()["modele"] == "Catalyst"
