"""Fabrique de routeur d'activités, partagée par les modules (incidents, demandes, projets…).

Évite la duplication : liste paginée cloisonnée, création (priorité + SLA + audit), détail et
transition (machine à états) sont identiques d'un module à l'autre — seules changent la clé
d'accès RBAC, le module domaine et l'URL.
"""

import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.activites import (
    ActiviteIntrouvable,
    TransitionInterdite,
    creer_activite,
    transition,
)
from dsi360.application.notifications import notifier
from dsi360.application.taches import creer_tache, maj_tache, supprimer_tache
from dsi360.domain.etats import ordre_etats, transitions_possibles
from dsi360.domain.sla import statut_sla
from dsi360.domain.texte import phrase_propre
from dsi360.infrastructure import audit
from dsi360.infrastructure.db import session_scope
from dsi360.infrastructure.export import vers_csv, vers_xlsx
from dsi360.infrastructure.repositories import activite as repo
from dsi360.infrastructure.repositories import tache as tache_repo
from dsi360.interface.routeurs.documents_communs import enregistrer_documents
from dsi360.interface.schemas import (
    ActiviteCreation,
    ActiviteDetail,
    ActiviteMaj,
    AssignationDemande,
    AssignationLot,
    CategorieDemande,
    ContributeurDemande,
    CreationReponse,
    DecisionDemande,
    PageActivites,
    ResultatAssignationLot,
    RevueDemande,
    Tache,
    TacheCreation,
    TacheMaj,
    TransitionDemande,
)
from dsi360.interface.securite import exiger_acces

_TAILLE = 15
_FENETRE_APPROCHE = timedelta(hours=2)


def _statut_sla(resolution_le: datetime | None, maintenant: datetime) -> str:
    if resolution_le is None:
        return "a_lheure"
    return statut_sla(resolution_le, maintenant, _FENETRE_APPROCHE)


def _responsable(r: RowMapping) -> dict[str, str] | None:
    if r["resp_email"] is None:
        return None
    return {"prenom": r["resp_prenom"], "nom": r["resp_nom"], "email": r["resp_email"]}


def _donnees(r: RowMapping) -> dict[str, Any]:
    valeur = r["donnees"]
    if isinstance(valeur, str):
        valeur = json.loads(valeur)
    return dict(valeur) if isinstance(valeur, dict) else {}


def _gestionnaire(r: RowMapping) -> str | None:
    """Gestionnaire DSI : compte rattaché si présent, sinon nom conservé à l'import."""
    if r["resp_email"] is not None:
        return f"{r['resp_prenom']} {r['resp_nom']}"
    valeur = _donnees(r).get("gestionnaire")
    return str(valeur) if valeur else None


def _resume(r: RowMapping, maintenant: datetime) -> dict[str, Any]:
    return {
        "id": r["id"],
        "reference": r["reference"],
        "titre": r["titre"],
        "statut": r["statut"],
        "priorite": r["priorite"],
        "categorie": r["categorie"],
        "direction": r["direction"],
        "sla_resolution_le": r["sla_resolution_le"],
        "statut_sla": _statut_sla(r["sla_resolution_le"], maintenant),
        "cree_le": r["cree_le"],
        "responsable": _responsable(r),
        "demandeur": r["demandeur_nom"],
        "gestionnaire": _gestionnaire(r),
        "responsable_id": r["resp_id"],
        "nb_commentaires": r["nb_commentaires"],
    }


def _detail(module: str, r: RowMapping, maintenant: datetime) -> dict[str, Any]:
    return {
        **_resume(r, maintenant),
        "description": r["description"],
        "categorie_id": str(r["categorie_id"]) if r["categorie_id"] is not None else None,
        "impact": r["impact"],
        "urgence": r["urgence"],
        "sla_prise_en_charge_le": r["sla_prise_en_charge_le"],
        "resolu_le": r["resolu_le"],
        "cloture_le": r["cloture_le"],
        "transitions_possibles": transitions_possibles(module, r["statut"]),
        "etats": ordre_etats(module),
        "avancement": int(_donnees(r).get("avancement", 0)),
        "niveau_support": int(_donnees(r).get("niveau_support", 1)),
        **{champ: _donnees(r).get(champ) for champ in _CHAMPS_RFC},
        "periodicite": _donnees(r).get("periodicite"),
        "prochaine_revue": _donnees(r).get("prochaine_revue"),
    }


# Champs RFC (changement, ITIL SI-12.04) stockés dans la colonne JSON `donnees`.
_CHAMPS_RFC = (
    "analyse_impact",
    "analyse_risque",
    "plan_deploiement",
    "plan_retour_arriere",
    "bilan_post_implementation",
)


def _visible(r: RowMapping, courant: dict[str, Any]) -> bool:
    if courant["transverse"]:
        return True
    return r["direction"] is None or r["direction"] == courant["direction"]


ENTETES_EXPORT = [
    "Référence",
    "Titre",
    "Statut",
    "Priorité",
    "Catégorie",
    "Direction",
    "Échéance SLA",
    "Créé le",
    "Responsable",
]


def _ligne_export(r: RowMapping) -> list[Any]:
    resp = f"{r['resp_prenom']} {r['resp_nom']}" if r["resp_email"] is not None else ""
    echeance = r["sla_resolution_le"].strftime("%Y-%m-%d %H:%M") if r["sla_resolution_le"] else ""
    return [
        r["reference"],
        r["titre"],
        r["statut"],
        f"P{r['priorite']}" if r["priorite"] is not None else "",
        r["categorie"] or "",
        r["direction"] or "",
        echeance,
        r["cree_le"].strftime("%Y-%m-%d %H:%M"),
        resp,
    ]


Session = Annotated[AsyncSession, Depends(session_scope)]


def creer_routeur(
    module: str,
    acces: str,
    prefixe: str,
    tag: str,
    *,
    import_uniquement: bool = False,
    avec_taches: bool = False,
    avec_documents: bool = False,
    avec_escalade: bool = False,
    avec_revue: bool = False,
    editable: bool = False,
) -> APIRouter:
    """Routeur générique d'un module d'activités.

    import_uniquement=True (incidents, demandes) : pas de création manuelle — les tickets
    proviennent exclusivement de l'import du rapport SD. On n'expose alors pas le POST de création.

    avec_taches=True (changement…) : expose la gestion des tâches (l'avancement et une partie du
    cycle de vie s'en déduisent, cf. application/taches.py).
    """
    routeur = APIRouter(prefix=prefixe, tags=[tag])
    Courant = Annotated[dict[str, Any], Depends(exiger_acces(acces))]  # noqa: N806

    async def charger_visible(
        session: AsyncSession, ident: str, courant: dict[str, Any]
    ) -> RowMapping:
        r = await repo.par_id(session, module, ident)
        if r is None or not _visible(r, courant):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Introuvable.")
        return r

    @routeur.get("", response_model=PageActivites)
    async def lister(
        courant: Courant,
        session: Session,
        page: Annotated[int, Query(ge=1)] = 1,
        statut: Annotated[str | None, Query()] = None,
        responsable_id: Annotated[str | None, Query()] = None,
        non_assigne: Annotated[bool, Query()] = False,
        q: Annotated[str | None, Query(max_length=80)] = None,
        etat: Annotated[str | None, Query()] = None,
    ) -> dict[str, Any]:
        direction = None if courant["transverse"] else courant["direction"]
        lignes, total = await repo.lister(
            session,
            module,
            direction=direction,
            statut=statut,
            page=page,
            taille=_TAILLE,
            responsable_id=responsable_id,
            non_assigne=non_assigne,
            q=q,
            etat=etat,
        )
        maintenant = datetime.now(UTC)
        return {
            "elements": [_resume(r, maintenant) for r in lignes],
            "total": total,
            "page": page,
            "taille": _TAILLE,
        }

    if not import_uniquement:

        @routeur.post("", response_model=CreationReponse, status_code=status.HTTP_201_CREATED)
        async def creer(
            corps: ActiviteCreation, courant: Courant, session: Session
        ) -> dict[str, str]:
            ident = await creer_activite(
                session,
                module,
                titre=corps.titre,
                description=corps.description,
                impact=corps.impact,
                urgence=corps.urgence,
                categorie_id=corps.categorie_id,
                direction_id=corps.direction_id,
                responsable_id=corps.responsable_id,
                acteur=courant,
                demandeur=corps.demandeur,
            )
            return {"id": ident}

    @routeur.get("/export")
    async def exporter(
        courant: Courant,
        session: Session,
        format: Annotated[str, Query(alias="format")] = "csv",
    ) -> Response:
        direction = None if courant["transverse"] else courant["direction"]
        lignes = await repo.lister_tout(session, module, direction=direction)
        donnees = [_ligne_export(r) for r in lignes]
        if format == "xlsx":
            contenu = vers_xlsx(ENTETES_EXPORT, donnees, tag)
            media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ext = "xlsx"
        else:
            contenu = vers_csv(ENTETES_EXPORT, donnees)
            media = "text/csv"
            ext = "csv"
        nom = f"{prefixe.strip('/')}-export.{ext}"
        return Response(
            content=contenu,
            media_type=media,
            headers={"Content-Disposition": f"attachment; filename={nom}"},
        )

    async def detail_complet(r: RowMapping, session: AsyncSession) -> dict[str, Any]:
        base = _detail(module, r, datetime.now(UTC))
        base["historique"] = await audit.historique_statuts(session, module, r["reference"])
        base["contributeurs"] = [
            dict(c) for c in await repo.lister_contributeurs(session, r["id"])
        ]
        base["valideurs"] = [dict(c) for c in await repo.lister_valideurs(session, r["id"])]
        return base

    # Déclaré avant /{ident} pour éviter que "assignation-lot" soit pris pour un identifiant.
    @routeur.post("/assignation-lot", response_model=ResultatAssignationLot)
    async def assigner_lot(
        corps: AssignationLot, courant: Courant, session: Session
    ) -> dict[str, int]:
        if corps.responsable_id is not None:
            existe = await session.scalar(
                text("SELECT 1 FROM core.utilisateur WHERE id::text = :id AND actif"),
                {"id": corps.responsable_id},
            )
            if existe is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Agent introuvable ou inactif."
                )
        assignes = 0
        for ident in corps.ids:
            r = await repo.par_id(session, module, ident)
            if r is None or not _visible(r, courant):
                continue  # on ignore silencieusement hors périmètre / introuvable
            await repo.assigner(session, ident, corps.responsable_id)
            assignes += 1
        if assignes > 0 and corps.responsable_id not in (None, courant["id"]):
            await session.execute(
                text(
                    "INSERT INTO core.notification "
                    "(destinataire_id, type, titre, message) "
                    "VALUES (cast(:dest as uuid), 'ASSIGNATION', :titre, :msg)"
                ),
                {
                    "dest": corps.responsable_id,
                    "titre": f"{assignes} ticket(s) assigné(s)",
                    "msg": f"{assignes} {tag.lower()} vous ont été affectés.",
                },
            )
        await audit.consigner(
            session,
            action="ASSIGNATION_LOT",
            acteur_id=courant["id"],
            acteur_email=courant["email"],
            module=module,
            cible_type=module,
            cible_id=f"{assignes} tickets",
            nouvelle={"responsable_id": corps.responsable_id, "assignes": assignes},
        )
        await session.commit()
        return {"assignes": assignes}

    @routeur.get("/{ident}", response_model=ActiviteDetail)
    async def detail(ident: str, courant: Courant, session: Session) -> dict[str, Any]:
        r = await charger_visible(session, ident, courant)
        return await detail_complet(r, session)

    @routeur.post("/{ident}/transition", response_model=ActiviteDetail)
    async def transitionner(
        ident: str, corps: TransitionDemande, courant: Courant, session: Session
    ) -> dict[str, Any]:
        await charger_visible(session, ident, courant)
        try:
            await transition(session, module, ident, corps.vers, courant)
        except ActiviteIntrouvable as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Introuvable."
            ) from exc
        except TransitionInterdite as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=f"Transition interdite : {exc}"
            ) from exc
        r = await charger_visible(session, ident, courant)
        return await detail_complet(r, session)

    @routeur.post("/{ident}/assignation", response_model=ActiviteDetail)
    async def assigner(
        ident: str, corps: AssignationDemande, courant: Courant, session: Session
    ) -> dict[str, Any]:
        avant = await charger_visible(session, ident, courant)
        if corps.responsable_id is not None:
            existe = await session.scalar(
                text("SELECT 1 FROM core.utilisateur WHERE id::text = :id AND actif"),
                {"id": corps.responsable_id},
            )
            if existe is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Agent introuvable ou inactif."
                )
        await repo.assigner(session, ident, corps.responsable_id)
        # Notifie l'agent nouvellement assigné (sauf s'il s'assigne lui-même).
        if (
            corps.responsable_id is not None
            and corps.responsable_id != avant["resp_id"]
            and corps.responsable_id != courant["id"]
        ):
            await session.execute(
                text(
                    "INSERT INTO core.notification "
                    "(destinataire_id, activite_id, type, titre, message) "
                    "VALUES (cast(:dest as uuid), cast(:aid as uuid), 'ASSIGNATION', :titre, :msg)"
                ),
                {
                    "dest": corps.responsable_id,
                    "aid": avant["id"],
                    "titre": f"Ticket assigné : {avant['reference']}",
                    "msg": avant["titre"],
                },
            )
        # Réaffectation : prévient aussi l'ancien responsable qu'il n'est plus en charge.
        if avant["resp_id"] is not None and avant["resp_id"] != corps.responsable_id:
            await notifier(
                session,
                destinataire_id=str(avant["resp_id"]),
                activite_id=str(avant["id"]),
                type_="ASSIGNATION",
                titre=f"Ticket réaffecté : {avant['reference']}",
                message=f"{avant['reference']} ne vous est plus assigné.",
            )
        await audit.consigner(
            session,
            action="ASSIGNATION",
            acteur_id=courant["id"],
            acteur_email=courant["email"],
            module=module,
            cible_type=module,
            cible_id=avant["reference"],
            ancienne={"responsable_id": avant["resp_id"]},
            nouvelle={"responsable_id": corps.responsable_id},
        )
        await session.commit()
        r = await charger_visible(session, ident, courant)
        return await detail_complet(r, session)

    @routeur.post("/{ident}/categorie", response_model=ActiviteDetail)
    async def changer_categorie(
        ident: str, corps: CategorieDemande, courant: Courant, session: Session
    ) -> dict[str, Any]:
        avant = await charger_visible(session, ident, courant)
        if corps.categorie_id is not None:
            ok = await session.scalar(
                text("SELECT 1 FROM core.categorie WHERE id::text = :c AND module = :m"),
                {"c": corps.categorie_id, "m": module},
            )
            if ok is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Catégorie inconnue pour ce module.",
                )
        await session.execute(
            text(
                "UPDATE core.activite SET categorie_id = cast(:c as uuid) "
                "WHERE id = cast(:id as uuid)"
            ),
            {"c": corps.categorie_id, "id": ident},
        )
        await audit.consigner(
            session,
            action="MODIFICATION",
            acteur_id=courant["id"],
            acteur_email=courant["email"],
            module=module,
            cible_type=module,
            cible_id=avant["reference"],
            nouvelle={"categorie_id": corps.categorie_id},
        )
        await session.commit()
        r = await charger_visible(session, ident, courant)
        return await detail_complet(r, session)

    @routeur.post("/{ident}/contributeurs", response_model=ActiviteDetail)
    async def ajouter_contributeur(
        ident: str, corps: ContributeurDemande, courant: Courant, session: Session
    ) -> dict[str, Any]:
        avant = await charger_visible(session, ident, courant)
        existe = await session.scalar(
            text("SELECT 1 FROM core.utilisateur WHERE id::text = :id AND actif"),
            {"id": corps.utilisateur_id},
        )
        if existe is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Agent introuvable ou inactif."
            )
        await repo.ajouter_contributeur(session, ident, corps.utilisateur_id)
        # Notifie le contributeur ajouté (sauf s'il s'ajoute lui-même).
        if corps.utilisateur_id != courant["id"]:
            await session.execute(
                text(
                    "INSERT INTO core.notification "
                    "(destinataire_id, activite_id, type, titre, message) "
                    "VALUES (cast(:dest as uuid), cast(:aid as uuid), 'ASSIGNATION', :titre, :msg)"
                ),
                {
                    "dest": corps.utilisateur_id,
                    "aid": avant["id"],
                    "titre": f"Contributeur : {avant['reference']}",
                    "msg": avant["titre"],
                },
            )
        await audit.consigner(
            session,
            action="MODIFICATION",
            acteur_id=courant["id"],
            acteur_email=courant["email"],
            module=module,
            cible_type=module,
            cible_id=avant["reference"],
            nouvelle={"contributeur_ajoute": corps.utilisateur_id},
        )
        await session.commit()
        r = await charger_visible(session, ident, courant)
        return await detail_complet(r, session)

    @routeur.delete("/{ident}/contributeurs/{utilisateur_id}", response_model=ActiviteDetail)
    async def retirer_contributeur(
        ident: str, utilisateur_id: str, courant: Courant, session: Session
    ) -> dict[str, Any]:
        avant = await charger_visible(session, ident, courant)
        await repo.retirer_contributeur(session, ident, utilisateur_id)
        await audit.consigner(
            session,
            action="MODIFICATION",
            acteur_id=courant["id"],
            acteur_email=courant["email"],
            module=module,
            cible_type=module,
            cible_id=avant["reference"],
            ancienne={"contributeur_retire": utilisateur_id},
        )
        await session.commit()
        r = await charger_visible(session, ident, courant)
        return await detail_complet(r, session)

    @routeur.post("/{ident}/valideurs", response_model=ActiviteDetail)
    async def ajouter_valideur(
        ident: str, corps: ContributeurDemande, courant: Courant, session: Session
    ) -> dict[str, Any]:
        avant = await charger_visible(session, ident, courant)
        existe = await session.scalar(
            text("SELECT 1 FROM core.utilisateur WHERE id::text = :id AND actif"),
            {"id": corps.utilisateur_id},
        )
        if existe is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Agent introuvable ou inactif."
            )
        await repo.ajouter_valideur(session, ident, corps.utilisateur_id)
        # Notifie le valideur désigné (sauf s'il se désigne lui-même).
        if corps.utilisateur_id != courant["id"]:
            await session.execute(
                text(
                    "INSERT INTO core.notification "
                    "(destinataire_id, activite_id, type, titre, message) "
                    "VALUES (cast(:dest as uuid), cast(:aid as uuid), 'VALIDATION', :titre, :msg)"
                ),
                {
                    "dest": corps.utilisateur_id,
                    "aid": avant["id"],
                    "titre": f"Validation demandée : {avant['reference']}",
                    "msg": avant["titre"],
                },
            )
        await audit.consigner(
            session,
            action="MODIFICATION",
            acteur_id=courant["id"],
            acteur_email=courant["email"],
            module=module,
            cible_type=module,
            cible_id=avant["reference"],
            nouvelle={"valideur_ajoute": corps.utilisateur_id},
        )
        await session.commit()
        r = await charger_visible(session, ident, courant)
        return await detail_complet(r, session)

    @routeur.delete("/{ident}/valideurs/{utilisateur_id}", response_model=ActiviteDetail)
    async def retirer_valideur(
        ident: str, utilisateur_id: str, courant: Courant, session: Session
    ) -> dict[str, Any]:
        avant = await charger_visible(session, ident, courant)
        await repo.retirer_valideur(session, ident, utilisateur_id)
        await audit.consigner(
            session,
            action="MODIFICATION",
            acteur_id=courant["id"],
            acteur_email=courant["email"],
            module=module,
            cible_type=module,
            cible_id=avant["reference"],
            ancienne={"valideur_retire": utilisateur_id},
        )
        await session.commit()
        r = await charger_visible(session, ident, courant)
        return await detail_complet(r, session)

    @routeur.post("/{ident}/decision", response_model=ActiviteDetail)
    async def decider(
        ident: str, corps: DecisionDemande, courant: Courant, session: Session
    ) -> dict[str, Any]:
        """Un valideur approuve ou rejette l'activité (approbation ITIL : CAB/ECAB, demandes)."""
        avant = await charger_visible(session, ident, courant)
        ok = await repo.definir_decision(session, ident, courant["id"], corps.decision)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous n'êtes pas valideur de cette activité.",
            )
        libelle = "approuvé" if corps.decision == "APPROUVE" else "rejeté"
        if avant["resp_id"] is not None and str(avant["resp_id"]) != courant["id"]:
            await notifier(
                session,
                destinataire_id=str(avant["resp_id"]),
                activite_id=str(avant["id"]),
                type_="VALIDATION",
                titre=f"{avant['reference']} — {libelle} par un valideur",
                message=f"{courant['email']} a {libelle} {avant['reference']}.",
            )
        await audit.consigner(
            session,
            action="MODIFICATION",
            acteur_id=courant["id"],
            acteur_email=courant["email"],
            module=module,
            cible_type=module,
            cible_id=avant["reference"],
            nouvelle={"decision": corps.decision},
        )
        await session.commit()
        r = await charger_visible(session, ident, courant)
        return await detail_complet(r, session)

    if avec_revue:

        @routeur.post("/{ident}/revue", response_model=ActiviteDetail)
        async def planifier_revue(
            ident: str, corps: RevueDemande, courant: Courant, session: Session
        ) -> dict[str, Any]:
            avant = await charger_visible(session, ident, courant)
            fragment = corps.model_dump(exclude_unset=True, mode="json")
            if fragment:
                await session.execute(
                    text(
                        "UPDATE core.activite SET donnees = donnees || cast(:f as jsonb) "
                        "WHERE id = cast(:id as uuid)"
                    ),
                    {"id": ident, "f": json.dumps(fragment)},
                )
                await audit.consigner(
                    session,
                    action="MODIFICATION",
                    acteur_id=courant["id"],
                    acteur_email=courant["email"],
                    module=module,
                    cible_type=module,
                    cible_id=avant["reference"],
                    nouvelle=fragment,
                )
                await session.commit()
            r = await charger_visible(session, ident, courant)
            return await detail_complet(r, session)

    if avec_escalade:

        @routeur.post("/{ident}/escalader", response_model=ActiviteDetail)
        async def escalader(ident: str, courant: Courant, session: Session) -> dict[str, Any]:
            avant = await charger_visible(session, ident, courant)
            niveau = int(_donnees(avant).get("niveau_support", 1))
            if niveau >= 3:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Déjà au niveau de support maximal (N3).",
                )
            niveau += 1
            await session.execute(
                text(
                    "UPDATE core.activite SET donnees = donnees || cast(:f as jsonb) "
                    "WHERE id = cast(:id as uuid)"
                ),
                {"id": ident, "f": json.dumps({"niveau_support": niveau})},
            )
            # Notifie le gestionnaire de l'escalade fonctionnelle.
            if avant["resp_id"] is not None and str(avant["resp_id"]) != courant["id"]:
                await notifier(
                    session,
                    destinataire_id=str(avant["resp_id"]),
                    activite_id=str(avant["id"]),
                    # Type dédié : 'ESCALADE' est réservé (index unique) à l'escalade SLA auto.
                    type_="ESCALADE_SUPPORT",
                    titre=f"Escalade N{niveau} — {avant['reference']}",
                    message=f"{avant['reference']} a été escaladé au support niveau {niveau}.",
                )
            await audit.consigner(
                session,
                action="ESCALADE",
                acteur_id=courant["id"],
                acteur_email=courant["email"],
                module=module,
                cible_type=module,
                cible_id=avant["reference"],
                nouvelle={"niveau_support": niveau},
            )
            await session.commit()
            r = await charger_visible(session, ident, courant)
            return await detail_complet(r, session)

    if editable:

        @routeur.patch("/{ident}", response_model=ActiviteDetail)
        async def modifier(
            ident: str, corps: ActiviteMaj, courant: Courant, session: Session
        ) -> dict[str, Any]:
            avant = await charger_visible(session, ident, courant)
            champs = corps.model_dump(exclude_unset=True)
            # Colonnes directes (titre, description).
            fragments = []
            params: dict[str, Any] = {"id": ident}
            if champs.get("titre") is not None:
                params["titre"] = phrase_propre(champs["titre"])
                fragments.append("titre = :titre")
            if "description" in champs:
                params["description"] = champs["description"]
                fragments.append("description = :description")
            if fragments:
                await session.execute(
                    text(
                        f"UPDATE core.activite SET {', '.join(fragments)} "
                        "WHERE id = cast(:id as uuid)"
                    ),
                    params,
                )
            # Champs RFC -> fusionnés dans la colonne JSON `donnees`.
            fragment_json = {c: champs[c] for c in _CHAMPS_RFC if c in champs}
            if fragment_json:
                await session.execute(
                    text(
                        "UPDATE core.activite SET donnees = donnees || cast(:f as jsonb) "
                        "WHERE id = cast(:id as uuid)"
                    ),
                    {"id": ident, "f": json.dumps(fragment_json)},
                )
            if fragments or fragment_json:
                await audit.consigner(
                    session,
                    action="MODIFICATION",
                    acteur_id=courant["id"],
                    acteur_email=courant["email"],
                    module=module,
                    cible_type=module,
                    cible_id=avant["reference"],
                    nouvelle={k: champs[k] for k in champs},
                )
                await session.commit()
            r = await charger_visible(session, ident, courant)
            return await detail_complet(r, session)

    if avec_taches:
        _enregistrer_taches(routeur, module, charger_visible, Courant, detail_complet)
    if avec_documents:
        enregistrer_documents(routeur, module=module, charger=charger_visible, Courant=Courant)

    return routeur


def _tache_resume(r: RowMapping) -> dict[str, Any]:
    assigne = None
    if r["assigne_email"] is not None:
        assigne = {
            "prenom": r["assigne_prenom"],
            "nom": r["assigne_nom"],
            "email": r["assigne_email"],
        }
    return {
        "id": r["id"],
        "titre": r["titre"],
        "description": r["description"],
        "statut": r["statut"],
        "assigne": assigne,
        "assigne_id": r["assigne_id"],
        "echeance": r["echeance"],
        "ordre": r["ordre"],
    }


def _enregistrer_taches(
    routeur: APIRouter,
    module: str,
    charger_visible: Callable[[AsyncSession, str, dict[str, Any]], Awaitable[RowMapping]],
    Courant: Any,  # noqa: N803 - annotation FastAPI (Depends), même nom que la variable locale
    detail_complet: Callable[[RowMapping, AsyncSession], Awaitable[dict[str, Any]]],
) -> None:
    """Endpoints de tâches d'un module d'activités (avancement + cycle de vie dérivés)."""

    async def _charger_tache(
        session: AsyncSession, ident: str, tache_id: str, courant: dict[str, Any]
    ) -> RowMapping:
        await charger_visible(session, ident, courant)
        t = await tache_repo.par_id(session, tache_id)
        if t is None or t["activite_id"] != ident:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tâche introuvable.")
        return t

    async def _verifier_agent(session: AsyncSession, agent_id: str | None) -> None:
        if agent_id is None:
            return
        existe = await session.scalar(
            text("SELECT 1 FROM core.utilisateur WHERE id::text = :id AND actif"), {"id": agent_id}
        )
        if existe is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Agent introuvable ou inactif."
            )

    @routeur.get("/{ident}/taches", response_model=list[Tache])
    async def lister_taches(
        ident: str, courant: Courant, session: Session
    ) -> list[dict[str, Any]]:
        await charger_visible(session, ident, courant)
        return [_tache_resume(t) for t in await tache_repo.lister(session, ident)]

    @routeur.post(
        "/{ident}/taches", response_model=ActiviteDetail, status_code=status.HTTP_201_CREATED
    )
    async def creer_tache_activite(
        ident: str, corps: TacheCreation, courant: Courant, session: Session
    ) -> dict[str, Any]:
        await charger_visible(session, ident, courant)
        await _verifier_agent(session, corps.assigne_id)
        await creer_tache(
            session,
            ident,
            module,
            {
                "titre": phrase_propre(corps.titre),
                "description": corps.description,
                "assigne_id": corps.assigne_id,
                "echeance": corps.echeance,
                "ordre": corps.ordre,
            },
            courant,
        )
        await session.commit()
        r = await charger_visible(session, ident, courant)
        return await detail_complet(r, session)

    @routeur.patch("/{ident}/taches/{tache_id}", response_model=ActiviteDetail)
    async def maj_tache_activite(
        ident: str, tache_id: str, corps: TacheMaj, courant: Courant, session: Session
    ) -> dict[str, Any]:
        tache = await _charger_tache(session, ident, tache_id, courant)
        champs = corps.model_dump(exclude_unset=True)
        await _verifier_agent(session, champs.get("assigne_id"))
        if champs.get("titre") is not None:
            champs["titre"] = phrase_propre(champs["titre"])
        await maj_tache(session, dict(tache), module, champs, courant)
        await session.commit()
        r = await charger_visible(session, ident, courant)
        return await detail_complet(r, session)

    @routeur.delete("/{ident}/taches/{tache_id}", response_model=ActiviteDetail)
    async def supprimer_tache_activite(
        ident: str, tache_id: str, courant: Courant, session: Session
    ) -> dict[str, Any]:
        tache = await _charger_tache(session, ident, tache_id, courant)
        await supprimer_tache(session, dict(tache), module, courant)
        await session.commit()
        r = await charger_visible(session, ident, courant)
        return await detail_complet(r, session)
