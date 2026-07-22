"""La discussion interne s'ouvre aux équipements.

Une panne récurrente, un déplacement, une décision de rebut se racontent dans le fil — c'est la
mémoire du matériel, que la fiche seule ne porte pas. Le mécanisme est celui des activités ; seule
la clé change, et la base garantit qu'un message porte sur l'un OU l'autre, jamais les deux.
"""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_activite, creer_utilisateur, entetes


async def _equipement(session: AsyncSession, designation: str = "GAB de test") -> str:
    ident = await session.scalar(
        text(
            "INSERT INTO core.equipement (designation, code_immo) "
            "VALUES (:d, :c) RETURNING id::text"
        ),
        {"d": designation, "c": f"IMMO-{designation[:6]}"},
    )
    await session.commit()
    return str(ident)


async def test_le_fil_d_un_equipement_est_vide_puis_se_remplit(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await creer_utilisateur(session, email="admin.disc1@afgbank.ml", profil="ADMIN")
    eq = await _equipement(session, "GAB Faladié")

    vide = await client.get(f"/commentaires/equipement/{eq}", headers=entetes(admin))
    assert vide.status_code == 200, vide.text
    assert vide.json() == []

    depot = await client.post(
        f"/commentaires/equipement/{eq}",
        json={"texte": "Lecteur de cartes remplacé le 12/07.", "mentions": []},
        headers=entetes(admin),
    )
    assert depot.status_code == 201, depot.text

    fil = await client.get(f"/commentaires/equipement/{eq}", headers=entetes(admin))
    messages = fil.json()
    assert len(messages) == 1
    assert messages[0]["texte"] == "Lecteur de cartes remplacé le 12/07."
    assert messages[0]["auteur_id"] == admin


async def test_un_equipement_inconnu_repond_404(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Mieux vaut le dire qu'un fil vide, qui ferait croire à un matériel sans histoire."""
    admin = await creer_utilisateur(session, email="admin.disc2@afgbank.ml", profil="ADMIN")

    r = await client.get(
        "/commentaires/equipement/00000000-0000-0000-0000-000000000000", headers=entetes(admin)
    )

    assert r.status_code == 404


async def test_une_mention_previent_la_personne_citee(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await creer_utilisateur(session, email="admin.disc3@afgbank.ml", profil="ADMIN")
    cite = await creer_utilisateur(session, email="cite.disc@afgbank.ml")
    eq = await _equipement(session, "Serveur lame")

    await client.post(
        f"/commentaires/equipement/{eq}",
        json={"texte": "@Untel peux-tu vérifier ?", "mentions": [cite]},
        headers=entetes(admin),
    )

    notifs = (
        await session.execute(
            text(
                "SELECT type, titre FROM core.notification "
                "WHERE destinataire_id = cast(:u as uuid) AND type = 'MENTION'"
            ),
            {"u": cite},
        )
    ).mappings().all()
    assert len(notifs) == 1
    assert "Serveur" in notifs[0]["titre"] or "IMMO" in notifs[0]["titre"]


async def test_la_discussion_des_activites_fonctionne_toujours(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Garde-fou : rendre la colonne facultative ne doit rien avoir cassé."""
    admin = await creer_utilisateur(session, email="admin.disc4@afgbank.ml", profil="ADMIN")
    activite = await creer_activite(session, module="changement", reference="CHG-DISC-1")

    depot = await client.post(
        f"/commentaires/{activite}",
        json={"texte": "Toujours opérationnel.", "mentions": []},
        headers=entetes(admin),
    )
    assert depot.status_code == 201, depot.text

    fil = await client.get(f"/commentaires/{activite}", headers=entetes(admin))
    assert [m["texte"] for m in fil.json()] == ["Toujours opérationnel."]


@pytest.mark.parametrize(
    ("activite", "equipement"),
    [(True, True), (False, False)],
    ids=["les deux à la fois", "aucun des deux"],
)
async def test_un_message_porte_sur_un_seul_sujet(
    session: AsyncSession, activite: bool, equipement: bool
) -> None:
    """La contrainte vit en base : le code appelant ne peut pas la contourner par inadvertance."""
    valeurs: dict[str, Any] = {"aid": None, "eid": None}
    if activite:
        valeurs["aid"] = await creer_activite(
            session, module="changement", reference=f"CHG-CTR-{activite}{equipement}"
        )
    if equipement:
        valeurs["eid"] = await _equipement(session, f"Contrainte {equipement}")

    with pytest.raises(IntegrityError):
        await session.execute(
            text(
                "INSERT INTO core.commentaire (activite_id, equipement_id, auteur_email, texte) "
                "VALUES (cast(:aid as uuid), cast(:eid as uuid), 'x@afgbank.ml', 'test')"
            ),
            valeurs,
        )
        await session.flush()
    await session.rollback()
