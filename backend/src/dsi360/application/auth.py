"""Cas d'usage d'authentification (mode LOCAL). L'OIDC Entra ID viendra s'ajouter ici."""

from typing import Any

from sqlalchemy import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.infrastructure.repositories import utilisateur as repo
from dsi360.infrastructure.securite import verifier_mot_de_passe


async def authentifier(session: AsyncSession, email: str, mot_de_passe: str) -> RowMapping | None:
    """Vérifie les identifiants LOCAL. Retourne l'utilisateur si valides, sinon None."""
    u = await repo.par_email(session, email)
    if u is None or not u["actif"] or u["source_auth"] != "LOCAL":
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
