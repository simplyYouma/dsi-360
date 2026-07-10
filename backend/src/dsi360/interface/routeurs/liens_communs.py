"""Liens utiles (espace documentaire, wiki, dossier réseau…) — registrar partagé.

Rattachés à l'**activité**, jamais à une tâche : un lien sert le sujet, pas une étape de sa
réalisation. Éparpillés sur les tâches, ils devenaient introuvables une fois la tâche terminée.
Réutilisé par les projets et la fabrique d'activités (changements).
"""

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.infrastructure import audit
from dsi360.interface.schemas import LienCreation, LienItem


def enregistrer_liens(
    routeur: APIRouter,
    *,
    module: str,
    charger: Callable[[AsyncSession, str, dict[str, Any]], Awaitable[RowMapping]],
    Courant: Any,  # noqa: N803 - annotation FastAPI (Depends), même nom que la variable locale
    Session: Any,  # noqa: N803
    CourantEcriture: Any,  # noqa: N803
) -> None:
    """Ajoute les endpoints de liens utiles d'une activité à son routeur.

    ``charger(session, ident, courant)`` doit renvoyer l'activité (avec ``reference``) ou lever 404.

    ``CourantEcriture`` garde les routes qui modifient : lire reste ouvert à qui voit l'activité,
    écrire est réservé aux acteurs de travail.
    """

    @routeur.get("/{ident}/liens", response_model=list[LienItem])
    async def lister_liens(
        ident: str,
        courant: Courant,
        session: Session,
    ) -> list[dict[str, Any]]:
        await charger(session, ident, courant)
        lignes = (
            await session.execute(
                text(
                    "SELECT id::text AS id, libelle, url, cree_le FROM core.lien "
                    "WHERE activite_id = cast(:id as uuid) ORDER BY cree_le"
                ),
                {"id": ident},
            )
        ).mappings().all()
        return [dict(x) for x in lignes]

    @routeur.post("/{ident}/liens", response_model=LienItem, status_code=status.HTTP_201_CREATED)
    async def creer_lien(
        ident: str,
        corps: LienCreation,
        courant: CourantEcriture,
        session: Session,
    ) -> dict[str, Any]:
        activite = await charger(session, ident, courant)
        ligne = (
            await session.execute(
                text(
                    "INSERT INTO core.lien (activite_id, libelle, url, cree_par) "
                    "VALUES (cast(:aid as uuid), :libelle, :url, :email) "
                    "RETURNING id::text AS id, libelle, url, cree_le"
                ),
                {
                    "aid": ident,
                    "libelle": corps.libelle.strip(),
                    "url": corps.url.strip(),
                    "email": courant["email"],
                },
            )
        ).mappings().one()
        await audit.consigner(
            session,
            action="CREATION",
            acteur_id=courant["id"],
            acteur_email=courant["email"],
            module=module,
            cible_type="lien",
            cible_id=activite["reference"],
            nouvelle={"libelle": corps.libelle.strip(), "url": corps.url.strip()},
        )
        await session.commit()
        return dict(ligne)

    @routeur.delete("/{ident}/liens/{lien_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def supprimer_lien(
        ident: str,
        lien_id: str,
        courant: CourantEcriture,
        session: Session,
    ) -> None:
        activite = await charger(session, ident, courant)
        ligne = (
            await session.execute(
                text(
                    "DELETE FROM core.lien WHERE id = cast(:id as uuid) "
                    "AND activite_id = cast(:aid as uuid) RETURNING libelle, url"
                ),
                {"id": lien_id, "aid": ident},
            )
        ).mappings().first()
        if ligne is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lien introuvable.")
        await audit.consigner(
            session,
            action="SUPPRESSION",
            acteur_id=courant["id"],
            acteur_email=courant["email"],
            module=module,
            cible_type="lien",
            cible_id=activite["reference"],
            ancienne={"libelle": ligne["libelle"], "url": ligne["url"]},
        )
        await session.commit()
