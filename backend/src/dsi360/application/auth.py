"""Cas d'usage d'authentification (mode LOCAL). L'OIDC Entra ID viendra s'ajouter ici."""

import hashlib
import math
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.config import get_settings
from dsi360.infrastructure import email as email_infra
from dsi360.infrastructure import email_modeles
from dsi360.infrastructure.repositories import utilisateur as repo
from dsi360.infrastructure.securite import verifier_mot_de_passe


def empreinte_jeton(jeton: str) -> str:
    """Empreinte SHA-256 stockée en base (le jeton en clair n'est jamais persisté)."""
    return hashlib.sha256(jeton.encode()).hexdigest()


async def envoyer_lien_mot_de_passe(
    session: AsyncSession,
    *,
    utilisateur_id: str,
    prenom: str,
    email_destinataire: str,
    minutes: int,
    bienvenue: bool,
) -> None:
    """Crée un jeton à usage unique et envoie le lien de (ré)définition du mot de passe.

    `bienvenue=True` : e-mail d'activation de compte (1er mot de passe). `bienvenue=False` :
    réinitialisation. Le jeton expire au bout de `minutes`. La transaction est validée ici pour
    garantir que le jeton est persistant avant l'envoi de l'e-mail.
    """
    jeton = secrets.token_urlsafe(32)
    await session.execute(
        text(
            "INSERT INTO core.reinitialisation_mdp (utilisateur_id, jeton_hash, expire_le) "
            "VALUES (cast(:uid as uuid), :h, :exp)"
        ),
        {
            "uid": utilisateur_id,
            "h": empreinte_jeton(jeton),
            "exp": datetime.now(UTC) + timedelta(minutes=minutes),
        },
    )
    await session.commit()
    url = f"{get_settings().url_app}/reinitialiser?jeton={jeton}"
    if bienvenue:
        sujet, corps, html = email_modeles.definir_mot_de_passe(
            prenom, email_destinataire, url, minutes
        )
    else:
        sujet, corps, html = email_modeles.reinitialisation(prenom, url, minutes)
    email_infra.envoyer(email_destinataire, sujet, corps, html)


def compte_actif(u: RowMapping) -> bool:
    """Compte réellement utilisable : actif (non bloqué) ET non expiré (comptes temporaires).

    Vérifié à chaque requête et à chaque rafraîchissement de jeton : bloquer ou expirer un compte
    coupe l'accès immédiatement, sans contournement possible.
    """
    if not u["actif"]:
        return False
    expire_le = u["expire_le"]
    return expire_le is None or expire_le > datetime.now(UTC)


class CompteVerrouille(Exception):
    """Trop d'échecs consécutifs : la porte reste close, même avec le bon mot de passe."""

    def __init__(self, secondes: int) -> None:
        super().__init__(f"Compte verrouillé pour {secondes} secondes.")
        self.secondes = secondes


def _secondes_de_verrou(u: RowMapping) -> int:
    """Secondes restantes avant réouverture. 0 si le compte n'est pas verrouillé."""
    jusqu_a = u["verrouille_jusqu_a"]
    if jusqu_a is None:
        return 0
    restant = (jusqu_a - datetime.now(UTC)).total_seconds()
    # Arrondi au-dessus : ne jamais annoncer zéro seconde d'attente sur un verrou encore actif.
    return max(0, math.ceil(float(restant)))


# Au seuil, on verrouille et on repart de zéro : le verrou expiré, l'agent retrouve ses essais.
_ECHEC = text(
    "UPDATE core.utilisateur SET "
    " echecs_connexion = CASE WHEN echecs_connexion + 1 >= :maxi "
    "                         THEN 0 ELSE echecs_connexion + 1 END, "
    " verrouille_jusqu_a = CASE WHEN echecs_connexion + 1 >= :maxi "
    "                          THEN cast(:jusqu_a as timestamptz) END "
    "WHERE id = cast(:uid as uuid)"
)

_SUCCES = text(
    "UPDATE core.utilisateur SET echecs_connexion = 0, verrouille_jusqu_a = NULL "
    "WHERE id = cast(:uid as uuid)"
)


async def _enregistrer_echec(session: AsyncSession, utilisateur_id: str) -> None:
    """Incrémente le compteur d'échecs, et verrouille le compte au seuil.

    L'écriture n'est pas validée ici : l'appelant journalise la tentative, et `audit.consigner`
    valide la transaction. Sans cette journalisation, le compteur serait perdu avec le 401.
    """
    s = get_settings()
    await session.execute(
        _ECHEC,
        {
            "maxi": s.login_echecs_max,
            "jusqu_a": datetime.now(UTC) + timedelta(minutes=s.login_verrou_minutes),
            "uid": utilisateur_id,
        },
    )


async def authentifier(session: AsyncSession, email: str, mot_de_passe: str) -> RowMapping | None:
    """Vérifie les identifiants LOCAL. Retourne l'utilisateur si valides, sinon None.

    Lève `CompteVerrouille` si le compte a été martelé : le verrou prime sur le mot de passe, sinon
    l'attaquant saurait, en tombant juste, qu'il a trouvé le bon.

    Un e-mail inconnu ne fait rien écrire : ni compteur, ni verrou. Le système ne doit pas révéler,
    par son comportement, quels comptes existent.
    """
    u = await repo.par_email(session, email)
    if u is None or not compte_actif(u) or u["source_auth"] != "LOCAL":
        return None

    secondes = _secondes_de_verrou(u)
    if secondes:
        raise CompteVerrouille(secondes)

    empreinte = u["mot_de_passe_hash"]
    if not empreinte or not verifier_mot_de_passe(empreinte, mot_de_passe):
        await _enregistrer_echec(session, u["id"])
        return None

    # Une connexion réussie efface les traces : compteur et verrou expiré.
    if u["echecs_connexion"] or u["verrouille_jusqu_a"] is not None:
        await session.execute(_SUCCES, {"uid": u["id"]})
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
