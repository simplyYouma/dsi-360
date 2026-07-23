"""Interroger le journal d'audit : chercher, filtrer, exporter ce qu'on regarde.

Un journal qu'on ne peut pas interroger ne prouve rien. À des dizaines de milliers de lignes,
« qui a touché à cet équipement ? » doit tenir en une recherche — sinon la traçabilité n'existe
que sur le papier.
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_utilisateur, entetes


async def _tracer(client: AsyncClient, admin: str) -> str:
    """Produit une trace au journal : la création d'un équipement au code reconnaissable."""
    code = "JRN-CIBLE-1"
    r = await client.post(
        "/inventaire",
        json={"designation": "Matériel tracé", "code_immo": code},
        headers=entetes(admin),
    )
    assert r.status_code == 201, r.text
    return code


async def test_la_recherche_retrouve_une_cible_precise(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await creer_utilisateur(session, email="admin.jrn1@afgbank.ml", profil="ADMIN")
    code = await _tracer(client, admin)

    r = await client.get(f"/admin/journal?page=1&q={code}", headers=entetes(admin))

    assert r.status_code == 200, r.text
    elements = r.json()["elements"]
    assert elements, "la cible cherchée doit remonter"
    assert all(code in (e["cible"] or "") for e in elements), "et rien d'autre"


async def test_les_filtres_module_et_action_se_combinent(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await creer_utilisateur(session, email="admin.jrn2@afgbank.ml", profil="ADMIN")
    await _tracer(client, admin)

    r = await client.get(
        "/admin/journal?page=1&module=inventaire&action=CREATION", headers=entetes(admin)
    )

    assert r.status_code == 200, r.text
    elements = r.json()["elements"]
    assert elements
    assert all(e["module"] == "inventaire" and e["action"] == "CREATION" for e in elements)


async def test_les_filtres_ne_proposent_que_ce_qui_existe(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Une liste théorique ferait chercher en vain : on n'offre que ce que le journal contient."""
    admin = await creer_utilisateur(session, email="admin.jrn3@afgbank.ml", profil="ADMIN")
    await _tracer(client, admin)

    r = await client.get("/admin/journal/referentiels", headers=entetes(admin))

    assert r.status_code == 200, r.text
    refs = r.json()
    assert "inventaire" in refs["modules"]
    assert "CREATION" in refs["actions"]


async def test_l_export_suit_la_vue(client: AsyncClient, session: AsyncSession) -> None:
    """Un fichier qui dirait autre chose que l'écran dont il sort serait un piège — surtout
    quand il part en pièce jointe à un auditeur."""
    admin = await creer_utilisateur(session, email="admin.jrn4@afgbank.ml", profil="ADMIN")
    await _tracer(client, admin)
    # Une seconde trace, d'une autre action : sans elle, le filtre n'aurait rien à écarter et
    # le test passerait sans rien prouver.
    liste = (await client.get("/inventaire", headers=entetes(admin))).json()["elements"]
    cible = next(e for e in liste if e["code_immo"] == "JRN-CIBLE-1")
    await client.patch(
        f"/inventaire/{cible['id']}", json={"modele": "Modifié"}, headers=entetes(admin)
    )

    complet = await client.get("/admin/journal/export?format=csv", headers=entetes(admin))
    filtre = await client.get(
        "/admin/journal/export?format=csv&module=inventaire&action=CREATION",
        headers=entetes(admin),
    )

    assert complet.status_code == 200 and filtre.status_code == 200
    lignes_completes = complet.content.decode("utf-8-sig").splitlines()
    lignes_filtrees = filtre.content.decode("utf-8-sig").splitlines()
    assert len(lignes_filtrees) < len(lignes_completes), "l'export doit se restreindre"
    # En-tête exclue : chaque ligne exportée relève bien du filtre demandé.
    assert all("inventaire" in ligne for ligne in lignes_filtrees[1:])


async def test_le_journal_reste_reserve_a_l_administrateur(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Chercher dans le journal n'ouvre pas une porte dérobée : la garde tient sur toutes."""
    agent = await creer_utilisateur(session, email="agent.jrn5@afgbank.ml")

    for chemin in (
        "/admin/journal?page=1&q=INF",
        "/admin/journal/referentiels",
        "/admin/journal/export?format=csv",
    ):
        r = await client.get(chemin, headers=entetes(agent))
        assert r.status_code == 403, f"{chemin} : {r.status_code}"
