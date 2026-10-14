"""Une référence supprimée ne revient jamais — et une suppression ne bloque pas la création.

Le numéro se tirait du COMPTE des fiches existantes. Deux pannes en découlaient, l'une et l'autre
rencontrées en production le 14/10/2026 :

* supprimer une fiche faisait reculer le compte, la référence proposée retombait sur une qui existe
  déjà, et `activite_reference_key` refusait l'insertion. Le module devenait **définitivement**
  incréable, puisque le compte ne remontait jamais : l'ouverture des soirées EOD est restée bloquée
  en 500 jusqu'à ce qu'on regarde pourquoi ;
* quand c'était la dernière fiche qui partait, le numéro se réattribuait en silence. Le journal
  d'audit désigne les activités par leur référence, en texte, précisément pour leur survivre : deux
  soirées distinctes s'y sont retrouvées sous « EOD-2026-00003 », et plus rien ne les distinguait.

Les deux cas sont éprouvés ici, dans cet ordre.
"""

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_utilisateur, entetes


async def _ouvrir(client: AsyncClient, uid: str, journee: str) -> str:
    r = await client.post("/eod", headers=entetes(uid), json={"journee": journee})
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def _reference(session: AsyncSession, ident: str) -> str:
    valeur = await session.scalar(
        text("SELECT reference FROM core.activite WHERE id = cast(:i as uuid)"), {"i": ident}
    )
    return str(valeur)


async def test_supprimer_une_soiree_ne_bloque_pas_la_suivante(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le cas qui bloquait la production : on supprime au milieu, la création doit repartir."""
    admin = await creer_utilisateur(session, email="admin.ref@afgbank.ml", profil="ADMIN")

    premiere = await _ouvrir(client, admin, "2026-03-02")
    deuxieme = await _ouvrir(client, admin, "2026-03-03")
    ref_deuxieme = await _reference(session, deuxieme)

    r = await client.delete(f"/eod/{premiere}", headers=entetes(admin))
    assert r.status_code == 204, r.text

    # Avec un compteur tiré du nombre de fiches, cette création repartait sur la référence de la
    # deuxième soirée — violation d'unicité, et 500 pour l'opérateur.
    troisieme = await _ouvrir(client, admin, "2026-03-04")
    assert await _reference(session, troisieme) != ref_deuxieme


async def test_la_reference_d_une_soiree_supprimee_ne_resservira_pas(
    client: AsyncClient, session: AsyncSession
) -> None:
    """La dernière fiche supprimée emporte son numéro : le journal en garde la trace."""
    admin = await creer_utilisateur(session, email="admin.ref2@afgbank.ml", profil="ADMIN")

    seule = await _ouvrir(client, admin, "2026-04-02")
    ref_seule = await _reference(session, seule)

    r = await client.delete(f"/eod/{seule}", headers=entetes(admin))
    assert r.status_code == 204, r.text

    suivante = await _ouvrir(client, admin, "2026-04-03")
    assert await _reference(session, suivante) != ref_seule

    # Et la preuve que le journal reste seul juge : la référence effacée y figure toujours, une
    # seule fois. Si elle resservait, deux activités distinctes la porteraient.
    attributions = await session.scalar(
        text(
            "SELECT count(*) FROM audit.journal "
            "WHERE action = 'CREATION' AND cible_id = :r"
        ),
        {"r": ref_seule},
    )
    assert attributions == 1
