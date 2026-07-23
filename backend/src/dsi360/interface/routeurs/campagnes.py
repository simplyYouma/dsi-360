"""Inventaires physiques : recenser le parc et consigner l'état de chaque matériel.

Routeur distinct du référentiel du parc pour une raison de routage : `/inventaire/{ident}`
attraperait `/inventaire/campagnes` — il doit donc être enregistré **avant** lui dans l'app.

Sans cérémonie : un inventaire se crée, on y pose ses constats, et il cohabite avec les
précédents. Ni ouverture à déclarer, ni clôture — le cahier demandait de relever l'état du
parc, pas d'administrer un cycle de vie.

Partage des rôles : l'administrateur crée l'inventaire ; **tout agent du module recense** — le
recensement est un travail de terrain, pas un privilège. Le serveur fait foi (ADR-0003).
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.infrastructure import audit
from dsi360.infrastructure.db import session_scope
from dsi360.infrastructure.repositories import campagne as repo
from dsi360.infrastructure.repositories import equipement as repo_equipement
from dsi360.interface.schemas import (
    CampagneCreation,
    CampagneInventaire,
    ConstatCreation,
    LigneRecensement,
    PageCampagnes,
)
from dsi360.interface.securite import exiger_acces, exiger_admin

_ACCES = "inventaire"

routeur = APIRouter(prefix="/inventaire/campagnes", tags=["inventaire"])
Session = Annotated[AsyncSession, Depends(session_scope)]
Courant = Annotated[dict[str, Any], Depends(exiger_acces(_ACCES))]


def _campagne(r: RowMapping) -> dict[str, Any]:
    return {
        "id": r["id"],
        "libelle": r["libelle"],
        "statut": r["statut"],
        "ouverte_le": r["ouverte_le"],
        "cloturee_le": r["cloturee_le"],
        "ouverte_par": r["ouverte_par"],
        "constates": int(r["constates"]),
        "bons": int(r["bons"]),
        "rebuts": int(r["rebuts"]),
        "casses": int(r["casses"]),
        "non_retrouves": int(r["non_retrouves"]),
    }


async def _charger(session: AsyncSession, ident: str) -> RowMapping:
    r = await repo.par_id(session, ident)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campagne introuvable.")
    return r


@routeur.get("", response_model=PageCampagnes)
async def lister(courant: Courant, session: Session) -> dict[str, Any]:
    """Tous les inventaires avec leurs comptes — la comparaison d'une année à l'autre se lit ici."""
    return {
        "campagnes": [_campagne(r) for r in await repo.lister(session)],
        # L'avancement se mesure contre le parc actif du moment.
        "parc_actif": await repo.parc_actif(session),
    }


@routeur.post("", response_model=CampagneInventaire, status_code=status.HTTP_201_CREATED)
async def ouvrir(corps: CampagneCreation, courant: Courant, session: Session) -> dict[str, Any]:
    """Créer un inventaire. Rien d'autre : ni ouverture à déclarer, ni précédent à clore."""
    exiger_admin(courant)
    ident = await repo.creer(session, corps.libelle, courant["id"])
    await audit.consigner(
        session,
        action="CREATION",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module="inventaire",
        cible_type="campagne",
        cible_id=corps.libelle.strip(),
        nouvelle={"libelle": corps.libelle.strip()},
    )
    await session.commit()
    return _campagne(await _charger(session, ident))


@routeur.get("/{ident}/recensement", response_model=list[LigneRecensement])
async def recensement(ident: str, courant: Courant, session: Session) -> list[dict[str, Any]]:
    """Le parc, équipement par équipement, avec son constat — les non recensés d'abord."""
    await _charger(session, ident)
    return await repo.recensement(session, ident)


@routeur.put("/{ident}/constats/{equipement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def constater(
    ident: str,
    equipement_id: str,
    corps: ConstatCreation,
    courant: Courant,
    session: Session,
) -> None:
    """Poser (ou remplacer) le constat d'un équipement. Ouvert à tout agent du module."""
    campagne = await _charger(session, ident)
    equipement = await repo_equipement.par_id(session, equipement_id)
    if equipement is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Équipement introuvable.")
    await repo.poser_constat(
        session, ident, equipement_id, corps.etat, courant["id"], corps.justification
    )
    # Le constat rejoint l'historique de l'équipement : qui l'a vu, quand, dans quel état — et
    # sur quoi il s'est fondé. C'est ce motif qui rendra la campagne relisible dans un an.
    await audit.consigner(
        session,
        action="CONSTAT",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module="inventaire",
        cible_type="equipement",
        cible_id=equipement["code_immo"] or equipement["designation"],
        nouvelle={
            "etat": corps.etat,
            "campagne": campagne["libelle"],
            "motif": corps.justification.strip(),
        },
    )
    await session.commit()


@routeur.delete("/{ident}/constats/{equipement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def retirer(
    ident: str, equipement_id: str, courant: Courant, session: Session
) -> None:
    """Annuler un constat posé par erreur : l'équipement redevient « à recenser »."""
    await _charger(session, ident)
    await repo.retirer_constat(session, ident, equipement_id)
    await session.commit()
