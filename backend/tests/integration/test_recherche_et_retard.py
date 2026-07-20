"""Deux règles de liste : la recherche passe outre les filtres, et « En retard » est une vue.

Chercher, c'est vouloir retrouver un dossier — pas fouiller la vue courante. Si la recherche
restait prisonnière du filtre d'état, un ticket clôturé serait introuvable tant que la liste
affiche « En cours » : l'écran mentirait par omission.
"""

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_activite, creer_utilisateur, entetes


async def test_la_recherche_trouve_au_dela_du_filtre_d_etat(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Un ticket clôturé se retrouve même quand la liste est filtrée sur « En cours »."""
    admin = await creer_utilisateur(session, email="admin.rech@afgbank.ml", profil="ADMIN")
    clos = await creer_activite(session, module="changement", reference="CHG-RECH-CLOS")
    await session.execute(
        text("UPDATE core.activite SET statut = 'Clôturé' WHERE id = cast(:i as uuid)"),
        {"i": clos},
    )
    await session.commit()

    # Sans recherche, la vue « en cours » le cache — c'est son rôle.
    r = await client.get("/changements?etat=en_cours", headers=entetes(admin))
    assert r.status_code == 200, r.text
    assert "CHG-RECH-CLOS" not in {e["reference"] for e in r.json()["elements"]}

    # Avec recherche, il se retrouve : la recherche prime sur le filtre.
    r = await client.get("/changements?etat=en_cours&q=CHG-RECH-CLOS", headers=entetes(admin))
    assert r.status_code == 200, r.text
    assert "CHG-RECH-CLOS" in {e["reference"] for e in r.json()["elements"]}


async def test_la_recherche_trouve_au_dela_du_filtre_par_personne(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Chercher le ticket d'un collègue aboutit, même la liste filtrée sur quelqu'un d'autre."""
    admin = await creer_utilisateur(session, email="admin.rech2@afgbank.ml", profil="ADMIN")
    agent = await creer_utilisateur(session, email="agent.rech2@afgbank.ml")
    autre = await creer_utilisateur(session, email="autre.rech2@afgbank.ml")
    await creer_activite(
        session, module="changement", reference="CHG-RECH-AUTRE", responsable_id=autre
    )

    r = await client.get(
        f"/changements?responsable_id={agent}&q=CHG-RECH-AUTRE", headers=entetes(admin)
    )

    assert r.status_code == 200, r.text
    assert "CHG-RECH-AUTRE" in {e["reference"] for e in r.json()["elements"]}


async def test_la_recherche_ne_franchit_jamais_la_direction(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Elle passe outre les filtres de confort, jamais le cloisonnement : c'est de la sécurité."""
    autre_dir = await session.scalar(
        text(
            "INSERT INTO core.direction (code, libelle) VALUES ('AUTRE-RECH', 'Autre') "
            "ON CONFLICT (code) DO UPDATE SET libelle = excluded.libelle RETURNING id::text"
        )
    )
    await session.commit()
    lecteur = await creer_utilisateur(session, email="lecteur.rech@afgbank.ml")
    cache = await creer_activite(session, module="changement", reference="CHG-RECH-HORS")
    await session.execute(
        text(
            "UPDATE core.activite SET direction_id = cast(:d as uuid) WHERE id = cast(:i as uuid)"
        ),
        {"d": autre_dir, "i": cache},
    )
    await session.commit()

    r = await client.get("/changements?q=CHG-RECH-HORS", headers=entetes(lecteur))

    assert r.status_code == 200, r.text
    assert "CHG-RECH-HORS" not in {e["reference"] for e in r.json()["elements"]}


async def test_le_retard_est_un_axe_a_part_croisable_avec_la_phase(
    client: AsyncClient, session: AsyncSession
) -> None:
    """« En retard » = pas encore résolu et échéance passée. C'est une horloge, pas une phase :
    elle se croise avec la vue courante au lieu de la remplacer."""
    admin = await creer_utilisateur(session, email="admin.retard@afgbank.ml", profil="ADMIN")
    retard = await creer_activite(session, module="changement", reference="CHG-RET-OUI")
    a_temps = await creer_activite(session, module="changement", reference="CHG-RET-NON")
    await session.execute(
        text(
            "UPDATE core.activite SET sla_resolution_le = now() - interval '2 days' "
            "WHERE id = cast(:i as uuid)"
        ),
        {"i": retard},
    )
    await session.execute(
        text(
            "UPDATE core.activite SET sla_resolution_le = now() + interval '2 days' "
            "WHERE id = cast(:i as uuid)"
        ),
        {"i": a_temps},
    )
    await session.commit()

    r = await client.get("/changements?retard=true", headers=entetes(admin))

    assert r.status_code == 200, r.text
    refs = {e["reference"] for e in r.json()["elements"]}
    assert "CHG-RET-OUI" in refs, "échéance dépassée, non résolu"
    assert "CHG-RET-NON" not in refs, "encore dans les temps"

    # Croisé avec la phase : « en cours ET en retard », ce que l'ancien segment interdisait.
    r = await client.get("/changements?etat=en_cours&retard=true", headers=entetes(admin))
    assert r.status_code == 200, r.text
    assert "CHG-RET-OUI" in {e["reference"] for e in r.json()["elements"]}
