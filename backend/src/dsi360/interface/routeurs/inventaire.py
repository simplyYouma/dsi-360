"""Module Inventaire : le parc matériel de la DSI (immobilisations IT).

Un équipement n'est pas une activité : ni workflow, ni SLA, ni valideur. Ce routeur est donc
autonome, sans passer par la fabrique `activites_communs`.

L'amortissement n'est jamais stocké : il se calcule à la lecture (`domain/amortissement`), sinon
la valeur nette comptable serait fausse dès le lendemain de son enregistrement.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.inventaire import (
    creer_equipement,
    maj_equipement,
    supprimer_equipement,
)
from dsi360.domain import amortissement
from dsi360.infrastructure.db import session_scope
from dsi360.infrastructure.export import vers_csv, vers_xlsx
from dsi360.infrastructure.repositories import equipement as repo
from dsi360.interface.schemas import (
    EquipementCreation,
    EquipementDetail,
    EquipementMaj,
    PageEquipements,
    ReferentielCreation,
    ReferentielItem,
    StatsInventaire,
)
from dsi360.interface.securite import exiger_acces, exiger_admin

_ACCES = "inventaire"
_TAILLE = 15

routeur = APIRouter(prefix="/inventaire", tags=["inventaire"])
Session = Annotated[AsyncSession, Depends(session_scope)]
Courant = Annotated[dict[str, Any], Depends(exiger_acces(_ACCES))]


def _nombre(valeur: Any) -> float | None:
    """Les numeric PostgreSQL reviennent en Decimal : le JSON veut des flottants."""
    return None if valeur is None else float(valeur)


def _detenteur(r: RowMapping) -> str | None:
    """Nom du détenteur si le matricule a été rapproché d'un compte ; sinon rien.

    On n'affiche jamais le matricule brut à la place d'un nom : il est exposé à part
    (`matricule`), pour qu'on voie qu'un rattachement reste à faire.
    """
    if r["det_prenom"] is None:
        return None
    return f"{r['det_prenom']} {r['det_nom']}"


def _amortissement(r: RowMapping) -> amortissement.Amortissement:
    return amortissement.calculer(
        _nombre(r["valeur_acquisition"]),
        r["date_acquisition"],
        _nombre(r["taux"]),
        r["duree_annees"],
    )


def _resume(r: RowMapping) -> dict[str, Any]:
    a = _amortissement(r)
    return {
        "id": r["id"],
        "code_immo": r["code_immo"],
        "numero_serie": r["numero_serie"],
        "modele": r["modele"],
        "designation": r["designation"],
        "emplacement": r["emplacement"],
        "departement": r["departement"],
        "detenteur": _detenteur(r),
        # Le matricule du compte prime ; à défaut, celui que porte le fichier.
        "matricule": r["det_matricule"] or r["matricule_brut"],
        "date_acquisition": r["date_acquisition"],
        "valeur_acquisition": _nombre(r["valeur_acquisition"]),
        "valeur_nette": a.valeur_nette,
        "amorti_pct": a.pourcentage,
        "actif": r["actif"],
    }


def _detail(r: RowMapping) -> dict[str, Any]:
    a = _amortissement(r)
    return {
        **_resume(r),
        "emplacement_id": r["emplacement_id"],
        "departement_id": r["departement_id"],
        "detenteur_id": r["detenteur_id"],
        "taux": _nombre(r["taux"]),
        "duree_annees": r["duree_annees"],
        "source": r["source"],
        "dotation_annuelle": a.dotation_annuelle,
        "amortissement_cumule": a.cumul,
        "fin_amortissement": a.fin,
        "totalement_amorti": a.totalement_amorti,
        "amortissement_incoherent": a.incoherent,
    }


async def _charger(session: AsyncSession, ident: str) -> RowMapping:
    r = await repo.par_id(session, ident)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Équipement introuvable.")
    return r


@routeur.get("", response_model=PageEquipements)
async def lister(
    courant: Courant,
    session: Session,
    page: Annotated[int, Query(ge=1)] = 1,
    q: Annotated[str | None, Query(max_length=80)] = None,
    emplacement_id: Annotated[str | None, Query()] = None,
    departement_id: Annotated[str | None, Query()] = None,
    detenteur_id: Annotated[str | None, Query()] = None,
    actif: Annotated[bool | None, Query()] = True,
) -> dict[str, Any]:
    lignes, total = await repo.lister(
        session,
        page=page,
        taille=_TAILLE,
        q=q,
        emplacement_id=emplacement_id,
        departement_id=departement_id,
        detenteur_id=detenteur_id,
        actif=actif,
    )
    return {
        "elements": [_resume(r) for r in lignes],
        "total": total,
        "page": page,
        "taille": _TAILLE,
    }


@routeur.get("/stats", response_model=StatsInventaire)
async def stats(courant: Courant, session: Session) -> dict[str, int | float]:
    """Compteurs de l'en-tête : effectif, sorties du parc, matériels sans détenteur, valeur."""
    return await repo.compter(session)


_ENTETES_EXPORT = [
    "Code immo",
    "Désignation",
    "N° série",
    "Modèle",
    "Emplacement",
    "Département",
    "Détenteur",
    "Matricule",
    "Date acquisition",
    "Valeur acquisition",
    "Valeur nette",
    "Amorti (%)",
    "En service",
]


@routeur.get("/export")
async def exporter(
    courant: Courant,
    session: Session,
    format: Annotated[str, Query(alias="format")] = "csv",
) -> Response:
    lignes = await repo.lister_tout(session)
    donnees = []
    for r in lignes:
        v = _resume(r)
        donnees.append(
            [
                v["code_immo"] or "",
                v["designation"],
                v["numero_serie"] or "",
                v["modele"] or "",
                v["emplacement"] or "",
                v["departement"] or "",
                v["detenteur"] or "",
                v["matricule"] or "",
                v["date_acquisition"].strftime("%d/%m/%Y") if v["date_acquisition"] else "",
                v["valeur_acquisition"] if v["valeur_acquisition"] is not None else "",
                v["valeur_nette"] if v["valeur_nette"] is not None else "",
                v["amorti_pct"] if v["amorti_pct"] is not None else "",
                "Oui" if v["actif"] else "Non",
            ]
        )
    if format == "xlsx":
        contenu = vers_xlsx(_ENTETES_EXPORT, donnees, "Inventaire")
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = "xlsx"
    else:
        contenu = vers_csv(_ENTETES_EXPORT, donnees)
        media = "text/csv"
        ext = "csv"
    return Response(
        content=contenu,
        media_type=media,
        headers={"Content-Disposition": f"attachment; filename=inventaire.{ext}"},
    )


@routeur.get("/{ident}", response_model=EquipementDetail)
async def detail(ident: str, courant: Courant, session: Session) -> dict[str, Any]:
    return _detail(await _charger(session, ident))


@routeur.post("", response_model=EquipementDetail, status_code=status.HTTP_201_CREATED)
async def creer(corps: EquipementCreation, courant: Courant, session: Session) -> dict[str, Any]:
    await _refuser_code_deja_pris(session, corps.code_immo, None)
    ident = await creer_equipement(session, corps.model_dump(exclude_none=True), courant)
    await session.commit()
    return _detail(await _charger(session, ident))


@routeur.patch("/{ident}", response_model=EquipementDetail)
async def modifier(
    ident: str, corps: EquipementMaj, courant: Courant, session: Session
) -> dict[str, Any]:
    avant = await _charger(session, ident)
    champs = corps.model_dump(exclude_unset=True)
    if "code_immo" in champs:
        await _refuser_code_deja_pris(session, champs["code_immo"], ident)
    await maj_equipement(session, dict(avant), champs, courant)
    await session.commit()
    return _detail(await _charger(session, ident))


@routeur.delete("/{ident}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer(ident: str, courant: Courant, session: Session) -> None:
    """Suppression définitive, réservée à l'administrateur.

    Pour sortir un matériel du parc sans perdre son historique, on le passe plutôt à
    « hors service » (`actif = false`).
    """
    exiger_admin(courant)
    avant = await _charger(session, ident)
    await supprimer_equipement(session, dict(avant), courant)
    await session.commit()


async def _refuser_code_deja_pris(
    session: AsyncSession, code: str | None, ident_courant: str | None
) -> None:
    """Le code d'immobilisation identifie l'équipement en comptabilité : jamais deux fois."""
    if code is None or code.strip() == "":
        return
    existant = await repo.par_code_immo(session, code)
    if existant is not None and existant["id"] != ident_courant:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Le code d'immobilisation « {code.strip()} » est déjà utilisé.",
        )


# --- Référentiels de localisation ------------------------------------------------------------


@routeur.get("/referentiels/{cle}", response_model=list[ReferentielItem])
async def referentiel(cle: str, courant: Courant, session: Session) -> list[dict[str, Any]]:
    if cle not in repo.TABLES_REFERENTIEL:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Référentiel inconnu.")
    return [dict(r) for r in await repo.lister_referentiel(session, cle)]


@routeur.post(
    "/referentiels/{cle}", response_model=ReferentielItem, status_code=status.HTTP_201_CREATED
)
async def ajouter_referentiel(
    cle: str, corps: ReferentielCreation, courant: Courant, session: Session
) -> dict[str, Any]:
    exiger_admin(courant)
    if cle not in repo.TABLES_REFERENTIEL:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Référentiel inconnu.")
    ident = await repo.trouver_ou_creer_referentiel(session, cle, corps.libelle)
    await session.commit()
    return {"id": ident, "libelle": corps.libelle.strip(), "actif": True}
