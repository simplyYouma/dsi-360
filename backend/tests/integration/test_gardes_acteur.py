"""Ce que font les acteurs de travail : faire avancer le sujet.

L'administrateur, le gestionnaire et les contributeurs transitionnent l'activité, créent des tâches,
posent des notes et des liens. Le valideur ne travaille pas — il décide. Le lecteur regarde.

**Exception des tickets importés** : incidents et demandes viennent du rapport quotidien. Un
incident importé sans gestionnaire rapproché n'aurait aucun acteur : plus personne ne pourrait
l'escalader ni le clore. Pour ces deux modules, l'accès au module suffit encore à travailler ;
leur cas se traite dans un lot dédié.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_activite, creer_utilisateur, designer, entetes

ACTEURS = ["admin", "responsable", "contributeur"]
NON_ACTEURS = ["valideur", "lecteur"]


async def _equipe(session: AsyncSession, suffixe: str) -> dict[str, str]:
    roles = {}
    for role, profil in (
        ("admin", "ADMIN"),
        ("responsable", "SUPPORT_APP_HELPDESK"),
        ("contributeur", "SUPPORT_APP_HELPDESK"),
        ("valideur", "SUPPORT_APP_HELPDESK"),
        ("lecteur", "SUPPORT_APP_HELPDESK"),
    ):
        roles[role] = await creer_utilisateur(
            session, email=f"{role}.{suffixe}@afgbank.ml", profil=profil
        )
    return roles


async def _changement_dote(session: AsyncSession, suffixe: str) -> tuple[str, dict[str, str]]:
    gens = await _equipe(session, suffixe)
    changement = await creer_activite(
        session,
        module="changement",
        reference=f"CHG-ACT-{suffixe}",
        responsable_id=gens["responsable"],
    )
    await designer(
        session, activite_id=changement, utilisateur_id=gens["contributeur"], role="CONTRIBUTEUR"
    )
    await designer(
        session, activite_id=changement, utilisateur_id=gens["valideur"], role="VALIDEUR"
    )
    return changement, gens


# --- Transition de statut ------------------------------------------------------------------------


@pytest.mark.parametrize("role", ACTEURS)
async def test_les_acteurs_font_avancer_le_changement(
    client: AsyncClient, session: AsyncSession, role: str
) -> None:
    changement, gens = await _changement_dote(session, f"trans-{role}")

    r = await client.post(
        f"/changements/{changement}/transition",
        headers=entetes(gens[role]),
        json={"vers": "Soumis"},
    )

    assert r.status_code == 200, f"{role} : {r.text}"


@pytest.mark.parametrize("role", NON_ACTEURS)
async def test_ni_le_valideur_ni_le_lecteur_ne_transitionnent(
    client: AsyncClient, session: AsyncSession, role: str
) -> None:
    changement, gens = await _changement_dote(session, f"trans-non-{role}")

    r = await client.post(
        f"/changements/{changement}/transition",
        headers=entetes(gens[role]),
        json={"vers": "Soumis"},
    )

    assert r.status_code == 403, f"{role} ne fait pas avancer le sujet"


# --- Tâches, notes, liens ------------------------------------------------------------------------


@pytest.mark.parametrize("role", ACTEURS)
async def test_les_acteurs_creent_des_taches(
    client: AsyncClient, session: AsyncSession, role: str
) -> None:
    changement, gens = await _changement_dote(session, f"tache-{role}")

    r = await client.post(
        f"/changements/{changement}/taches",
        headers=entetes(gens[role]),
        json={"titre": "Préparer le déploiement"},
    )

    assert r.status_code == 201, f"{role} : {r.text}"


@pytest.mark.parametrize("role", NON_ACTEURS)
async def test_ni_le_valideur_ni_le_lecteur_ne_creent_de_tache(
    client: AsyncClient, session: AsyncSession, role: str
) -> None:
    changement, gens = await _changement_dote(session, f"tache-non-{role}")

    r = await client.post(
        f"/changements/{changement}/taches",
        headers=entetes(gens[role]),
        json={"titre": "Tâche indue"},
    )

    assert r.status_code == 403


async def test_le_lecteur_voit_les_taches_sans_pouvoir_les_toucher(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Lire reste ouvert : le cloisonnement se joue sur l'écriture."""
    changement, gens = await _changement_dote(session, "tache-lecture")

    r = await client.get(f"/changements/{changement}/taches", headers=entetes(gens["lecteur"]))

    assert r.status_code == 200, r.text


async def test_seuls_les_acteurs_posent_une_note(
    client: AsyncClient, session: AsyncSession
) -> None:
    changement, gens = await _changement_dote(session, "note")
    corps = {"texte": "Point d'avancement du COPIL."}

    assert (
        await client.post(
            f"/changements/{changement}/notes", headers=entetes(gens["contributeur"]), json=corps
        )
    ).status_code == 201
    assert (
        await client.post(
            f"/changements/{changement}/notes", headers=entetes(gens["lecteur"]), json=corps
        )
    ).status_code == 403
    assert (
        await client.get(f"/changements/{changement}/notes", headers=entetes(gens["lecteur"]))
    ).status_code == 200, "le journal de bord reste lisible"


async def test_seuls_les_acteurs_ajoutent_un_lien(
    client: AsyncClient, session: AsyncSession
) -> None:
    changement, gens = await _changement_dote(session, "lien")
    corps = {"libelle": "Runbook", "url": "https://intranet.afgbank.ml/runbook"}

    assert (
        await client.post(
            f"/changements/{changement}/liens", headers=entetes(gens["responsable"]), json=corps
        )
    ).status_code == 201
    assert (
        await client.post(
            f"/changements/{changement}/liens", headers=entetes(gens["lecteur"]), json=corps
        )
    ).status_code == 403
    assert (
        await client.get(f"/changements/{changement}/liens", headers=entetes(gens["lecteur"]))
    ).status_code == 200


# --- La décision reste aux valideurs -------------------------------------------------------------


async def test_le_responsable_ne_valide_pas_a_la_place_du_valideur(
    client: AsyncClient, session: AsyncSession
) -> None:
    changement, gens = await _changement_dote(session, "decision")

    r = await client.post(
        f"/changements/{changement}/decision",
        headers=entetes(gens["responsable"]),
        json={"decision": "APPROUVE"},
    )

    assert r.status_code == 403


# --- Projets : mêmes règles, pas d'exception -----------------------------------------------------


async def test_seuls_les_acteurs_font_avancer_un_projet(
    client: AsyncClient, session: AsyncSession
) -> None:
    gens = await _equipe(session, "projet")
    projet = await creer_activite(
        session, module="projet", reference="PRJ-ACT-1", responsable_id=gens["responsable"]
    )
    await designer(
        session, activite_id=projet, utilisateur_id=gens["contributeur"], role="CONTRIBUTEUR"
    )

    assert (
        await client.post(
            f"/projets/{projet}/taches",
            headers=entetes(gens["contributeur"]),
            json={"titre": "Cadrer le besoin"},
        )
    ).status_code == 201
    assert (
        await client.post(
            f"/projets/{projet}/taches", headers=entetes(gens["lecteur"]), json={"titre": "Indue"}
        )
    ).status_code == 403


async def test_le_lecteur_ne_modifie_pas_le_cadrage_d_un_projet(
    client: AsyncClient, session: AsyncSession
) -> None:
    gens = await _equipe(session, "cadrage")
    projet = await creer_activite(
        session, module="projet", reference="PRJ-ACT-2", responsable_id=gens["responsable"]
    )

    assert (
        await client.patch(
            f"/projets/{projet}", headers=entetes(gens["lecteur"]), json={"sponsor": "Moi"}
        )
    ).status_code == 403
    assert (
        await client.patch(
            f"/projets/{projet}", headers=entetes(gens["responsable"]), json={"sponsor": "La DG"}
        )
    ).status_code == 200


# --- Exception des tickets importés --------------------------------------------------------------


async def test_un_incident_importe_reste_traitable_par_tout_agent(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Sans cette exception, un incident importé sans gestionnaire n'aurait aucun acteur."""
    gens = await _equipe(session, "import-inc")
    incident = await creer_activite(session, module="incident", reference="INC-ACT-1")

    r = await client.post(
        f"/incidents/{incident}/transition",
        headers=entetes(gens["lecteur"]),
        json={"vers": "Ouvert"},
    )

    assert r.status_code == 200, r.text


async def test_une_demande_importee_reste_traitable_par_tout_agent(
    client: AsyncClient, session: AsyncSession
) -> None:
    gens = await _equipe(session, "import-dem")
    demande = await creer_activite(session, module="demande", reference="DEM-ACT-1")

    r = await client.post(
        f"/demandes/{demande}/transition",
        headers=entetes(gens["lecteur"]),
        json={"vers": "Qualifiée"},
    )

    assert r.status_code == 200, r.text
