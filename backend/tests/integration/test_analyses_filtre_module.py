"""Analyses : ne regarder que les modules choisis.

Le piège d'un filtre partiel : un total restreint aux modules retenus, mais une courbe ou un
vieillissement portant encore tout le reste — deux chiffres qui se contredisent sur le même écran.
On vérifie donc que le cadrage traverse *tout* le tableau, y compris ce qui échappe au filtre de
période (tendance, vieillissement).
"""

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_activite, creer_utilisateur, entetes


async def _jeu(session: AsyncSession, admin: str) -> None:
    """Deux incidents et un projet — de quoi distinguer un module de l'autre."""
    await creer_activite(
        session, module="incident", reference="INC-2026-77001", responsable_id=admin
    )
    await creer_activite(
        session, module="incident", reference="INC-2026-77002", responsable_id=admin
    )
    await creer_activite(
        session, module="projet", reference="PRJ-2026-77001", responsable_id=admin
    )


async def test_sans_filtre_tous_les_modules_repondent(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await creer_utilisateur(session, email="ana.tous@afgbank.ml", profil="ADMIN")
    await _jeu(session, admin)

    a = (await client.get("/analyses", headers=entetes(admin))).json()
    modules = {m["libelle"] for m in a["par_module"]}
    assert "incident" in modules
    assert "projet" in modules


async def test_le_filtre_ne_garde_que_les_modules_demandes(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await creer_utilisateur(session, email="ana.filtre@afgbank.ml", profil="ADMIN")
    await _jeu(session, admin)

    r = await client.get("/analyses?modules=incident", headers=entetes(admin))
    assert r.status_code == 200, r.text
    a = r.json()

    assert {m["libelle"] for m in a["par_module"]} == {"incident"}
    # Le SLA par module suit le même cadrage : rien d'un module écarté ne doit ressortir.
    assert {m["module"] for m in a["sla_par_module"]} <= {"incident"}


async def test_plusieurs_modules_se_cumulent(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le paramètre est répétable : ?modules=incident&modules=projet."""
    admin = await creer_utilisateur(session, email="ana.multi@afgbank.ml", profil="ADMIN")
    await _jeu(session, admin)

    a = (
        await client.get("/analyses?modules=incident&modules=projet", headers=entetes(admin))
    ).json()
    modules = {m["libelle"] for m in a["par_module"]}
    assert "incident" in modules
    assert "projet" in modules
    assert "demande" not in modules


async def test_le_total_du_filtre_ne_depasse_jamais_le_total_general(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Un filtre restreint : son total doit être inférieur ou égal à celui de la vue complète."""
    admin = await creer_utilisateur(session, email="ana.total@afgbank.ml", profil="ADMIN")
    await _jeu(session, admin)

    tous = (await client.get("/analyses", headers=entetes(admin))).json()
    filtre = (await client.get("/analyses?modules=incident", headers=entetes(admin))).json()

    assert filtre["total"] <= tous["total"]
    # Le module écarté pesait quelque chose : le filtre doit donc réellement retrancher.
    projets = next((m["valeur"] for m in tous["par_module"] if m["libelle"] == "projet"), 0)
    assert projets > 0
    assert filtre["total"] == tous["total"] - sum(
        m["valeur"] for m in tous["par_module"] if m["libelle"] != "incident"
    )


async def test_la_tendance_suit_le_meme_cadrage_que_les_compteurs(
    client: AsyncClient, session: AsyncSession
) -> None:
    """La tendance a ses propres bornes de temps : elle doit pourtant porter le même filtre.

    C'est le piège du filtre partiel — une courbe qui raconterait autre chose que le total
    affiché juste à côté.
    """
    admin = await creer_utilisateur(session, email="ana.tend@afgbank.ml", profil="ADMIN")
    await _jeu(session, admin)

    tous = (await client.get("/analyses", headers=entetes(admin))).json()
    filtre = (await client.get("/analyses?modules=incident", headers=entetes(admin))).json()

    crees_tous = sum(p["crees"] for p in tous["tendance"])
    crees_filtre = sum(p["crees"] for p in filtre["tendance"])
    assert crees_filtre < crees_tous, (crees_filtre, crees_tous)


async def test_le_vieillissement_suit_aussi_le_filtre(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le vieillissement est un instantané, hors période — mais pas hors périmètre."""
    admin = await creer_utilisateur(session, email="ana.vieil@afgbank.ml", profil="ADMIN")
    await _jeu(session, admin)
    # Les tranches d'âge commencent au-delà de zéro jour : un dossier créé à l'instant n'y tombe
    # pas. On vieillit le projet pour qu'il pèse réellement dans le visuel.
    await session.execute(
        text(
            "UPDATE core.activite SET cree_le = now() - interval '40 days' "
            "WHERE reference = 'PRJ-2026-77001'"
        )
    )
    await session.commit()

    tous = (await client.get("/analyses", headers=entetes(admin))).json()
    filtre = (await client.get("/analyses?modules=incident", headers=entetes(admin))).json()

    assert sum(v["valeur"] for v in filtre["vieillissement"]) < sum(
        v["valeur"] for v in tous["vieillissement"]
    )


async def test_l_evaluation_des_gestionnaires_suit_le_filtre(
    client: AsyncClient, session: AsyncSession
) -> None:
    """On évalue sur le périmètre qu'on regarde, pas sur un autre."""
    admin = await creer_utilisateur(session, email="ana.gest@afgbank.ml", profil="ADMIN")
    await _jeu(session, admin)

    r = await client.get("/analyses/gestionnaires?modules=incident", headers=entetes(admin))
    assert r.status_code == 200, r.text


async def test_un_module_inconnu_ne_casse_rien(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Un nom forgé ne doit pas faire tomber la page : il ne correspond simplement à rien."""
    admin = await creer_utilisateur(session, email="ana.inconnu@afgbank.ml", profil="ADMIN")
    await _jeu(session, admin)

    r = await client.get("/analyses?modules=nexistepas", headers=entetes(admin))
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["total"] == 0
    assert a["par_module"] == []
