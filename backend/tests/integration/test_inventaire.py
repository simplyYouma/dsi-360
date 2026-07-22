"""Inventaire : référentiel du parc matériel, avec sa valeur au bilan.

L'équipement n'est pas une activité : pas de workflow, pas de SLA. Ce qui compte ici, c'est que
le code d'immobilisation reste unique, que la valeur nette se calcule au vol, et que le détenteur
se rattache par matricule sans jamais créer de compte.
"""

from datetime import date
from typing import Any

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_utilisateur, entetes


async def _admin(session: AsyncSession, email: str) -> str:
    return await creer_utilisateur(session, email=email, profil="ADMIN")


async def _creer(
    client: AsyncClient, uid: str, **champs: Any
) -> dict[str, Any]:
    corps: dict[str, Any] = {"designation": "Poste de travail"} | champs
    r = await client.post("/inventaire", json=corps, headers=entetes(uid))
    assert r.status_code == 201, r.text
    return dict(r.json())


async def test_creer_puis_relire_un_equipement(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await _admin(session, "admin.inv1@afgbank.ml")

    cree = await _creer(
        client,
        admin,
        designation="GAB NCR SelfServ 25",
        code_immo="INF00208",
        numero_serie="SN-4412",
        modele="SelfServ 25",
    )

    r = await client.get(f"/inventaire/{cree['id']}", headers=entetes(admin))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["code_immo"] == "INF00208"
    assert d["designation"] == "GAB NCR SelfServ 25"
    assert d["numero_serie"] == "SN-4412"
    assert d["source"] == "SAISIE"
    assert d["actif"] is True


async def test_le_code_immo_ne_peut_pas_servir_deux_fois(
    client: AsyncClient, session: AsyncSession
) -> None:
    """C'est l'identifiant comptable du bien : deux équipements ne peuvent le partager."""
    admin = await _admin(session, "admin.inv2@afgbank.ml")
    await _creer(client, admin, code_immo="INF00300")

    r = await client.post(
        "/inventaire",
        json={"designation": "Autre matériel", "code_immo": "inf00300"},
        headers=entetes(admin),
    )

    assert r.status_code == 409, "le doublon est refusé, quelle que soit la casse"
    assert "déjà utilisé" in r.json()["detail"]


async def test_un_equipement_sans_code_immo_reste_possible(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Un matériel acheté mais pas encore immobilisé doit pouvoir entrer au parc."""
    admin = await _admin(session, "admin.inv3@afgbank.ml")

    premier = await _creer(client, admin, designation="Clavier de rechange")
    second = await _creer(client, admin, designation="Souris de rechange")

    assert premier["code_immo"] is None
    assert second["code_immo"] is None, "l'absence de code ne compte pas comme un doublon"


async def test_la_valeur_nette_est_calculee_a_la_lecture(
    client: AsyncClient, session: AsyncSession
) -> None:
    """La VNC n'est jamais stockée : figée en base, elle serait fausse dès le lendemain."""
    admin = await _admin(session, "admin.inv4@afgbank.ml")

    cree = await _creer(
        client,
        admin,
        designation="Serveur lame",
        valeur_acquisition=1_000_000,
        date_acquisition=str(date(2020, 1, 1)),
        taux=25,
        duree_annees=4,
    )

    # Acquis en 2020 à 25 %/an : totalement amorti depuis 2024.
    assert cree["valeur_nette"] == 0
    assert cree["amorti_pct"] == 100
    assert cree["totalement_amorti"] is True
    assert cree["dotation_annuelle"] == 250_000
    assert cree["fin_amortissement"].startswith("2024")
    assert cree["amortissement_incoherent"] is False


async def test_un_taux_qui_contredit_la_duree_est_signale(
    client: AsyncClient, session: AsyncSession
) -> None:
    """On ne corrige pas une donnée douteuse en silence : on la montre."""
    admin = await _admin(session, "admin.inv5@afgbank.ml")

    cree = await _creer(
        client,
        admin,
        valeur_acquisition=1000,
        date_acquisition=str(date(2024, 1, 1)),
        taux=25,
        duree_annees=10,
    )

    assert cree["amortissement_incoherent"] is True


async def test_le_detenteur_se_rattache_a_un_compte(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le nom du détenteur vient du compte ; le matricule s'affiche à côté."""
    admin = await _admin(session, "admin.inv6@afgbank.ml")
    agent = await creer_utilisateur(session, email="agent.inv@afgbank.ml")
    await session.execute(
        text("UPDATE core.utilisateur SET matricule = 'M-7788' WHERE id = cast(:i as uuid)"),
        {"i": agent},
    )
    await session.commit()

    cree = await _creer(client, admin, detenteur_id=agent)

    assert cree["detenteur"] is not None
    assert cree["matricule"] == "M-7788"


async def test_modifier_un_equipement_conserve_le_reste(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await _admin(session, "admin.inv7@afgbank.ml")
    cree = await _creer(client, admin, code_immo="INF00400", numero_serie="SN-1")

    r = await client.patch(
        f"/inventaire/{cree['id']}", json={"modele": "Latitude 5540"}, headers=entetes(admin)
    )

    assert r.status_code == 200, r.text
    d = r.json()
    assert d["modele"] == "Latitude 5540"
    assert d["numero_serie"] == "SN-1", "un champ non fourni n'est pas effacé"
    assert d["code_immo"] == "INF00400"


async def test_sortir_du_parc_sans_supprimer(client: AsyncClient, session: AsyncSession) -> None:
    """Un matériel cédé quitte les listes actives, mais son historique reste."""
    admin = await _admin(session, "admin.inv8@afgbank.ml")
    cree = await _creer(client, admin, designation="Imprimante hors service")

    await client.patch(f"/inventaire/{cree['id']}", json={"actif": False}, headers=entetes(admin))

    actifs = await client.get("/inventaire", headers=entetes(admin))
    refs = {e["id"] for e in actifs.json()["elements"]}
    assert cree["id"] not in refs, "il sort de la liste par défaut"

    tous = await client.get("/inventaire?actif=false", headers=entetes(admin))
    assert cree["id"] in {e["id"] for e in tous.json()["elements"]}


async def test_la_recherche_trouve_par_serie_et_par_detenteur(
    client: AsyncClient, session: AsyncSession
) -> None:
    """On cherche un matériel par ce qui est écrit dessus — ou par qui le détient."""
    admin = await _admin(session, "admin.inv9@afgbank.ml")
    agent = await creer_utilisateur(session, email="porteur.inv@afgbank.ml")
    await session.execute(
        text(
            "UPDATE core.utilisateur SET matricule = 'M-9001', prenom = 'Awa', nom = 'Toure' "
            "WHERE id = cast(:i as uuid)"
        ),
        {"i": agent},
    )
    await session.commit()
    await _creer(
        client, admin, designation="Portable Awa", numero_serie="XYZ-777", detenteur_id=agent
    )

    par_serie = await client.get("/inventaire?q=XYZ-777", headers=entetes(admin))
    par_nom = await client.get("/inventaire?q=Toure", headers=entetes(admin))
    par_matricule = await client.get("/inventaire?q=M-9001", headers=entetes(admin))

    for reponse in (par_serie, par_nom, par_matricule):
        assert reponse.status_code == 200, reponse.text
        assert any(e["numero_serie"] == "XYZ-777" for e in reponse.json()["elements"])


async def test_les_compteurs_de_l_entete(client: AsyncClient, session: AsyncSession) -> None:
    admin = await _admin(session, "admin.inv10@afgbank.ml")
    await _creer(client, admin, designation="Poste A", valeur_acquisition=500_000)
    sorti = await _creer(client, admin, designation="Poste B", valeur_acquisition=300_000)
    await client.patch(f"/inventaire/{sorti['id']}", json={"actif": False}, headers=entetes(admin))

    r = await client.get("/inventaire/stats", headers=entetes(admin))

    assert r.status_code == 200, r.text
    s = r.json()
    assert s["total"] >= 2
    assert s["sortis"] >= 1
    assert s["sans_detenteur"] >= 2
    # La valeur du parc ne compte que ce qui est encore en service.
    assert s["valeur_acquisition"] >= 500_000


async def test_l_acces_au_module_est_exige(client: AsyncClient, session: AsyncSession) -> None:
    """Sans l'accès « inventaire », le parc reste fermé — comme tout autre module."""
    profil = await session.scalar(
        text(
            "INSERT INTO core.profil (code, libelle, transverse) "
            "VALUES ('SANS_INV', 'Sans inventaire', false) RETURNING id::text"
        )
    )
    await session.execute(
        text(
            "INSERT INTO core.acces_role (profil_code, acces) VALUES ('SANS_INV', 'incidents') "
            "ON CONFLICT DO NOTHING"
        )
    )
    await session.commit()
    assert profil is not None
    intrus = await creer_utilisateur(session, email="intrus.inv@afgbank.ml", profil="SANS_INV")

    r = await client.get("/inventaire", headers=entetes(intrus))

    assert r.status_code == 403, r.text


async def test_seul_l_administrateur_supprime(client: AsyncClient, session: AsyncSession) -> None:
    """La suppression est définitive : on la réserve à l'administrateur."""
    admin = await _admin(session, "admin.inv11@afgbank.ml")
    agent = await creer_utilisateur(session, email="agent.supp@afgbank.ml")
    cree = await _creer(client, admin, designation="À supprimer")

    refus = await client.delete(f"/inventaire/{cree['id']}", headers=entetes(agent))
    assert refus.status_code == 403, refus.text

    ok = await client.delete(f"/inventaire/{cree['id']}", headers=entetes(admin))
    assert ok.status_code == 204, ok.text
    relu = await client.get(f"/inventaire/{cree['id']}", headers=entetes(admin))
    assert relu.status_code == 404


async def test_les_referentiels_s_alimentent_et_se_listent(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Emplacements et départements : créés à la demande, jamais en double."""
    admin = await _admin(session, "admin.inv12@afgbank.ml")

    a = await client.post(
        "/inventaire/referentiels/emplacements",
        json={"libelle": "Agence Yirimadio"},
        headers=entetes(admin),
    )
    b = await client.post(
        "/inventaire/referentiels/emplacements",
        json={"libelle": "AGENCE YIRIMADIO"},
        headers=entetes(admin),
    )

    assert a.status_code == 201, a.text
    assert b.json()["id"] == a.json()["id"], "même lieu, à la casse près"

    liste = await client.get("/inventaire/referentiels/emplacements", headers=entetes(admin))
    assert any(e["libelle"].lower() == "agence yirimadio" for e in liste.json())


async def test_un_referentiel_inconnu_est_refuse(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le nom de table ne vient jamais de l'appelant : la liste blanche tranche."""
    admin = await _admin(session, "admin.inv13@afgbank.ml")

    r = await client.get("/inventaire/referentiels/utilisateur", headers=entetes(admin))

    assert r.status_code == 404
