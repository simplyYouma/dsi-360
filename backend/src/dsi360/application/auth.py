"""Cas d'usage d'authentification (mode LOCAL). L'OIDC Entra ID viendra s'ajouter ici."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.infrastructure.repositories import utilisateur as repo
from dsi360.infrastructure.securite import verifier_mot_de_passe


def compte_actif(u: RowMapping) -> bool:
    """Compte réellement utilisable : actif (non bloqué) ET non expiré (comptes temporaires).

    Vérifié à chaque requête et à chaque rafraîchissement de jeton : bloquer ou expirer un compte
    coupe l'accès immédiatement, sans contournement possible.
    """
    if not u["actif"]:
        return False
    expire_le = u["expire_le"]
    return expire_le is None or expire_le > datetime.now(UTC)


async def authentifier(session: AsyncSession, email: str, mot_de_passe: str) -> RowMapping | None:
    """Vérifie les identifiants LOCAL. Retourne l'utilisateur si valides, sinon None."""
    u = await repo.par_email(session, email)
    if u is None or not compte_actif(u) or u["source_auth"] != "LOCAL":
        return None
    empreinte = u["mot_de_passe_hash"]
    if not empreinte or not verifier_mot_de_passe(empreinte, mot_de_passe):
        return None
    return u


async def profil_complet(session: AsyncSession, u: RowMapping) -> dict[str, Any]:
    """Construit la vue 'moi' : identité + profil + accès effectifs."""
    acces = await repo.acces_du_profil(session, u["profil"])
    return {
        "id": u["id"],
        "email": u["email"],
        "nom": u["nom"],
        "prenom": u["prenom"],
        "profil": u["profil"],
        "profil_libelle": u["profil_libelle"],
        "transverse": u["transverse"],
        "direction": u["direction"],
        "doit_changer_mdp": u["doit_changer_mdp"],
        "acces": acces,
    }
