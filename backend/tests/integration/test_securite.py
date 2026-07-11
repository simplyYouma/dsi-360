"""Garde-fous de sécurité de la plateforme : en-têtes, frontière d'authentification, journal.

Ces tests protègent des régressions silencieuses : un en-tête retiré, une route déprotégée, un
journal rendu modifiable passeraient inaperçus sans eux.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.config.settings import _DEFAUT_ADMIN_MDP, _DEFAUT_JWT, Settings
from tests.integration.conftest import creer_activite, creer_utilisateur, entetes


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


async def test_le_fil_de_discussion_exige_l_acces_au_module(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Deux plans RBAC : sans l'accès au module, le fil interne d'une activité est invisible (404).

    Le fil de commentaires était la seule route générique à ne vérifier que le périmètre direction.
    """
    # Profil restreint : tout l'opérationnel SAUF « changements ».
    await session.execute(
        text(
            "INSERT INTO core.profil (code, libelle, transverse) "
            "VALUES ('RESTREINT_TEST', 'Restreint', false)"
        )
    )
    for acces in ("incidents", "demandes", "projets", "audit", "risques"):
        await session.execute(
            text("INSERT INTO core.acces_role (profil_code, acces) VALUES ('RESTREINT_TEST', :a)"),
            {"a": acces},
        )
    await session.commit()

    restreint = await creer_utilisateur(
        session, email="restreint@afgbank.ml", profil="RESTREINT_TEST"
    )
    # Profil métier par défaut : accès à tous les modules opérationnels.
    complet = await creer_utilisateur(session, email="complet.chg@afgbank.ml")
    aid = await creer_activite(session, module="changement", reference="CHG-RBAC-1")

    # Sans accès « changements », l'activité et sa discussion n'existent pas pour lui.
    refuse = await client.get(f"/commentaires/{aid}", headers=entetes(restreint))
    assert refuse.status_code == 404, refuse.text
    # Avec l'accès au module, le fil est visible.
    autorise = await client.get(f"/commentaires/{aid}", headers=entetes(complet))
    assert autorise.status_code == 200, autorise.text


def test_les_secrets_par_defaut_sont_detectes() -> None:
    """Un secret d'usine (JWT, mot de passe admin) est reconnu comme faible ; un vrai secret non."""
    fort = Settings(jwt_secret_key="un-vrai-secret", seed_admin_password="fort")
    assert fort.secrets_par_defaut() == []
    faibles = Settings(
        jwt_secret_key=_DEFAUT_JWT, seed_admin_password=_DEFAUT_ADMIN_MDP
    ).secrets_par_defaut()
    assert "DSI360_JWT_SECRET_KEY" in faibles
    assert "DSI360_SEED_ADMIN_PASSWORD" in faibles


def test_le_demarrage_refuse_un_secret_par_defaut_hors_dev(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail-closed : hors dev, l'app refuse de démarrer avec un secret laissé par défaut."""
    from dsi360.interface import app as app_mod

    faible = Settings(
        environnement="prod", jwt_secret_key=_DEFAUT_JWT, seed_admin_password=_DEFAUT_ADMIN_MDP
    )
    monkeypatch.setattr(app_mod, "get_settings", lambda: faible)
    with pytest.raises(RuntimeError, match="secret"):
        app_mod.creer_app()
