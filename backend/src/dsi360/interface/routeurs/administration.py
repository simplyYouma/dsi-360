"""Administration (§9) : utilisateurs, matrice d'accès, journal d'audit."""

import secrets
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.config.acces import MODULES
from dsi360.domain.texte import nom_propre
from dsi360.infrastructure import audit
from dsi360.infrastructure.db import session_scope
from dsi360.infrastructure.repositories import sla as repo_sla
from dsi360.infrastructure.repositories import utilisateur as repo_u
from dsi360.infrastructure.securite import hacher_mot_de_passe
from dsi360.interface.schemas import (
    CreationReponse,
    CreationUtilisateur,
    DirectionItem,
    MajAcces,
    MajSlaRegles,
    MajUtilisateur,
    MatriceAcces,
    PageJournal,
    PageUtilisateurs,
    ProfilItem,
    SlaRegleItem,
)
from dsi360.interface.securite import exiger_acces

routeur = APIRouter(prefix="/admin", tags=["administration"])

Session = Annotated[AsyncSession, Depends(session_scope)]
Courant = Annotated[dict[str, Any], Depends(exiger_acces("administration"))]
_TAILLE = 15


# --- Référentiels pour les formulaires ---


@routeur.get("/profils", response_model=list[ProfilItem])
async def profils(courant: Courant, session: Session) -> list[dict[str, Any]]:
    r = await session.execute(text("SELECT code, libelle FROM core.profil ORDER BY libelle"))
    return [dict(x) for x in r.mappings().all()]


@routeur.get("/directions", response_model=list[DirectionItem])
async def directions(courant: Courant, session: Session) -> list[dict[str, Any]]:
    r = await session.execute(text("SELECT code, libelle FROM core.direction ORDER BY libelle"))
    return [dict(x) for x in r.mappings().all()]


# --- Utilisateurs ---

_CHAMPS_U = (
    "u.id::text AS id, u.email, u.nom, u.prenom, p.code AS profil, p.libelle AS profil_libelle, "
    "d.code AS direction, u.actif, u.doit_changer_mdp"
)
_BASE_U = (
    "FROM core.utilisateur u JOIN core.profil p ON p.id = u.profil_id "
    "LEFT JOIN core.direction d ON d.id = u.direction_id"
)


@routeur.get("/utilisateurs", response_model=PageUtilisateurs)
async def lister_utilisateurs(
    courant: Courant, session: Session, page: Annotated[int, Query(ge=1)] = 1
) -> dict[str, Any]:
    total = await session.scalar(text("SELECT count(*) FROM core.utilisateur")) or 0
    lignes = await session.execute(
        text(f"SELECT {_CHAMPS_U} {_BASE_U} ORDER BY u.nom, u.prenom LIMIT :l OFFSET :o"),
        {"l": _TAILLE, "o": (page - 1) * _TAILLE},
    )
    return {
        "elements": [dict(x) for x in lignes.mappings().all()],
        "total": total,
        "page": page,
        "taille": _TAILLE,
    }


@routeur.post("/utilisateurs", response_model=CreationReponse, status_code=status.HTTP_201_CREATED)
async def creer_utilisateur(
    corps: CreationUtilisateur, courant: Courant, session: Session
) -> dict[str, str]:
    if await session.scalar(
        text("SELECT 1 FROM core.utilisateur WHERE lower(email) = lower(:e)"), {"e": corps.email}
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail déjà utilisé.")
    ident = await session.scalar(
        text(
            "INSERT INTO core.utilisateur"
            "(email, nom, prenom, profil_id, direction_id, source_auth, mot_de_passe_hash, "
            " doit_changer_mdp) VALUES (:email, :nom, :prenom, "
            " (SELECT id FROM core.profil WHERE code = :profil), "
            " (SELECT id FROM core.direction WHERE code = :direction), 'LOCAL', :hash, true) "
            "RETURNING id::text"
        ),
        {
            "email": corps.email,
            "nom": nom_propre(corps.nom),
            "prenom": nom_propre(corps.prenom),
            "profil": corps.profil_code,
            "direction": corps.direction_code,
            "hash": hacher_mot_de_passe(corps.mot_de_passe),
        },
    )
    await audit.consigner(
        session,
        action="CREATION",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module="administration",
        cible_type="utilisateur",
        cible_id=corps.email,
    )
    return {"id": str(ident)}


@routeur.put("/utilisateurs/{ident}", status_code=status.HTTP_204_NO_CONTENT)
async def modifier_utilisateur(
    ident: str, corps: MajUtilisateur, courant: Courant, session: Session
) -> None:
    existe = await session.scalar(
        text("SELECT 1 FROM core.utilisateur WHERE id::text = :id"), {"id": ident}
    )
    if existe is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable."
        )
    await session.execute(
        text(
            "UPDATE core.utilisateur SET nom = :nom, prenom = :prenom, actif = :actif, "
            "profil_id = (SELECT id FROM core.profil WHERE code = :profil), "
            "direction_id = (SELECT id FROM core.direction WHERE code = :direction) "
            "WHERE id::text = :id"
        ),
        {
            "id": ident,
            "nom": nom_propre(corps.nom),
            "prenom": nom_propre(corps.prenom),
            "actif": corps.actif,
            "profil": corps.profil_code,
            "direction": corps.direction_code,
        },
    )
    await audit.consigner(
        session,
        action="MODIFICATION",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module="administration",
        cible_type="utilisateur",
        cible_id=ident,
    )


@routeur.post("/utilisateurs/{ident}/reinitialiser-mdp")
async def reinitialiser_mdp(ident: str, courant: Courant, session: Session) -> dict[str, str]:
    temporaire = secrets.token_urlsafe(9)
    u = await repo_u.par_id(session, ident)
    if u is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable."
        )
    await repo_u.definir_mot_de_passe(session, ident, hacher_mot_de_passe(temporaire))
    await session.execute(
        text("UPDATE core.utilisateur SET doit_changer_mdp = true WHERE id::text = :id"),
        {"id": ident},
    )
    await audit.consigner(
        session,
        action="REINITIALISATION_MDP",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module="administration",
        cible_type="utilisateur",
        cible_id=u["email"],
    )
    return {"mot_de_passe_temporaire": temporaire}


# --- Matrice d'accès ---


@routeur.get("/acces", response_model=MatriceAcces)
async def matrice_acces(courant: Courant, session: Session) -> dict[str, Any]:
    profils_l = (
        await session.execute(text("SELECT code, libelle FROM core.profil ORDER BY libelle"))
    ).mappings().all()
    acces_l = (
        await session.execute(text("SELECT profil_code, acces FROM core.acces_role"))
    ).all()
    par_profil: dict[str, list[str]] = {}
    for profil_code, acces in acces_l:
        par_profil.setdefault(profil_code, []).append(acces)
    roles = [
        {"profil": p["code"], "libelle": p["libelle"], "acces": par_profil.get(p["code"], [])}
        for p in profils_l
    ]
    return {"modules": list(MODULES), "roles": roles}


@routeur.put("/acces", status_code=status.HTTP_204_NO_CONTENT)
async def definir_acces(corps: MajAcces, courant: Courant, session: Session) -> None:
    await session.execute(
        text("DELETE FROM core.acces_role WHERE profil_code = :p"), {"p": corps.profil}
    )
    for acces in corps.acces:
        if acces in MODULES:
            await session.execute(
                text("INSERT INTO core.acces_role(profil_code, acces) VALUES (:p, :a)"),
                {"p": corps.profil, "a": acces},
            )
    await audit.consigner(
        session,
        action="MODIFICATION",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module="administration",
        cible_type="acces_role",
        cible_id=corps.profil,
    )
    await session.commit()


# --- Journal d'audit ---


@routeur.get("/journal", response_model=PageJournal)
async def lister_journal(
    courant: Courant, session: Session, page: Annotated[int, Query(ge=1)] = 1
) -> dict[str, Any]:
    total = await session.scalar(text("SELECT count(*) FROM audit.journal")) or 0
    lignes = await session.execute(
        text(
            "SELECT horodatage, acteur_email AS acteur, module, action, "
            "coalesce(cible_id, cible_type) AS cible FROM audit.journal "
            "ORDER BY id DESC LIMIT :l OFFSET :o"
        ),
        {"l": _TAILLE, "o": (page - 1) * _TAILLE},
    )
    return {
        "elements": [dict(x) for x in lignes.mappings().all()],
        "total": total,
        "page": page,
        "taille": _TAILLE,
    }


# --- Règles SLA paramétrables (par priorité) ---


@routeur.get("/sla", response_model=list[SlaRegleItem])
async def lister_sla(courant: Courant, session: Session) -> list[dict[str, Any]]:
    return await repo_sla.lister(session)


@routeur.put("/sla", status_code=status.HTTP_204_NO_CONTENT)
async def definir_sla(corps: MajSlaRegles, courant: Courant, session: Session) -> None:
    for r in corps.regles:
        await repo_sla.definir(session, r.priorite, r.prise_en_charge_minutes, r.resolution_minutes)
    await audit.consigner(
        session,
        action="MAJ_SLA",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module="administration",
        cible_type="sla_regle",
        nouvelle={"regles": [r.model_dump() for r in corps.regles]},
    )
    await session.commit()
