"""Endpoints d'authentification : login, refresh, logout, /moi."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.auth import authentifier, compte_actif
from dsi360.config import get_settings
from dsi360.infrastructure import email, email_modeles
from dsi360.infrastructure.audit import consigner
from dsi360.infrastructure.db import session_scope
from dsi360.infrastructure.repositories import utilisateur as repo
from dsi360.infrastructure.securite import (
    creer_jeton,
    decoder_jeton,
    hacher_mot_de_passe,
    verifier_mot_de_passe,
)
from dsi360.interface.schemas import (
    ChangementMotDePasse,
    Connexion,
    Jetons,
    MoiReponse,
    MotDePasseOublie,
    Rafraichissement,
    Reinitialisation,
)
from dsi360.interface.securite import UtilisateurCourant

routeur = APIRouter(tags=["authentification"])

Session = Annotated[AsyncSession, Depends(session_scope)]

_REFRESH_INVALIDE = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="Jeton de rafraîchissement invalide."
)


def _jetons_pour(identifiant: str) -> Jetons:
    return Jetons(
        acces=creer_jeton(identifiant, "acces"),
        refresh=creer_jeton(identifiant, "refresh"),
    )


@routeur.post("/auth/login", response_model=Jetons)
async def login(corps: Connexion, requete: Request, session: Session) -> Jetons:
    u = await authentifier(session, corps.email, corps.mot_de_passe)
    if u is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Identifiants invalides."
        )
    await consigner(
        session,
        action="CONNEXION",
        acteur_id=str(u["id"]),
        acteur_email=u["email"],
        module="authentification",
        adresse_ip=requete.client.host if requete.client else None,
    )
    return _jetons_pour(str(u["id"]))


@routeur.post("/auth/refresh", response_model=Jetons)
async def refresh(corps: Rafraichissement, session: Session) -> Jetons:
    try:
        charge = decoder_jeton(corps.refresh)
    except jwt.PyJWTError as exc:
        raise _REFRESH_INVALIDE from exc
    if charge.get("type") != "refresh":
        raise _REFRESH_INVALIDE
    u = await repo.par_id(session, str(charge.get("sub")))
    if u is None or not compte_actif(u):
        raise _REFRESH_INVALIDE
    return _jetons_pour(str(u["id"]))


@routeur.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout() -> None:
    # JWT sans état : la déconnexion se fait côté client (oubli des jetons). La révocation
    # des refresh (liste noire Redis) sera ajoutée au durcissement.
    return None


@routeur.get("/moi", response_model=MoiReponse)
async def moi(courant: UtilisateurCourant) -> dict[str, Any]:
    return courant


@routeur.post("/auth/mot-de-passe", status_code=status.HTTP_204_NO_CONTENT)
async def changer_mot_de_passe(
    corps: ChangementMotDePasse, requete: Request, courant: UtilisateurCourant, session: Session
) -> None:
    u = await repo.par_id(session, courant["id"])
    if (
        u is None
        or u["source_auth"] != "LOCAL"
        or not u["mot_de_passe_hash"]
        or not verifier_mot_de_passe(u["mot_de_passe_hash"], corps.ancien)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Ancien mot de passe incorrect."
        )
    await repo.definir_mot_de_passe(session, courant["id"], hacher_mot_de_passe(corps.nouveau))
    await consigner(
        session,
        action="CHANGEMENT_MDP",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module="authentification",
        adresse_ip=requete.client.host if requete.client else None,
    )
    sujet, texte, html = email_modeles.mot_de_passe_change(courant["prenom"])
    email.envoyer(courant["email"], sujet, texte, html)


def _empreinte(jeton: str) -> str:
    return hashlib.sha256(jeton.encode()).hexdigest()


@routeur.post("/auth/mot-de-passe-oublie", status_code=status.HTTP_204_NO_CONTENT)
async def mot_de_passe_oublie(corps: MotDePasseOublie, session: Session) -> None:
    """Envoie un lien de réinitialisation. Réponse identique que le compte existe ou non
    (aucune énumération de comptes possible)."""
    u = await repo.par_email(session, corps.email)
    if u is not None and u["actif"] and u["source_auth"] == "LOCAL":
        jeton = secrets.token_urlsafe(32)
        minutes = get_settings().reset_validite_minutes
        await session.execute(
            text(
                "INSERT INTO core.reinitialisation_mdp (utilisateur_id, jeton_hash, expire_le) "
                "VALUES (cast(:uid as uuid), :h, :exp)"
            ),
            {
                "uid": u["id"],
                "h": _empreinte(jeton),
                "exp": datetime.now(UTC) + timedelta(minutes=minutes),
            },
        )
        await session.commit()
        url = f"{get_settings().url_app}/reinitialiser?jeton={jeton}"
        sujet, texte, html = email_modeles.reinitialisation(u["prenom"], url, minutes)
        email.envoyer(u["email"], sujet, texte, html)


@routeur.post("/auth/reinitialiser", status_code=status.HTTP_204_NO_CONTENT)
async def reinitialiser(corps: Reinitialisation, session: Session) -> None:
    """Consomme un jeton valide (non utilisé, non expiré) et fixe le nouveau mot de passe."""
    ligne = (
        await session.execute(
            text(
                "SELECT r.id, r.utilisateur_id::text AS uid, u.email, u.prenom "
                "FROM core.reinitialisation_mdp r "
                "JOIN core.utilisateur u ON u.id = r.utilisateur_id "
                "WHERE r.jeton_hash = :h AND r.utilise = false AND r.expire_le > now()"
            ),
            {"h": _empreinte(corps.jeton)},
        )
    ).mappings().first()
    if ligne is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Lien invalide ou expiré."
        )
    await repo.definir_mot_de_passe(session, ligne["uid"], hacher_mot_de_passe(corps.nouveau))
    await session.execute(
        text("UPDATE core.reinitialisation_mdp SET utilise = true WHERE id = :id"),
        {"id": ligne["id"]},
    )
    await consigner(
        session,
        action="RESET_MDP",
        acteur_id=ligne["uid"],
        acteur_email=ligne["email"],
        module="authentification",
    )
    await session.commit()
    sujet, texte, html = email_modeles.mot_de_passe_change(ligne["prenom"])
    email.envoyer(ligne["email"], sujet, texte, html)
