"""Hachage des mots de passe (argon2) pour les comptes LOCAL. Cf. docs/04-SECURITY."""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hacher_mot_de_passe(clair: str) -> str:
    return _hasher.hash(clair)


def verifier_mot_de_passe(hash_stocke: str, clair: str) -> bool:
    try:
        return _hasher.verify(hash_stocke, clair)
    except VerifyMismatchError:
        return False
