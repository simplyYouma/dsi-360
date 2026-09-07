"""Administration (§9) : utilisateurs, matrice d'accès, journal d'audit."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.auth import envoyer_lien_mot_de_passe
from dsi360.config import get_settings
from dsi360.config.acces import MODULES, PROFIL_ADMIN
from dsi360.domain.sla import MODULES_SLA
from dsi360.domain.texte import code_technique, nom_propre
from dsi360.infrastructure import audit, email, email_modeles
from dsi360.infrastructure.db import session_scope
from dsi360.infrastructure.export import vers_csv, vers_xlsx
from dsi360.infrastructure.repositories import sla as repo_sla
from dsi360.infrastructure.repositories import utilisateur as repo_u
from dsi360.interface.schemas import (
    CategorieItem,
    CreationCategorie,
    CreationDepartement,
    CreationProfil,
    CreationReponse,
    CreationUtilisateur,
    DepartementItem,
    DirectionItem,
    MajAcces,
    MajDepartement,
    MajProfil,
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
async def profils(
    courant: Courant,
    session: Session,
    direction: Annotated[str | None, Query()] = None,
) -> list[dict[str, Any]]:
    """Les profils, avec leur département. `?direction=DSI` ne garde que ceux de cette direction.

    Les profils **transverses** restent listés quoi qu'il arrive : ils n'appartiennent à aucun
    département, donc à aucune direction — les filtrer ferait disparaître `ADMIN` du formulaire de
    création de compte, et personne ne pourrait plus nommer d'administrateur.
    """
    cond = ""
    params: dict[str, Any] = {}
    if direction is not None:
        cond = " WHERE p.transverse OR dir.code = :direction"
        params["direction"] = direction
    r = await session.execute(
        text(
            "SELECT p.code, p.libelle, p.transverse, dep.id::text AS departement_id, "
            "       dep.libelle AS departement "
            "FROM core.profil p "
            "LEFT JOIN core.departement dep ON dep.id = p.departement_id "
            "LEFT JOIN core.direction dir ON dir.id = dep.direction_id"
            f"{cond} ORDER BY p.libelle"
        ),
        params,
    )
    return [dict(x) for x in r.mappings().all()]


# --- Profils (paramétrage, cf. ADR-0003 §1) ---
#
# Les profils sont un paramétrage, pas un vocabulaire figé : on en ajoute, on en renomme, on en
# supprime. Deux garde-fous, tous deux côté serveur :
#   - un profil auquel des comptes sont rattachés ne se supprime pas (on perdrait leurs droits) ;
#   - ADMIN ne se supprime pas et reste transverse — sinon plus personne n'administre la
#     plateforme, et aucun écran ne permettrait de revenir en arrière.


async def _profil_ou_404(session: AsyncSession, code: str) -> dict[str, Any]:
    ligne = (
        await session.execute(
            text(
                "SELECT code, libelle, transverse, departement_id::text AS departement_id "
                "FROM core.profil WHERE code = :c"
            ),
            {"c": code},
        )
    ).mappings().first()
    if ligne is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profil introuvable.")
    return dict(ligne)


async def _exiger_profil_unique(
    session: AsyncSession, *, code: str, libelle: str, sauf: str | None = None
) -> None:
    """Refuse un code ou un libellé déjà pris.

    Le libellé compte autant que le code : « Administrateur » donnerait le code ADMINISTRATEUR,
    distinct d'ADMIN, et la liste afficherait deux profils au nom identique.
    """
    conflit = await session.scalar(
        text(
            "SELECT code FROM core.profil "
            "WHERE (code = :code OR lower(libelle) = lower(:libelle)) "
            "AND (cast(:sauf as text) IS NULL OR code <> :sauf) LIMIT 1"
        ),
        {"code": code, "libelle": libelle, "sauf": sauf},
    )
    if conflit is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Ce profil existe déjà."
        )


@routeur.post("/profils", response_model=ProfilItem, status_code=status.HTTP_201_CREATED)
async def creer_profil(corps: CreationProfil, courant: Courant, session: Session) -> dict[str, Any]:
    libelle = corps.libelle.strip()
    code = _code_technique(libelle, "profil")
    await _exiger_profil_unique(session, code=code, libelle=libelle)
    ligne = (
        await session.execute(
            text(
                "INSERT INTO core.profil (code, libelle, transverse, departement_id) "
                "VALUES (:c, :l, :t, cast(:d as uuid)) "
                "RETURNING code, libelle, transverse, departement_id::text AS departement_id"
            ),
            {"c": code, "l": libelle, "t": corps.transverse, "d": corps.departement_id},
        )
    ).mappings().one()
    # Aucun accès n'est accordé : sécurité par défaut, l'administrateur ouvre ensuite les modules.
    await audit.consigner(
        session,
        action="CREATION",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module="administration",
        cible_type="profil",
        cible_id=code,
        nouvelle={
            "code": code,
            "libelle": libelle,
            "transverse": corps.transverse,
            "departement_id": corps.departement_id,
        },
    )
    await session.commit()
    return dict(ligne)


@routeur.patch("/profils/{code}", response_model=ProfilItem)
async def modifier_profil(
    code: str, corps: MajProfil, courant: Courant, session: Session
) -> dict[str, Any]:
    avant = await _profil_ou_404(session, code)
    libelle = corps.libelle.strip()
    # Le code technique ne bouge pas avec le libellé : il est référencé par core.acces_role et par
    # les comptes. Renommer « Réseau télécom » n'en fait pas un autre profil.
    await _exiger_profil_unique(session, code=code, libelle=libelle, sauf=code)
    transverse = avant["transverse"] if corps.transverse is None else corps.transverse
    if code == PROFIL_ADMIN and not transverse:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="L'administrateur doit rester transverse.",
        )
    # Omis = inchangé. Sans `exclude_unset`, un PATCH qui ne parle que du libellé détacherait le
    # profil de son département sans que personne ne l'ait demandé.
    fournis = corps.model_dump(exclude_unset=True)
    departement_id = (
        fournis["departement_id"] if "departement_id" in fournis else avant["departement_id"]
    )
    if departement_id is not None:
        await _departement_ou_404(session, departement_id)
    ligne = (
        await session.execute(
            text(
                "UPDATE core.profil SET libelle = :l, transverse = :t, "
                "       departement_id = cast(:d as uuid) WHERE code = :c "
                "RETURNING code, libelle, transverse, departement_id::text AS departement_id"
            ),
            {"c": code, "l": libelle, "t": transverse, "d": departement_id},
        )
    ).mappings().one()
    await audit.consigner(
        session,
        action="MODIFICATION",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module="administration",
        cible_type="profil",
        cible_id=code,
        ancienne=avant,
        nouvelle={
            "code": code,
            "libelle": libelle,
            "transverse": transverse,
            "departement_id": departement_id,
        },
    )
    await session.commit()
    return dict(ligne)


@routeur.delete("/profils/{code}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer_profil(code: str, courant: Courant, session: Session) -> None:
    avant = await _profil_ou_404(session, code)
    if code == PROFIL_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Le profil administrateur ne peut pas être supprimé.",
        )
    rattaches = await session.scalar(
        text(
            "SELECT count(*) FROM core.utilisateur u JOIN core.profil p ON p.id = u.profil_id "
            "WHERE p.code = :c"
        ),
        {"c": code},
    )
    if rattaches:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"{rattaches} compte(s) portent ce profil — réaffectez-les avant de le supprimer."
            ),
        )
    # core.acces_role référence profil_code avec ON DELETE CASCADE : aucun accès orphelin ne reste.
    await session.execute(text("DELETE FROM core.profil WHERE code = :c"), {"c": code})
    await audit.consigner(
        session,
        action="SUPPRESSION",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module="administration",
        cible_type="profil",
        cible_id=code,
        ancienne=avant,
    )
    await session.commit()


# --- Départements (paramétrage) ---
#
# Subdivision d'une direction : « Production et Applicatif », « Réseau et Infrastructure ». Le
# département ORGANISE — il range les dossiers et alimente les analyses. Il ne cloisonne RIEN :
# le périmètre d'accès reste la direction (`autorisations.visible`). Confondre les deux
# transformerait un besoin de lisibilité en restriction d'accès que personne n'a demandée.
#
# Il est porté par le PROFIL : le département d'un agent se déduit de son profil, une seule vérité.


async def _departement_ou_404(session: AsyncSession, identifiant: str) -> dict[str, Any]:
    ligne = (
        await session.execute(
            text(
                "SELECT dep.id::text AS id, dep.code, dep.libelle, dir.code AS direction "
                "FROM core.departement dep JOIN core.direction dir ON dir.id = dep.direction_id "
                "WHERE dep.id::text = :i"
            ),
            {"i": identifiant},
        )
    ).mappings().first()
    if ligne is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Département introuvable."
        )
    return dict(ligne)


async def _exiger_departement_unique(
    session: AsyncSession, *, code: str, libelle: str, sauf: str | None = None
) -> None:
    """Refuse un code ou un libellé déjà pris — casse et espaces ignorés, comme en base."""
    conflit = await session.scalar(
        text(
            "SELECT id FROM core.departement "
            "WHERE (code = :code OR upper(btrim(libelle)) = upper(btrim(:libelle))) "
            "AND (cast(:sauf as text) IS NULL OR id::text <> :sauf) LIMIT 1"
        ),
        {"code": code, "libelle": libelle, "sauf": sauf},
    )
    if conflit is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Ce département existe déjà."
        )


@routeur.get("/departements", response_model=list[DepartementItem])
async def departements(courant: Courant, session: Session) -> list[dict[str, Any]]:
    r = await session.execute(
        text(
            "SELECT dep.id::text AS id, dep.code, dep.libelle, dir.code AS direction, "
            "       (SELECT count(*) FROM core.profil p WHERE p.departement_id = dep.id) "
            "         AS nb_profils "
            "FROM core.departement dep JOIN core.direction dir ON dir.id = dep.direction_id "
            "ORDER BY dep.libelle"
        )
    )
    return [dict(x) for x in r.mappings().all()]


@routeur.post(
    "/departements", response_model=DepartementItem, status_code=status.HTTP_201_CREATED
)
async def creer_departement(
    corps: CreationDepartement, courant: Courant, session: Session
) -> dict[str, Any]:
    libelle = corps.libelle.strip()
    code = _code_technique(libelle, "departement")
    await _exiger_departement_unique(session, code=code, libelle=libelle)
    # Sans direction précisée, on prend la seule qui existe. Le jour où il y en aura plusieurs,
    # l'appelant devra choisir — et le refus ci-dessous le dira au lieu d'en désigner une au hasard.
    directions_connues = list(
        (
            await session.execute(text("SELECT id::text, code FROM core.direction ORDER BY code"))
        ).all()
    )
    if corps.direction_code is not None:
        choisie = next((d for d in directions_connues if d[1] == corps.direction_code), None)
    elif len(directions_connues) == 1:
        choisie = directions_connues[0]
    else:
        choisie = None
    if choisie is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Direction inconnue : précisez à quelle direction rattacher ce département.",
        )
    identifiant = await session.scalar(
        text(
            "INSERT INTO core.departement (code, libelle, direction_id) "
            "VALUES (:c, :l, cast(:d as uuid)) RETURNING id::text"
        ),
        {"c": code, "l": libelle, "d": choisie[0]},
    )
    await audit.consigner(
        session,
        action="CREATION",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module="administration",
        cible_type="departement",
        cible_id=libelle,
        nouvelle={"code": code, "libelle": libelle, "direction": choisie[1]},
    )
    await session.commit()
    return {**await _departement_ou_404(session, str(identifiant)), "nb_profils": 0}


@routeur.patch("/departements/{identifiant}", response_model=DepartementItem)
async def modifier_departement(
    identifiant: str, corps: MajDepartement, courant: Courant, session: Session
) -> dict[str, Any]:
    avant = await _departement_ou_404(session, identifiant)
    libelle = corps.libelle.strip()
    # Le code technique ne bouge pas avec le libellé : il est ce à quoi les profils sont rattachés.
    await _exiger_departement_unique(
        session, code=avant["code"], libelle=libelle, sauf=identifiant
    )
    await session.execute(
        text("UPDATE core.departement SET libelle = :l WHERE id::text = :i"),
        {"i": identifiant, "l": libelle},
    )
    await audit.consigner(
        session,
        action="MODIFICATION",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module="administration",
        cible_type="departement",
        cible_id=libelle,
        ancienne=avant,
        nouvelle={**avant, "libelle": libelle},
    )
    await session.commit()
    nb = await session.scalar(
        text("SELECT count(*) FROM core.profil WHERE departement_id::text = :i"),
        {"i": identifiant},
    )
    return {**await _departement_ou_404(session, identifiant), "nb_profils": int(nb or 0)}


@routeur.delete("/departements/{identifiant}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer_departement(
    identifiant: str, courant: Courant, session: Session
) -> None:
    avant = await _departement_ou_404(session, identifiant)
    rattaches = await session.scalar(
        text("SELECT count(*) FROM core.profil WHERE departement_id::text = :i"),
        {"i": identifiant},
    )
    if rattaches:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"{rattaches} profil(s) appartiennent à ce département — "
                "rattachez-les ailleurs avant de le supprimer."
            ),
        )
    dossiers = await session.scalar(
        text("SELECT count(*) FROM core.activite WHERE departement_id::text = :i"),
        {"i": identifiant},
    )
    if dossiers:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"{dossiers} dossier(s) sont rangés dans ce département — "
                "déplacez-les avant de le supprimer."
            ),
        )
    await session.execute(
        text("DELETE FROM core.departement WHERE id::text = :i"), {"i": identifiant}
    )
    await audit.consigner(
        session,
        action="SUPPRESSION",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module="administration",
        cible_type="departement",
        cible_id=avant["libelle"],
        ancienne=avant,
    )
    await session.commit()


@routeur.get("/directions", response_model=list[DirectionItem])
async def directions(courant: Courant, session: Session) -> list[dict[str, Any]]:
    r = await session.execute(text("SELECT code, libelle FROM core.direction ORDER BY libelle"))
    return [dict(x) for x in r.mappings().all()]


# --- Catégories (paramétrage) ---

# Modules dont les catégories sont un vocabulaire fixe (non éditable). Le « type » de changement
# (Standard/Normal/Urgent) pilote le circuit CAB/ECAB et le calcul de priorité : il ne s'ajoute ni
# ne se supprime.
_MODULES_CATEGORIE_VERROUILLES: frozenset[str] = frozenset({"changement"})


def _code_technique(libelle: str, quoi: str) -> str:
    """Code stable dérivé du libellé (MAJUSCULES, alphanumérique, séparé par '_').

    Les accents sont dépliés d'abord : « Réseau télécom » donne RESEAU_TELECOM, et non
    R_SEAU_T_L_COM.
    """
    code = code_technique(libelle)
    if code is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Libellé de {quoi} invalide.",
        )
    return code


def _code_categorie(libelle: str) -> str:
    return _code_technique(libelle, "catégorie")


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
    "u.id::text AS id, u.email, u.nom, u.prenom, u.matricule, "
    "p.code AS profil, p.libelle AS profil_libelle, "
    "d.code AS direction, u.niveau_support, u.actif, u.expire_le, u.doit_changer_mdp"
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


def _exiger_niveau_support(profil_code: str, niveau: int | None) -> None:
    """Un agent qui traite des tickets doit déclarer son niveau (ADR-0005).

    Le niveau d'un ticket importé se lit sur le compte de son gestionnaire. Sans niveau, le ticket
    retomberait au N1 par défaut et la statistique mentirait en silence.

    L'administrateur distribue le travail, il ne traite pas les tickets : il n'a pas de niveau.
    """
    if profil_code != PROFIL_ADMIN and niveau is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Niveau de support requis : un agent traite les tickets à un niveau (N1 ou N2).",
        )


@routeur.post("/utilisateurs", response_model=CreationReponse, status_code=status.HTTP_201_CREATED)
async def creer_utilisateur(
    corps: CreationUtilisateur, courant: Courant, session: Session
) -> dict[str, str]:
    _valider_domaine_email(corps.email)
    _exiger_niveau_support(corps.profil_code, corps.niveau_support)
    if await session.scalar(
        text("SELECT 1 FROM core.utilisateur WHERE lower(email) = lower(:e)"), {"e": corps.email}
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail déjà utilisé.")
    # Aucun mot de passe n'est fixé ici : l'utilisateur définit le sien via un lien d'activation
    # expirable (cf. e-mail ci-dessous). Le compte reste inutilisable tant qu'il ne l'a pas défini.
    ident = await session.scalar(
        text(
            "INSERT INTO core.utilisateur"
            "(email, nom, prenom, matricule, profil_id, direction_id, niveau_support, source_auth, "
            " mot_de_passe_hash, doit_changer_mdp, expire_le) "
            "VALUES (:email, :nom, :prenom, nullif(btrim(:matricule), ''), "
            " (SELECT id FROM core.profil WHERE code = :profil), "
            " (SELECT id FROM core.direction WHERE code = :direction), :niveau, 'LOCAL', NULL, "
            " true, :expire_le) "
            "RETURNING id::text"
        ),
        {
            "email": corps.email,
            "nom": nom_propre(corps.nom),
            "prenom": nom_propre(corps.prenom),
            "matricule": corps.matricule,
            "profil": corps.profil_code,
            "direction": corps.direction_code,
            "niveau": corps.niveau_support,
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
    await envoyer_lien_mot_de_passe(
        session,
        utilisateur_id=str(ident),
        prenom=nom_propre(corps.prenom) or corps.prenom,
        email_destinataire=corps.email,
        minutes=get_settings().activation_validite_minutes,
        bienvenue=True,
    )
    return {"id": str(ident)}


@routeur.put("/utilisateurs/{ident}", status_code=status.HTTP_204_NO_CONTENT)
async def modifier_utilisateur(
    ident: str, corps: MajUtilisateur, courant: Courant, session: Session
) -> None:
    _exiger_niveau_support(corps.profil_code, corps.niveau_support)
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
    # Garde « dernier administrateur » : personne n'est au-dessus des autres, tous les admins sont
    # égaux — mais le système ne doit jamais tomber à zéro admin (plus personne ne pourrait alors
    # administrer). On refuse de bloquer ou de rétrograder le dernier administrateur actif.
    perd_admin = corps.profil_code != PROFIL_ADMIN or not corps.actif
    if perd_admin:
        est_admin_actif = await session.scalar(
            text(
                "SELECT u.actif FROM core.utilisateur u JOIN core.profil p ON p.id = u.profil_id "
                "WHERE u.id::text = :id AND p.code = :admin"
            ),
            {"id": ident, "admin": PROFIL_ADMIN},
        )
        if est_admin_actif:
            autres = await session.scalar(
                text(
                    "SELECT count(*) FROM core.utilisateur u "
                    "JOIN core.profil p ON p.id = u.profil_id "
                    "WHERE p.code = :admin AND u.actif AND u.id::text <> :id"
                ),
                {"id": ident, "admin": PROFIL_ADMIN},
            )
            if not autres:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Dernier administrateur actif : désignez d'abord un autre administrateur "
                        "avant de bloquer ou de rétrograder celui-ci."
                    ),
                )
    await session.execute(
        text(
            "UPDATE core.utilisateur SET nom = :nom, prenom = :prenom, actif = :actif, "
            "matricule = nullif(btrim(:matricule), ''), "
            "expire_le = :expire_le, niveau_support = :niveau, "
            "profil_id = (SELECT id FROM core.profil WHERE code = :profil), "
            "direction_id = (SELECT id FROM core.direction WHERE code = :direction) "
            "WHERE id::text = :id"
        ),
        {
            "id": ident,
            "nom": nom_propre(corps.nom),
            "prenom": nom_propre(corps.prenom),
            "matricule": corps.matricule,
            "actif": corps.actif,
            "expire_le": corps.expire_le,
            "niveau": corps.niveau_support,
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
        cible_id=avant["email"],
    )
    # Notifie l'utilisateur si son accès vient d'être bloqué.
    if avant["actif"] and not corps.actif:
        sujet, texte, html = email_modeles.compte_bloque(avant["prenom"])
        email.envoyer(avant["email"], sujet, texte, html)


@routeur.post("/utilisateurs/{ident}/reinitialiser-mdp")
async def reinitialiser_mdp(ident: str, courant: Courant, session: Session) -> dict[str, str]:
    """Renvoie à l'utilisateur un lien expirable pour (re)définir son mot de passe lui-même.

    Aucun mot de passe n'est affiché à l'écran : le lien part par e-mail (activation si le compte
    n'a pas encore de mot de passe, réinitialisation sinon).
    """
    u = await repo_u.par_id(session, ident)
    if u is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable."
        )
    activation = u["mot_de_passe_hash"] is None
    await audit.consigner(
        session,
        action="REINITIALISATION_MDP",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module="administration",
        cible_type="utilisateur",
        cible_id=u["email"],
    )
    minutes = (
        get_settings().activation_validite_minutes
        if activation
        else get_settings().reset_validite_minutes
    )
    await envoyer_lien_mot_de_passe(
        session,
        utilisateur_id=ident,
        prenom=u["prenom"],
        email_destinataire=u["email"],
        minutes=minutes,
        bienvenue=activation,
    )
    return {"email": u["email"]}


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


# Libellé lisible du type d'objet visé, pour la colonne « Cible » du journal. La cible brute (une
# référence, un e-mail, un code) devient « Incident · INC-2026-0001 » : le lecteur voit de quoi il
# s'agit sans connaître les codes internes.
_LIBELLE_CIBLE = {
    "incident": "Incident",
    "demande": "Demande",
    "projet": "Projet",
    "changement": "Changement",
    "audit": "Audit",
    "risque": "Risque",
    "tache": "Tâche",
    "note": "Note",
    "activite": "Activité",
    "profil": "Profil",
    "departement": "Département",
    "gouvernance": "Gouvernance",
    "utilisateur": "Utilisateur",
    "categorie": "Catégorie",
    "acces_role": "Accès",
    "sla_regle": "Règle SLA",
    "rapport_tickets": "Import",
}


def _cible_lisible(cible_type: str | None, cible_id: str | None) -> str | None:
    """« Incident · INC-2026-0001 » à partir du type et de l'identifiant journalisés."""
    libelle = _LIBELLE_CIBLE.get(cible_type or "", cible_type or "")
    if cible_id and libelle:
        return f"{libelle} · {cible_id}"
    return cible_id or libelle or None


# Libellés lisibles des actions journalisées (mêmes intitulés que l'écran) ; repli sur le code brut.
_LIBELLE_ACTION = {
    "CREATION": "Création",
    "MODIFICATION": "Modification",
    "SUPPRESSION": "Suppression",
    "TRANSITION": "Changement d'état",
    "ASSIGNATION": "Assignation",
    "EVALUATION": "Évaluation",
    "APPROBATION": "Approbation",
    "REJET": "Rejet",
    "ESCALADE": "Escalade",
    "REVUE_EFFECTUEE": "Revue effectuée",
    "IMPORT": "Import",
    "REINITIALISATION_MDP": "Réinitialisation mot de passe",
    "ACTIVATION": "Activation",
    "DESACTIVATION": "Désactivation",
    "CONNEXION": "Connexion",
    "INCARNATION": "Incarnation",
}


@routeur.get("/journal/export")
async def exporter_journal(
    courant: Courant,
    session: Session,
    format: Annotated[str, Query(alias="format")] = "xlsx",
    q: Annotated[str | None, Query(max_length=120)] = None,
    module: Annotated[str | None, Query(max_length=40)] = None,
    action: Annotated[str | None, Query(max_length=40)] = None,
) -> Response:
    """Export du journal d'audit (Excel ou CSV) — colonnes lisibles, comme à l'écran.

    L'export suit les mêmes filtres que la liste : un fichier qui dirait autre chose que
    l'écran dont il sort serait un piège, surtout quand il part en pièce jointe à un auditeur.
    """
    entetes = ["Date et heure", "Acteur", "Module", "Action", "Cible"]
    params: dict[str, Any] = {}
    conditions = _filtres_journal(q, module, action, params)
    lignes = await session.execute(
        text(
            "SELECT horodatage, acteur_email AS acteur, module, action, "
            f"cible_type, cible_id FROM audit.journal WHERE 1 = 1{conditions} "
            "ORDER BY id DESC LIMIT 50000"
        ),
        params,
    )
    donnees = [
        [
            e["horodatage"].strftime("%Y-%m-%d %H:%M:%S") if e["horodatage"] else "",
            e["acteur"] or "",
            e["module"] or "",
            _LIBELLE_ACTION.get(e["action"], e["action"] or ""),
            _cible_lisible(e["cible_type"], e["cible_id"]) or "",
        ]
        for e in lignes.mappings().all()
    ]
    if format == "csv":
        return Response(
            content=vers_csv(entetes, donnees),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=journal-audit.csv"},
        )
    return Response(
        content=vers_xlsx(entetes, donnees, "Journal d'audit"),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=journal-audit.xlsx"},
    )


def _filtres_journal(
    q: str | None, module: str | None, action: str | None, params: dict[str, Any]
) -> str:
    """Conditions du journal. Un journal qu'on ne peut pas interroger ne prouve rien : à
    30 000 lignes, retrouver « qui a touché à INC-2026-0001 » doit tenir en une recherche."""
    conditions = ""
    if q is not None and q.strip() != "":
        conditions += (
            " AND (acteur_email ILIKE :q OR cible_id ILIKE :q OR module ILIKE :q"
            " OR action ILIKE :q)"
        )
        params["q"] = f"%{q.strip()}%"
    if module:
        conditions += " AND module = :module"
        params["module"] = module
    if action:
        conditions += " AND action = :action"
        params["action"] = action
    return conditions


@routeur.get("/journal/referentiels")
async def referentiels_journal(courant: Courant, session: Session) -> dict[str, list[str]]:
    """Modules et actions réellement présents au journal : les filtres ne proposent que
    ce qui existe, plutôt qu'une liste théorique où l'on chercherait en vain."""
    lignes = await session.execute(
        text(
            "SELECT DISTINCT module, action FROM audit.journal "
            "WHERE module IS NOT NULL OR action IS NOT NULL"
        )
    )
    modules, actions = set(), set()
    for e in lignes.mappings().all():
        if e["module"]:
            modules.add(e["module"])
        if e["action"]:
            actions.add(e["action"])
    return {"modules": sorted(modules), "actions": sorted(actions)}


@routeur.get("/journal", response_model=PageJournal)
async def lister_journal(
    courant: Courant,
    session: Session,
    page: Annotated[int, Query(ge=1)] = 1,
    q: Annotated[str | None, Query(max_length=120)] = None,
    module: Annotated[str | None, Query(max_length=40)] = None,
    action: Annotated[str | None, Query(max_length=40)] = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    conditions = _filtres_journal(q, module, action, params)
    total = (
        await session.scalar(
            text(f"SELECT count(*) FROM audit.journal WHERE 1 = 1{conditions}"), params
        )
        or 0
    )
    lignes = await session.execute(
        text(
            "SELECT horodatage, acteur_email AS acteur, module, action, "
            f"cible_type, cible_id FROM audit.journal WHERE 1 = 1{conditions} "
            "ORDER BY id DESC LIMIT :l OFFSET :o"
        ),
        {**params, "l": _TAILLE, "o": (page - 1) * _TAILLE},
    )
    return {
        "elements": [
            {
                "horodatage": e["horodatage"],
                "acteur": e["acteur"],
                "module": e["module"],
                "action": e["action"],
                "cible": _cible_lisible(e["cible_type"], e["cible_id"]),
            }
            for e in lignes.mappings().all()
        ],
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
