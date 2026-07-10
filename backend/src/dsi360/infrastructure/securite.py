"""Sécurité : hachage des mots de passe (argon2) et jetons JWT. Cf. docs/04-SECURITY."""

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from dsi360.config import get_settings

_hasher = PasswordHasher()
_ALGO = "HS256"
_JOURS_REFRESH = 7

TypeJeton = Literal["acces", "refresh"]


def hacher_mot_de_passe(clair: str) -> str:
    return _hasher.hash(clair)


def verifier_mot_de_passe(hash_stocke: str, clair: str) -> bool:
    try:
        return _hasher.verify(hash_stocke, clair)
    except VerifyMismatchError:
        return False


def creer_jeton(sujet: str, type_jeton: TypeJeton, incarne_par: str | None = None) -> str:
    """`incarne_par` : e-mail de l'administrateur qui a pris cette identité (développement seul).

    Le jeton porte la marque, sinon le serveur ne pourrait pas distinguer un agent d'un
    administrateur déguisé — et refuser à ce dernier ce qui touche aux secrets de l'agent.
    """
    settings = get_settings()
    maintenant = datetime.now(UTC)
    duree = (
        timedelta(minutes=settings.jwt_acces_minutes)
        if type_jeton == "acces"
        else timedelta(days=_JOURS_REFRESH)
    )
    charge = {"sub": sujet, "type": type_jeton, "iat": maintenant, "exp": maintenant + duree}
    if incarne_par is not None:
        charge["incarne_par"] = incarne_par
    return jwt.encode(charge, settings.jwt_secret_key, algorithm=_ALGO)


def decoder_jeton(jeton: str) -> dict[str, Any]:
    """Décode et valide le jeton (signature + expiration). Lève jwt.PyJWTError si invalide."""
    return jwt.decode(jeton, get_settings().jwt_secret_key, algorithms=[_ALGO])
