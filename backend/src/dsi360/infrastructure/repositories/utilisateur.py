"""Accès aux utilisateurs et à leurs accès (lecture). Requêtes SQL via session async."""

from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

_CHAMPS = """
    u.id::text AS id, u.email, u.nom, u.prenom, u.mot_de_passe_hash, u.actif, u.expire_le,
    u.doit_changer_mdp, u.source_auth, u.echecs_connexion, u.verrouille_jusqu_a,
    p.code AS profil, p.libelle AS profil_libelle,
    p.transverse, d.code AS direction
"""

_PAR_EMAIL = text(
    f"SELECT {_CHAMPS} FROM core.utilisateur u "
    "JOIN core.profil p ON p.id = u.profil_id "
    "LEFT JOIN core.direction d ON d.id = u.direction_id "
    "WHERE lower(u.email) = lower(:email)"
)

_PAR_ID = text(
    f"SELECT {_CHAMPS} FROM core.utilisateur u "
    "JOIN core.profil p ON p.id = u.profil_id "
    "LEFT JOIN core.direction d ON d.id = u.direction_id "
    "WHERE u.id::text = :id"
)

_ACCES = text("SELECT acces FROM core.acces_role WHERE profil_code = :profil")


async def par_email(session: AsyncSession, email: str) -> RowMapping | None:
    resultat = await session.execute(_PAR_EMAIL, {"email": email})
    return resultat.mappings().first()


async def par_id(session: AsyncSession, identifiant: str) -> RowMapping | None:
    resultat = await session.execute(_PAR_ID, {"id": identifiant})
    return resultat.mappings().first()


async def acces_du_profil(session: AsyncSession, profil_code: str) -> list[str]:
    resultat = await session.execute(_ACCES, {"profil": profil_code})
    return list(resultat.scalars().all())


_MAJ_MDP = text(
    "UPDATE core.utilisateur SET mot_de_passe_hash = :hash, doit_changer_mdp = false "
    "WHERE id::text = :id"
)


async def definir_mot_de_passe(session: AsyncSession, identifiant: str, empreinte: str) -> None:
    await session.execute(_MAJ_MDP, {"hash": empreinte, "id": identifiant})
    await session.commit()
