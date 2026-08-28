"""Les chiffres d'un même écran doivent se recouper.

Le piège rencontré : « Activités ouvertes » jugeait l'état sur un horodatage (`cloture_le IS
NULL`) alors que les listes le jugent sur la phase du domaine. Or « Réalisé », « Accepté » ou
« Corrigé » ne posent aucun horodatage : ces activités étaient comptées ouvertes ici et terminées
ailleurs. Deux réponses à la même question, sur la même page.
"""

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_activite, creer_utilisateur, entetes


async def _statut(session: AsyncSession, reference: str, statut: str) -> None:
    await session.execute(
        text("UPDATE core.activite SET statut = :s WHERE reference = :r"),
        {"s": statut, "r": reference},
    )
    await session.commit()


async def test_une_activite_terminee_sans_date_de_cloture_n_est_pas_ouverte(
    client: AsyncClient, session: AsyncSession
) -> None:
    """« Réalisé » est une fin, même sans `cloture_le` : hors du stock ouvert."""
    admin = await creer_utilisateur(session, email="coh.fin@afgbank.ml", profil="ADMIN")
    avant = (await client.get("/analyses?modules=gouvernance", headers=entetes(admin))).json()

    await creer_activite(
        session, module="gouvernance", reference="GOV-2026-99001", responsable_id=admin
    )
    await _statut(session, "GOV-2026-99001", "Réalisé")

    apres = (await client.get("/analyses?modules=gouvernance", headers=entetes(admin))).json()

    # Aucun horodatage de clôture n'a été posé : c'est justement le cas piégeux.
    reste = await session.scalar(
        text("SELECT cloture_le FROM core.activite WHERE reference = 'GOV-2026-99001'")
    )
    assert reste is None

    assert apres["kpis"]["ouvertes"] == avant["kpis"]["ouvertes"], (
        "une activité réalisée ne doit pas compter dans les activités ouvertes"
    )


async def test_les_ouvertes_egalent_les_en_cours_du_detail(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le KPI de tête et le détail par module racontent la même chose, ou l'un des deux ment."""
    admin = await creer_utilisateur(session, email="coh.somme@afgbank.ml", profil="ADMIN")
    for i, statut in enumerate(("Nouveau", "Ouvert", "Résolu", "Clôturé")):
        ref = f"INC-2026-9910{i}"
        await creer_activite(session, module="incident", reference=ref, responsable_id=admin)
        await _statut(session, ref, statut)

    a = (await client.get("/analyses?modules=incident", headers=entetes(admin))).json()
    en_cours = sum(m["en_cours"] for m in a["resolution_par_module"])
    assert a["kpis"]["ouvertes"] == en_cours


async def test_les_trois_parts_totalisent_les_recues(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Reçues = abouties + arrêtées + en cours : sinon une activité manque, ou compte double."""
    admin = await creer_utilisateur(session, email="coh.parts@afgbank.ml", profil="ADMIN")
    a = (await client.get("/analyses", headers=entetes(admin))).json()
    for m in a["resolution_par_module"]:
        assert m["recus"] == m["resolus"] + m["abandonnes"] + m["en_cours"], m


async def test_le_respect_sla_ne_s_invente_pas_sans_donnee(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Sans population mesurable, on ne renvoie rien — pas « 100 % » sur un tableau vide."""
    admin = await creer_utilisateur(session, email="coh.sla@afgbank.ml", profil="ADMIN")

    # Un module sans aucun ticket importé ni échéance : rien à mesurer.
    a = (await client.get("/analyses?modules=gouvernance", headers=entetes(admin))).json()
    respect = a["kpis"]["respect_sla"]
    assert respect is None or isinstance(respect, int)
    if respect is not None:
        # S'il y a un chiffre, c'est qu'il y avait bien une population derrière.
        total_sla = a["sla"]["a_lheure"] + a["sla"]["approche"] + a["sla"]["depasse"]
        assert total_sla > 0, "un taux affiche doit reposer sur des echeances reelles"


async def test_le_tableau_de_bord_et_les_analyses_disent_la_meme_chose(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Deux écrans, une seule vérité : ouvertes, abouties et retards doivent coïncider.

    Les deux tiraient leurs comptes d'endroits différents. Le tableau de bord comptait les
    « Résolues » sur les horodatages : « Réalisé », « Accepté » et « Corrigé » n'en posent
    aucun, et manquaient donc à l'appel — 13 annoncées ici pour 21 abouties là-bas.
    """
    admin = await creer_utilisateur(session, email="coh.deux@afgbank.ml", profil="ADMIN")
    for i, statut in enumerate(("Nouveau", "Ouvert", "Résolu", "Clôturé")):
        ref = f"INC-2026-9920{i}"
        await creer_activite(session, module="incident", reference=ref, responsable_id=admin)
        await _statut(session, ref, statut)
    # Le cas piégeux : une fin qui ne pose aucun horodatage.
    await creer_activite(
        session, module="gouvernance", reference="GOV-2026-99201", responsable_id=admin
    )
    await _statut(session, "GOV-2026-99201", "Réalisé")

    tb = (await client.get("/tableau-de-bord", headers=entetes(admin))).json()["cartes"]
    an = (await client.get("/analyses", headers=entetes(admin))).json()
    abouties = sum(m["resolus"] for m in an["resolution_par_module"])

    assert tb["activites_ouvertes"] == an["kpis"]["ouvertes"]
    assert tb["resolues"] == abouties
    assert tb["en_retard"] == an["kpis"]["en_retard"]


async def test_la_charge_ne_depasse_jamais_le_stock_ouvert(
    client: AsyncClient, session: AsyncSession
) -> None:
    """« Charge de la DSI » est un sous-ensemble des ouvertes : celles qui ont un gestionnaire."""
    admin = await creer_utilisateur(session, email="coh.charge@afgbank.ml", profil="ADMIN")
    tb = (await client.get("/tableau-de-bord", headers=entetes(admin))).json()["cartes"]
    assert tb["charge_dsi"] <= tb["activites_ouvertes"]
    assert tb["critiques"] <= tb["activites_ouvertes"]
