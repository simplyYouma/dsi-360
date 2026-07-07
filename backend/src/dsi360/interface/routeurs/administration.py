"""Administration (§9) : utilisateurs, matrice d'accès, journal d'audit."""

import re
import secrets
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.config import get_settings
from dsi360.config.acces import MODULES
from dsi360.domain.sla import MODULES_SLA
from dsi360.domain.texte import nom_propre
from dsi360.infrastructure import audit, email, email_modeles
from dsi360.infrastructure.db import session_scope
from dsi360.infrastructure.repositories import groupe_support as repo_groupe
from dsi360.infrastructure.repositories import sla as repo_sla
from dsi360.infrastructure.repositories import utilisateur as repo_u
from dsi360.infrastructure.securite import hacher_mot_de_passe
from dsi360.interface.schemas import (
    CategorieItem,
    CreationCategorie,
    CreationReponse,
    CreationUtilisateur,
    DirectionItem,
    GroupeSupportItem,
    MajAcces,
    MajGroupeSupport,
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


# --- Catégories (paramétrage) ---

# Modules dont les catégories sont un vocabulaire fixe (non éditable). Le « type » de changement
# (Standard/Normal/Urgent) pilote le circuit CAB/ECAB et le calcul de priorité : il ne s'ajoute ni
# ne se supprime.
_MODULES_CATEGORIE_VERROUILLES: frozenset[str] = frozenset({"changement"})


def _code_categorie(libelle: str) -> str:
    """Code technique stable dérivé du libellé (MAJUSCULES, alphanumérique, séparé par '_')."""
    code = re.sub(r"[^A-Z0-9]+", "_", libelle.upper()).strip("_")
    if not code:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Libellé de catégorie invalide.",
        )
    return code


@routeur.post("/categories", response_model=CategorieItem, status_code=status.HTTP_201_CREATED)
async def creer_categorie(
    corps: CreationCategorie, courant: Courant, session: Session
) -> dict[str, str]:
    if corps.module not in MODULES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Module inconnu."
        )
    if corps.module in _MODULES_CATEGORIE_VERROUILLES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Les types de ce module sont fixes et ne peuvent pas être ajoutés.",
        )
    libelle = corps.libelle.strip()
    code = _code_categorie(libelle)
    if await session.scalar(
        text("SELECT 1 FROM core.categorie WHERE module = :m AND code = :c"),
        {"m": corps.module, "c": code},
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Cette catégorie existe déjà."
        )
    ligne = (
        await session.execute(
            text(
                "INSERT INTO core.categorie (module, code, libelle) VALUES (:m, :c, :l) "
                "RETURNING id::text AS id, code, libelle"
            ),
            {"m": corps.module, "c": code, "l": libelle},
        )
    ).mappings().one()
    await audit.consigner(
        session,
        action="CREATION",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module="administration",
        cible_type="categorie",
        cible_id=f"{corps.module}/{libelle}",
        nouvelle={"module": corps.module, "code": code, "libelle": libelle},
    )
    return dict(ligne)


@routeur.delete("/categories/{ident}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer_categorie(ident: str, courant: Courant, session: Session) -> None:
    cat = (
        await session.execute(
            text("SELECT module, libelle FROM core.categorie WHERE id = cast(:id as uuid)"),
            {"id": ident},
        )
    ).mappings().first()
    if cat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catégorie introuvable.")
    if cat["module"] in _MODULES_CATEGORIE_VERROUILLES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Les types de ce module sont fixes et ne peuvent pas être supprimés.",
        )
    utilisee = await session.scalar(
        text("SELECT count(*) FROM core.activite WHERE categorie_id = cast(:id as uuid)"),
        {"id": ident},
    )
    if utilisee:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Catégorie utilisée par des activités — impossible de la supprimer.",
        )
    ligne = (
        await session.execute(
            text(
                "DELETE FROM core.categorie WHERE id = cast(:id as uuid) "
                "RETURNING module, libelle"
            ),
            {"id": ident},
        )
    ).mappings().first()
    if ligne is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catégorie introuvable.")
    await audit.consigner(
        session,
        action="SUPPRESSION",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module="administration",
        cible_type="categorie",
        cible_id=f"{ligne['module']}/{ligne['libelle']}",
        ancienne={"module": ligne["module"], "libelle": ligne["libelle"]},
    )


# --- Utilisateurs ---

_CHAMPS_U = (
    "u.id::text AS id, u.email, u.nom, u.prenom, p.code AS profil, p.libelle AS profil_libelle, "
    "d.code AS direction, u.actif, u.expire_le, u.doit_changer_mdp"
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


def _valider_domaine_email(email: str) -> None:
    """Impose un domaine e-mail professionnel autorisé (paramétrable). Rejette sinon."""
    domaines = get_settings().domaines_email
    if not domaines:
        return
    _, _, domaine = email.partition("@")
    if domaine.lower() not in domaines:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"E-mail non autorisé : domaine attendu {', '.join(domaines)}.",
        )


@routeur.post("/utilisateurs", response_model=CreationReponse, status_code=status.HTTP_201_CREATED)
async def creer_utilisateur(
    corps: CreationUtilisateur, courant: Courant, session: Session
) -> dict[str, str]:
    _valider_domaine_email(corps.email)
    if await session.scalar(
        text("SELECT 1 FROM core.utilisateur WHERE lower(email) = lower(:e)"), {"e": corps.email}
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail déjà utilisé.")
    ident = await session.scalar(
        text(
            "INSERT INTO core.utilisateur"
            "(email, nom, prenom, profil_id, direction_id, source_auth, mot_de_passe_hash, "
            " doit_changer_mdp, expire_le) VALUES (:email, :nom, :prenom, "
            " (SELECT id FROM core.profil WHERE code = :profil), "
            " (SELECT id FROM core.direction WHERE code = :direction), 'LOCAL', :hash, true, "
            " :expire_le) "
            "RETURNING id::text"
        ),
        {
            "email": corps.email,
            "nom": nom_propre(corps.nom),
            "prenom": nom_propre(corps.prenom),
            "profil": corps.profil_code,
            "direction": corps.direction_code,
            "hash": hacher_mot_de_passe(corps.mot_de_passe),
            "expire_le": corps.expire_le,
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
    sujet, texte, html = email_modeles.bienvenue(
        corps.prenom, corps.email, corps.mot_de_passe, f"{get_settings().url_app}/"
    )
    email.envoyer(corps.email, sujet, texte, html)
    return {"id": str(ident)}


@routeur.put("/utilisateurs/{ident}", status_code=status.HTTP_204_NO_CONTENT)
async def modifier_utilisateur(
    ident: str, corps: MajUtilisateur, courant: Courant, session: Session
) -> None:
    avant = (
        await session.execute(
            text("SELECT actif, email, prenom FROM core.utilisateur WHERE id::text = :id"),
            {"id": ident},
        )
    ).mappings().first()
    if avant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable."
        )
    # Garde : un administrateur ne peut ni se bloquer ni se donner une expiration (anti-lockout).
    if ident == str(courant["id"]) and (not corps.actif or corps.expire_le is not None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas bloquer ou faire expirer votre propre compte.",
        )
    await session.execute(
        text(
            "UPDATE core.utilisateur SET nom = :nom, prenom = :prenom, actif = :actif, "
            "expire_le = :expire_le, "
            "profil_id = (SELECT id FROM core.profil WHERE code = :profil), "
            "direction_id = (SELECT id FROM core.direction WHERE code = :direction) "
            "WHERE id::text = :id"
        ),
        {
            "id": ident,
            "nom": nom_propre(corps.nom),
            "prenom": nom_propre(corps.prenom),
            "actif": corps.actif,
            "expire_le": corps.expire_le,
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
    # Notifie l'utilisateur si son accès vient d'être bloqué.
    if avant["actif"] and not corps.actif:
        sujet, texte, html = email_modeles.compte_bloque(avant["prenom"])
        email.envoyer(avant["email"], sujet, texte, html)


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


# --- Groupes de support (N1/N2/N3) ---


@routeur.get("/groupes-support", response_model=list[GroupeSupportItem])
async def lister_groupes_support(courant: Courant, session: Session) -> list[dict[str, Any]]:
    """Les niveaux de support et leurs membres (l'escalade réaffecte au niveau cible)."""
    return await repo_groupe.lister(session)


@routeur.put("/groupes-support", status_code=status.HTTP_204_NO_CONTENT)
async def definir_groupe_support(
    corps: MajGroupeSupport, courant: Courant, session: Session
) -> None:
    ok = await repo_groupe.definir_membres(
        session, corps.direction, corps.niveau, corps.utilisateur_ids
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Niveau de support inconnu pour cette direction.",
        )
    await audit.consigner(
        session,
        action="MODIFICATION",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module="administration",
        cible_type="groupe_support",
        cible_id=f"{corps.direction}/N{corps.niveau}",
        nouvelle={
            "direction": corps.direction,
            "niveau": corps.niveau,
            "membres": corps.utilisateur_ids,
        },
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


# --- Règles SLA paramétrables (par module + priorité) ---


def _valider_module_sla(module: str) -> None:
    if module not in MODULES_SLA:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Module SLA inconnu. Attendu : {', '.join(MODULES_SLA)}.",
        )


@routeur.get("/sla/modules", response_model=list[str])
async def lister_modules_sla(courant: Courant) -> list[str]:
    """Modules dont les cibles SLA sont paramétrables (un incident P1 ≠ une demande P1)."""
    return list(MODULES_SLA)


@routeur.get("/sla", response_model=list[SlaRegleItem])
async def lister_sla(
    courant: Courant, session: Session, module: Annotated[str, Query()]
) -> list[dict[str, Any]]:
    _valider_module_sla(module)
    return await repo_sla.lister(session, module)


@routeur.put("/sla", status_code=status.HTTP_204_NO_CONTENT)
async def definir_sla(corps: MajSlaRegles, courant: Courant, session: Session) -> None:
    _valider_module_sla(corps.module)
    for r in corps.regles:
        await repo_sla.definir(
            session, corps.module, r.priorite, r.prise_en_charge_minutes, r.resolution_minutes
        )
    await audit.consigner(
        session,
        action="MAJ_SLA",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module="administration",
        cible_type="sla_regle",
        cible_id=corps.module,
        nouvelle={"module": corps.module, "regles": [r.model_dump() for r in corps.regles]},
    )
    await session.commit()
