"""Ce que seul l'administrateur peut faire : distribuer le travail.

Assigner le gestionnaire, fixer l'impact et l'urgence (donc la priorité et le SLA), choisir le Type
d'un changement, désigner contributeurs et valideurs. Ni le responsable ni les contributeurs n'y
touchent : ils exécutent.

Le contrôle est **côté serveur**. Masquer le bouton ne suffirait pas — et aujourd'hui n'importe
quel agent pouvait se désigner valideur, puis approuver.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_activite, creer_utilisateur, designer, entetes


async def _equipe(session: AsyncSession, suffixe: str) -> dict[str, str]:
    """Un admin, un responsable, un contributeur, un valideur, un lecteur."""
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


async def _incident_dote(session: AsyncSession, suffixe: str) -> tuple[str, dict[str, str]]:
    """Un changement doté de ses acteurs.

    Les incidents et les demandes ne se pilotent plus depuis la plateforme (ADR-0005) : ces gardes
    s'exercent donc sur un module que l'on pilote vraiment.
    """
    gens = await _equipe(session, suffixe)
    activite = await creer_activite(
        session,
        module="changement",
        reference=f"CHG-ADM-{suffixe}",
        responsable_id=gens["responsable"],
    )
    await designer(
        session, activite_id=activite, utilisateur_id=gens["contributeur"], role="CONTRIBUTEUR"
    )
    await designer(session, activite_id=activite, utilisateur_id=gens["valideur"], role="VALIDEUR")
    return activite, gens


NON_ADMINS = ["responsable", "contributeur", "valideur", "lecteur"]


# --- Assigner le gestionnaire --------------------------------------------------------------------


async def test_l_admin_assigne_le_gestionnaire(
    client: AsyncClient, session: AsyncSession
) -> None:
    incident, gens = await _incident_dote(session, "assign1")

    r = await client.post(
        f"/changements/{incident}/assignation",
        headers=entetes(gens["admin"]),
        json={"responsable_id": gens["lecteur"]},
    )

    assert r.status_code == 200, r.text
    assert r.json()["responsable_id"] == gens["lecteur"]


@pytest.mark.parametrize("role", NON_ADMINS)
async def test_personne_d_autre_n_assigne(
    client: AsyncClient, session: AsyncSession, role: str
) -> None:
    incident, gens = await _incident_dote(session, f"assign-{role}")

    r = await client.post(
        f"/changements/{incident}/assignation",
        headers=entetes(gens[role]),
        json={"responsable_id": gens["lecteur"]},
    )

    assert r.status_code == 403, f"{role} ne doit pas pouvoir assigner"


async def test_le_responsable_ne_peut_pas_se_debarrasser_du_ticket(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Il ne se désassigne pas non plus : c'est l'admin qui redistribue."""
    incident, gens = await _incident_dote(session, "desassign")

    r = await client.post(
        f"/changements/{incident}/assignation",
        headers=entetes(gens["responsable"]),
        json={"responsable_id": None},
    )

    assert r.status_code == 403


async def test_on_ne_designe_pas_un_agent_sans_acces_au_module(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Pour être gestionnaire, il faut pouvoir ouvrir la page."""
    incident, gens = await _incident_dote(session, "ineligible")
    from sqlalchemy import text

    await session.execute(
        text(
            "DELETE FROM core.acces_role "
            "WHERE profil_code = 'SUPPORT_APP' AND acces = 'changements'"
        )
    )
    await session.commit()
    sans_acces = await creer_utilisateur(
        session, email="sansacces.inc@afgbank.ml", profil="SUPPORT_APP"
    )

    r = await client.post(
        f"/changements/{incident}/assignation",
        headers=entetes(gens["admin"]),
        json={"responsable_id": sans_acces},
    )

    assert r.status_code == 422, r.text


async def test_on_ne_designe_pas_un_compte_inactif(
    client: AsyncClient, session: AsyncSession
) -> None:
    incident, gens = await _incident_dote(session, "inactif")
    inactif = await creer_utilisateur(session, email="inactif.inc@afgbank.ml", actif=False)

    r = await client.post(
        f"/changements/{incident}/assignation",
        headers=entetes(gens["admin"]),
        json={"responsable_id": inactif},
    )

    assert r.status_code == 422, r.text


# --- Assignation en lot --------------------------------------------------------------------------


async def test_seul_l_admin_assigne_en_lot(client: AsyncClient, session: AsyncSession) -> None:
    incident, gens = await _incident_dote(session, "lot")
    corps = {"ids": [incident], "responsable_id": gens["lecteur"]}

    assert (
        await client.post(
            "/changements/assignation-lot", headers=entetes(gens["admin"]), json=corps
        )
    ).status_code == 200
    assert (
        await client.post(
            "/changements/assignation-lot", headers=entetes(gens["responsable"]), json=corps
        )
    ).status_code == 403


# --- Impact et urgence (donc priorité et SLA) ----------------------------------------------------


async def test_l_admin_reevalue_impact_et_urgence(
    client: AsyncClient, session: AsyncSession
) -> None:
    incident, gens = await _incident_dote(session, "eval1")

    r = await client.post(
        f"/changements/{incident}/evaluation",
        headers=entetes(gens["admin"]),
        json={"impact": 5, "urgence": 5},
    )

    assert r.status_code == 200, r.text
    assert r.json()["priorite"] == 1


@pytest.mark.parametrize("role", NON_ADMINS)
async def test_personne_d_autre_ne_reevalue(
    client: AsyncClient, session: AsyncSession, role: str
) -> None:
    incident, gens = await _incident_dote(session, f"eval-{role}")

    r = await client.post(
        f"/changements/{incident}/evaluation",
        headers=entetes(gens[role]),
        json={"impact": 5, "urgence": 5},
    )

    assert r.status_code == 403, f"{role} ne fixe pas la priorité ni l'engagement SLA"


# --- Type du changement --------------------------------------------------------------------------


async def _changement_dote(session: AsyncSession, suffixe: str) -> tuple[str, dict[str, str], str]:
    gens = await _equipe(session, suffixe)
    changement = await creer_activite(
        session,
        module="changement",
        reference=f"CHG-ADM-{suffixe}",
        responsable_id=gens["responsable"],
    )
    await designer(
        session, activite_id=changement, utilisateur_id=gens["contributeur"], role="CONTRIBUTEUR"
    )
    from sqlalchemy import text

    urgent = await session.scalar(
        text("SELECT id::text FROM core.categorie WHERE module = 'changement' AND code = 'URGENT'")
    )
    return changement, gens, str(urgent)


async def test_l_admin_change_le_type_du_changement(
    client: AsyncClient, session: AsyncSession
) -> None:
    changement, gens, urgent = await _changement_dote(session, "type1")

    r = await client.post(
        f"/changements/{changement}/categorie",
        headers=entetes(gens["admin"]),
        json={"categorie_id": urgent},
    )

    assert r.status_code == 200, r.text


@pytest.mark.parametrize("role", ["responsable", "contributeur", "lecteur"])
async def test_personne_d_autre_ne_change_le_type(
    client: AsyncClient, session: AsyncSession, role: str
) -> None:
    """Le Type pilote le circuit CAB/ECAB et dérive la priorité : c'est de l'organisation."""
    changement, gens, urgent = await _changement_dote(session, f"type-{role}")

    r = await client.post(
        f"/changements/{changement}/categorie",
        headers=entetes(gens[role]),
        json={"categorie_id": urgent},
    )

    assert r.status_code == 403


# --- Désigner les acteurs ------------------------------------------------------------------------


async def test_l_admin_designe_contributeurs_et_valideurs(
    client: AsyncClient, session: AsyncSession
) -> None:
    incident, gens = await _incident_dote(session, "designe")
    h = entetes(gens["admin"])

    assert (
        await client.post(
            f"/changements/{incident}/contributeurs",
            headers=h,
            json={"utilisateur_id": gens["lecteur"]},
        )
    ).status_code == 200
    assert (
        await client.post(
            f"/changements/{incident}/valideurs",
            headers=h,
            json={"utilisateur_id": gens["lecteur"]},
        )
    ).status_code == 200
    assert (
        await client.delete(f"/changements/{incident}/contributeurs/{gens['lecteur']}", headers=h)
    ).status_code == 200


@pytest.mark.parametrize("role", NON_ADMINS)
async def test_personne_d_autre_ne_designe_d_acteurs(
    client: AsyncClient, session: AsyncSession, role: str
) -> None:
    incident, gens = await _incident_dote(session, f"designe-{role}")

    r = await client.post(
        f"/changements/{incident}/contributeurs",
        headers=entetes(gens[role]),
        json={"utilisateur_id": gens["lecteur"]},
    )

    assert r.status_code == 403


async def test_un_agent_ne_peut_plus_se_designer_valideur(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le trou béant d'avant : s'auto-désigner valideur, puis approuver."""
    incident, gens = await _incident_dote(session, "autodesigne")

    r = await client.post(
        f"/changements/{incident}/valideurs",
        headers=entetes(gens["contributeur"]),
        json={"utilisateur_id": gens["contributeur"]},
    )

    assert r.status_code == 403


# --- Risques et projets --------------------------------------------------------------------------


async def test_seul_l_admin_nomme_le_chef_de_projet(
    client: AsyncClient, session: AsyncSession
) -> None:
    gens = await _equipe(session, "chef")
    projet = await creer_activite(
        session, module="projet", reference="PRJ-ADM-1", responsable_id=gens["responsable"]
    )

    r = await client.patch(
        f"/projets/{projet}",
        headers=entetes(gens["responsable"]),
        json={"responsable_id": gens["lecteur"]},
    )
    assert r.status_code == 403, "le chef de projet ne se remplace pas lui-même"

    r = await client.patch(
        f"/projets/{projet}",
        headers=entetes(gens["admin"]),
        json={"responsable_id": gens["lecteur"]},
    )
    assert r.status_code == 200, r.text


async def test_ouvrir_un_projet_sans_chef_est_permis_a_tous(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Créer est ouvert ; nommer le chef ne l'est pas. Le créateur n'est pas acteur d'office."""
    gens = await _equipe(session, "creation")

    r = await client.post(
        "/projets", headers=entetes(gens["lecteur"]), json={"titre": "Projet ouvert par un lecteur"}
    )
    assert r.status_code == 201, r.text

    r = await client.post(
        "/projets",
        headers=entetes(gens["lecteur"]),
        json={"titre": "Projet avec chef", "responsable_id": gens["lecteur"]},
    )
    assert r.status_code == 403, "se nommer chef de projet soi-même n'est pas permis"


async def test_seul_l_admin_assigne_un_risque(client: AsyncClient, session: AsyncSession) -> None:
    gens = await _equipe(session, "risque")
    risque = await creer_activite(
        session, module="risque", reference="RSQ-ADM-1", responsable_id=gens["responsable"]
    )
    corps = {"responsable_id": gens["lecteur"]}

    assert (
        await client.post(
            f"/risques/{risque}/assignation", headers=entetes(gens["admin"]), json=corps
        )
    ).status_code == 200
    assert (
        await client.post(
            f"/risques/{risque}/assignation", headers=entetes(gens["responsable"]), json=corps
        )
    ).status_code == 403


async def test_seul_l_administrateur_change_la_categorie_d_un_risque(
    client: AsyncClient, session: AsyncSession
) -> None:
    """La catégorie d'un risque pèse sur sa criticité : elle ne s'improvise pas."""
    admin = await creer_utilisateur(session, email="admin.rsqcat@afgbank.ml", profil="ADMIN")
    responsable = await creer_utilisateur(session, email="resp.rsqcat@afgbank.ml")
    risque = await creer_activite(
        session, module="risque", reference="RSQ-CAT-1", responsable_id=responsable
    )

    for utilisateur, attendu in ((responsable, 403), (admin, 200)):
        r = await client.post(
            f"/risques/{risque}/categorie",
            headers=entetes(utilisateur),
            json={"categorie_id": None},
        )
        assert r.status_code == attendu, r.text


async def test_designer_un_second_contributeur_remplace_le_premier(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Un seul contributeur par activité : nommer quelqu'un d'autre est une réaffectation."""
    admin = await creer_utilisateur(session, email="admin.unique@afgbank.ml", profil="ADMIN")
    premier = await creer_utilisateur(session, email="premier.unique@afgbank.ml")
    second = await creer_utilisateur(session, email="second.unique@afgbank.ml")
    changement = await creer_activite(session, module="changement", reference="CHG-UNQ-1")

    for uid in (premier, second):
        r = await client.post(
            f"/changements/{changement}/contributeurs",
            headers=entetes(admin),
            json={"utilisateur_id": uid},
        )
        assert r.status_code == 200, r.text

    contributeurs = r.json()["contributeurs"]
    assert len(contributeurs) == 1, "le second remplace le premier"
    assert contributeurs[0]["email"] == "second.unique@afgbank.ml"


async def test_une_decision_fige_la_liste_des_valideurs(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Dès qu'un valideur a tranché, on ne peut plus ni remplacer ni retirer un valideur.

    Sinon la décision du prédécesseur disparaîtrait silencieusement du décompte d'approbation.
    """
    admin = await creer_utilisateur(session, email="admin.reval@afgbank.ml", profil="ADMIN")
    premier = await creer_utilisateur(session, email="premier.reval@afgbank.ml")
    second = await creer_utilisateur(session, email="second.reval@afgbank.ml")
    changement = await creer_activite(session, module="changement", reference="CHG-UNQ-2")

    await client.post(
        f"/changements/{changement}/valideurs",
        headers=entetes(admin),
        json={"utilisateur_id": premier},
    )
    r = await client.post(
        f"/changements/{changement}/decision",
        headers=entetes(premier),
        json={"decision": "APPROUVE"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["valideurs_verrouilles"] is True

    # Réaffecter un autre valideur : refusé.
    r = await client.post(
        f"/changements/{changement}/valideurs",
        headers=entetes(admin),
        json={"utilisateur_id": second},
    )
    assert r.status_code == 409, r.text

    # Retirer le valideur qui a décidé : refusé aussi.
    r = await client.request(
        "DELETE",
        f"/changements/{changement}/valideurs/{premier}",
        headers=entetes(admin),
    )
    assert r.status_code == 409, r.text

    # La décision d'origine tient toujours.
    r = await client.get(f"/changements/{changement}", headers=entetes(admin))
    valideurs = r.json()["valideurs"]
    assert len(valideurs) == 1
    assert valideurs[0]["email"] == "premier.reval@afgbank.ml"
    assert valideurs[0]["decision"] == "APPROUVE"
