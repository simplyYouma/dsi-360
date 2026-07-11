"""Garde-fous de sécurité de la plateforme : en-têtes, frontière d'authentification, journal.

Ces tests protègent des régressions silencieuses : un en-tête retiré, une route déprotégée, un
journal rendu modifiable passeraient inaperçus sans eux.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_utilisateur, entetes


async def test_les_entetes_de_securite_sont_presents(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Défense en profondeur : chaque réponse porte les en-têtes qui bornent le navigateur."""
    admin = await creer_utilisateur(session, email="admin.sec@afgbank.ml", profil="ADMIN")

    r = await client.get("/incidents", headers=entetes(admin))

    assert r.status_code == 200, r.text
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "no-referrer"
    csp = r.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp


async def test_une_route_protegee_refuse_sans_jeton(client: AsyncClient) -> None:
    """Sans authentification, une route métier répond 401 — jamais de données en clair."""
    r = await client.get("/incidents")

    assert r.status_code == 401


async def test_un_jeton_falsifie_est_rejete(client: AsyncClient) -> None:
    """Un Bearer bricolé ne passe pas : la signature JWT est vérifiée côté serveur."""
    r = await client.get("/incidents", headers={"Authorization": "Bearer pas.un.vrai.jeton"})

    assert r.status_code == 401


async def test_le_journal_d_audit_refuse_la_modification(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Append-only : même en base, on ne peut ni modifier ni supprimer une entrée (déclencheur)."""
    admin = await creer_utilisateur(session, email="admin.sec2@afgbank.ml", profil="ADMIN")
    # Une action quelconque qui journalise.
    await client.post(
        "/auth/login", json={"email": "admin.sec2@afgbank.ml", "mot_de_passe": "x"}
    )

    with pytest.raises(Exception, match="append-only"):
        await session.execute(text("UPDATE audit.journal SET action = 'FALSIFIE'"))
    await session.rollback()

    with pytest.raises(Exception, match="append-only"):
        await session.execute(text("DELETE FROM audit.journal"))
    await session.rollback()
    assert admin  # l'admin existe : le test a bien tourné
