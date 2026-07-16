"""Le niveau de support d'un ticket importé se **déduit** de son gestionnaire.

Ce n'est plus une action : après chaque import, le support lit où se trouve le ticket.

Le gestionnaire du fichier est-il l'un des nôtres ? Alors le ticket est à son niveau (N1 ou N2).
S'il porte un autre nom, c'est DBS — tout ce qui n'est pas nous est DBS — et le ticket est au
niveau 3. Si le fichier ne nomme personne, le ticket n'est chez personne : niveau inconnu, et
surtout pas DBS.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_activite, creer_utilisateur, entetes


async def _agent(session: AsyncSession, email: str, niveau: int | None) -> str:
    uid = await creer_utilisateur(session, email=email)
    await session.execute(
        text("UPDATE core.utilisateur SET niveau_support = :n WHERE id = cast(:i as uuid)"),
        {"n": niveau, "i": uid},
    )
    await session.commit()
    return uid


async def _poser_gestionnaire(session: AsyncSession, ident: str, nom: str) -> None:
    """Ce que l'import écrit : le nom du gestionnaire porté par le fichier."""
    await session.execute(
        text(
            "UPDATE core.activite SET donnees = donnees || "
            "jsonb_build_object('gestionnaire', cast(:n as text)) WHERE id = cast(:i as uuid)"
        ),
        {"n": nom, "i": ident},
    )
    await session.commit()


async def _detail(client: AsyncClient, ident: str, uid: str) -> dict[str, object]:
    r = await client.get(f"/incidents/{ident}", headers=entetes(uid))
    assert r.status_code == 200, r.text
    return dict(r.json())


@pytest.mark.parametrize("niveau", [1, 2])
async def test_le_ticket_est_au_niveau_de_son_gestionnaire(
    client: AsyncClient, session: AsyncSession, niveau: int
) -> None:
    agent = await _agent(session, f"n{niveau}.niv@afgbank.ml", niveau)
    incident = await creer_activite(
        session, module="incident", reference=f"INC-NIV-{niveau}", responsable_id=agent
    )

    d = await _detail(client, incident, agent)

    assert d["niveau_support"] == niveau
    assert d["transfere_dbs"] is False


async def test_un_gestionnaire_sans_niveau_declare_entre_au_n1(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Défaut prudent. Les comptes sont créés par l'admin, avec leur niveau."""
    agent = await _agent(session, "sansniveau.niv@afgbank.ml", None)
    incident = await creer_activite(
        session, module="incident", reference="INC-NIV-0", responsable_id=agent
    )

    d = await _detail(client, incident, agent)

    assert d["niveau_support"] == 1
    assert d["transfere_dbs"] is False


async def test_un_gestionnaire_hors_dsi_met_le_ticket_chez_dbs(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le nom du fichier n'a été rapproché d'aucun compte : ce n'est pas nous, donc DBS."""
    lecteur = await creer_utilisateur(session, email="lecteur.niv@afgbank.ml")
    incident = await creer_activite(session, module="incident", reference="INC-NIV-DBS")
    await _poser_gestionnaire(session, incident, "Agent DBS")

    d = await _detail(client, incident, lecteur)

    assert d["niveau_support"] == 3
    assert d["transfere_dbs"] is True


@pytest.mark.parametrize("valeur", ["None", "N/A", "  ", "-", "inconnu"])
async def test_un_gestionnaire_non_renseigne_n_est_pas_dbs(
    client: AsyncClient, session: AsyncSession, valeur: str
) -> None:
    """Le fichier ne nomme personne : le ticket n'est chez personne, surtout pas chez DBS.

    « None », « N/A », « - »… sont des absences écrites en toutes lettres, pas des gestionnaires.
    """
    lecteur = await creer_utilisateur(session, email=f"lecteur.nr{len(valeur)}@afgbank.ml")
    incident = await creer_activite(session, module="incident", reference=f"INC-NR-{len(valeur)}")
    await _poser_gestionnaire(session, incident, valeur)

    d = await _detail(client, incident, lecteur)

    assert d["niveau_support"] is None
    assert d["transfere_dbs"] is False
    assert d["gestionnaire"] is None


async def test_le_niveau_suit_le_gestionnaire_a_chaque_import(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le support voit le niveau bouger tout seul quand le ticket change de mains."""
    n2 = await _agent(session, "n2.suivi@afgbank.ml", 2)
    incident = await creer_activite(
        session, module="incident", reference="INC-NIV-SUIVI", responsable_id=n2
    )
    assert (await _detail(client, incident, n2))["niveau_support"] == 2

    # Import suivant : le fichier donne un gestionnaire inconnu → parti chez DBS.
    await session.execute(
        text("UPDATE core.activite SET responsable_id = NULL WHERE id = cast(:i as uuid)"),
        {"i": incident},
    )
    await session.commit()
    await _poser_gestionnaire(session, incident, "Agent DBS")

    d = await _detail(client, incident, n2)
    assert d["niveau_support"] == 3
    assert d["transfere_dbs"] is True


async def test_la_liste_expose_le_niveau_de_chaque_ticket(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le support doit voir où se trouve chaque ticket sans ouvrir les fiches une à une."""
    n2 = await _agent(session, "n2.liste@afgbank.ml", 2)
    await creer_activite(session, module="incident", reference="INC-NIV-L1", responsable_id=n2)
    l2 = await creer_activite(session, module="incident", reference="INC-NIV-L2")
    await _poser_gestionnaire(session, l2, "Agent DBS")

    r = await client.get("/incidents", headers=entetes(n2))

    assert r.status_code == 200, r.text
    par_ref = {a["reference"]: a for a in r.json()["elements"]}
    assert par_ref["INC-NIV-L1"]["niveau_support"] == 2
    assert par_ref["INC-NIV-L1"]["transfere_dbs"] is False
    assert par_ref["INC-NIV-L2"]["niveau_support"] == 3
    assert par_ref["INC-NIV-L2"]["transfere_dbs"] is True


async def test_l_escalade_manuelle_n_existe_plus(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le niveau est une conséquence de l'import, jamais une décision prise ici."""
    agent = await _agent(session, "esc.niv@afgbank.ml", 1)
    incident = await creer_activite(
        session, module="incident", reference="INC-NIV-ESC", responsable_id=agent
    )

    r = await client.post(f"/incidents/{incident}/escalader", headers=entetes(agent))

    assert r.status_code == 404, r.text
