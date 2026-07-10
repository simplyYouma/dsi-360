"""Les capacités sont calculées par le serveur et exposées dans le détail.

Le front ne rejoue pas la règle : il obéit. Sinon elle vit à deux endroits et finit par diverger —
l'écran laisserait cliquer là où le serveur refuse, ou masquerait ce qui est permis.
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_activite, creer_utilisateur, designer, entetes

TOUTES = ("peut_assigner", "peut_evaluer", "peut_gerer_acteurs", "peut_travailler", "peut_decider")


async def _changement_dote(session: AsyncSession, suffixe: str) -> tuple[str, dict[str, str]]:
    gens = {}
    for role, profil in (
        ("admin", "ADMIN"),
        ("responsable", "SUPPORT_APP_HELPDESK"),
        ("contributeur", "SUPPORT_APP_HELPDESK"),
        ("valideur", "SUPPORT_APP_HELPDESK"),
        ("lecteur", "SUPPORT_APP_HELPDESK"),
    ):
        gens[role] = await creer_utilisateur(
            session, email=f"{role}.perm{suffixe}@afgbank.ml", profil=profil
        )
    changement = await creer_activite(
        session,
        module="changement",
        reference=f"CHG-PRM-{suffixe}",
        responsable_id=gens["responsable"],
    )
    await designer(
        session, activite_id=changement, utilisateur_id=gens["contributeur"], role="CONTRIBUTEUR"
    )
    await designer(
        session, activite_id=changement, utilisateur_id=gens["valideur"], role="VALIDEUR"
    )
    return changement, gens


async def _permissions(client: AsyncClient, base: str, ident: str, uid: str) -> dict[str, bool]:
    r = await client.get(f"{base}/{ident}", headers=entetes(uid))
    assert r.status_code == 200, r.text
    return dict(r.json()["permissions"])


async def test_l_administrateur_organise_et_travaille_mais_ne_decide_pas(
    client: AsyncClient, session: AsyncSession
) -> None:
    changement, gens = await _changement_dote(session, "adm")

    p = await _permissions(client, "/changements", changement, gens["admin"])

    assert p["peut_assigner"] and p["peut_evaluer"] and p["peut_gerer_acteurs"]
    assert p["peut_travailler"]
    assert not p["peut_decider"], "l'admin ne valide pas à la place des valideurs"


async def test_le_responsable_travaille_seulement(
    client: AsyncClient, session: AsyncSession
) -> None:
    changement, gens = await _changement_dote(session, "resp")

    p = await _permissions(client, "/changements", changement, gens["responsable"])

    assert p["peut_travailler"]
    assert not any(p[c] for c in TOUTES if c != "peut_travailler")


async def test_le_contributeur_travaille_seulement(
    client: AsyncClient, session: AsyncSession
) -> None:
    changement, gens = await _changement_dote(session, "contrib")

    p = await _permissions(client, "/changements", changement, gens["contributeur"])

    assert p["peut_travailler"]
    assert not p["peut_assigner"] and not p["peut_gerer_acteurs"] and not p["peut_evaluer"]


async def test_le_valideur_decide_seulement(client: AsyncClient, session: AsyncSession) -> None:
    changement, gens = await _changement_dote(session, "valid")

    p = await _permissions(client, "/changements", changement, gens["valideur"])

    assert p["peut_decider"]
    assert not any(p[c] for c in TOUTES if c != "peut_decider")


async def test_le_lecteur_ne_peut_rien(client: AsyncClient, session: AsyncSession) -> None:
    changement, gens = await _changement_dote(session, "lect")

    p = await _permissions(client, "/changements", changement, gens["lecteur"])

    assert not any(p.values())


async def test_les_permissions_sont_exposees_sur_les_projets(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await creer_utilisateur(session, email="admin.permprj@afgbank.ml", profil="ADMIN")
    lecteur = await creer_utilisateur(session, email="lecteur.permprj@afgbank.ml")
    projet = await creer_activite(session, module="projet", reference="PRJ-PRM-1")

    assert (await _permissions(client, "/projets", projet, admin))["peut_travailler"]
    assert not (await _permissions(client, "/projets", projet, lecteur))["peut_travailler"]


async def test_les_permissions_sont_exposees_sur_les_risques(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await creer_utilisateur(session, email="admin.permrsq@afgbank.ml", profil="ADMIN")
    lecteur = await creer_utilisateur(session, email="lecteur.permrsq@afgbank.ml")
    risque = await creer_activite(session, module="risque", reference="RSQ-PRM-1")

    assert (await _permissions(client, "/risques", risque, admin))["peut_assigner"]
    assert not (await _permissions(client, "/risques", risque, lecteur))["peut_assigner"]


async def test_un_incident_importe_n_offre_aucune_action(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Même l'administrateur n'agit pas sur un ticket importé : l'écran ne doit rien proposer.

    Sinon il laisserait cliquer là où le serveur répond 404 (ADR-0005).
    """
    admin = await creer_utilisateur(session, email="admin.perminc@afgbank.ml", profil="ADMIN")
    incident = await creer_activite(session, module="incident", reference="INC-PRM-1")

    assert not any((await _permissions(client, "/incidents", incident, admin)).values())
