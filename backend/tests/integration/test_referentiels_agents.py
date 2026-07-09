"""Référentiel des agents assignables.

La liste proposée pour désigner un gestionnaire, un contributeur ou un valideur ne contient que
des comptes **actifs dont le profil a l'accès au module** : on ne désigne pas quelqu'un qui ne peut
pas ouvrir la page.

Auparavant la requête filtrait sur des codes de profils en dur (`DSI`, `CHEF_SERVICE`,
`CHEF_PROJET`, `TECHNICIEN`) supprimés depuis : seuls les administrateurs remontaient.
"""

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_utilisateur, entetes


async def _sans_acces(session: AsyncSession, module: str, profil: str) -> None:
    """Retire l'accès d'un profil à un module (paramétrage d'administration)."""
    await session.execute(
        text("DELETE FROM core.acces_role WHERE profil_code = :p AND acces = :a"),
        {"p": profil, "a": module},
    )
    await session.commit()


async def test_les_agents_metier_sont_proposes(client: AsyncClient, session: AsyncSession) -> None:
    """Le bug : ces profils n'apparaissaient plus du tout."""
    uid = await creer_utilisateur(session, email="agent.ref@afgbank.ml", profil="RESEAU_TELECOM")

    r = await client.get("/referentiels/agents", headers=entetes(uid))

    assert r.status_code == 200, r.text
    assert uid in {a["id"] for a in r.json()}


async def test_un_compte_inactif_n_est_pas_proposable(
    client: AsyncClient, session: AsyncSession
) -> None:
    lecteur = await creer_utilisateur(session, email="actif.ref@afgbank.ml")
    inactif = await creer_utilisateur(session, email="inactif.ref@afgbank.ml", actif=False)

    r = await client.get("/referentiels/agents", headers=entetes(lecteur))

    assert inactif not in {a["id"] for a in r.json()}


async def test_le_filtre_par_module_ne_garde_que_les_profils_qui_y_ont_acces(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await creer_utilisateur(session, email="admin.ref@afgbank.ml", profil="ADMIN")
    exclu = await creer_utilisateur(session, email="exclu.ref@afgbank.ml", profil="SUPPORT_APP")
    garde = await creer_utilisateur(session, email="garde.ref@afgbank.ml", profil="RESEAU_TELECOM")
    await _sans_acces(session, "changements", "SUPPORT_APP")

    r = await client.get("/referentiels/agents?module=changements", headers=entetes(admin))

    assert r.status_code == 200, r.text
    ids = {a["id"] for a in r.json()}
    assert garde in ids, "ce profil a l'accès changements"
    assert exclu not in ids, "ce profil vient de perdre l'accès changements"
    assert admin in ids, "l'administrateur a tous les accès"


async def test_sans_module_tous_les_actifs_sont_renvoyes(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Sans filtre : sert l'autocomplétion des mentions @, qui vise tout le monde."""
    admin = await creer_utilisateur(session, email="admin.ref2@afgbank.ml", profil="ADMIN")
    exclu = await creer_utilisateur(session, email="exclu.ref2@afgbank.ml", profil="SUPPORT_APP")
    await _sans_acces(session, "changements", "SUPPORT_APP")

    r = await client.get("/referentiels/agents", headers=entetes(admin))

    assert exclu in {a["id"] for a in r.json()}


async def test_un_module_inconnu_ne_propose_personne(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await creer_utilisateur(session, email="admin.ref3@afgbank.ml", profil="ADMIN")

    r = await client.get("/referentiels/agents?module=nexiste-pas", headers=entetes(admin))

    assert r.status_code == 200, r.text
    assert r.json() == []
