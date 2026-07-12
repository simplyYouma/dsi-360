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
    AucunValideur,
    DossierIncomplet,
    TransitionInterdite,
    TransitionReservee,
    appliquer_decisions,
    creer_activite,
    reevaluer,
    transition,
)
from dsi360.application.autorisations import ACTEUR, ADMIN, capacites, charger_roles
from dsi360.application.notifications import notifier
from dsi360.application.taches import creer_tache, maj_tache, supprimer_tache
from dsi360.domain.etats import (
    est_etat_terminal,
    est_porte_validation,
    ordre_etats,
    transition_reservee,
    transitions_possibles,
)
from dsi360.domain.revue import prochaine_revue
from dsi360.domain.sla import statut_sla
from dsi360.domain.texte import phrase_propre
from dsi360.infrastructure import audit
from dsi360.infrastructure.db import session_scope
from dsi360.infrastructure.export import vers_csv, vers_xlsx
from dsi360.infrastructure.repositories import activite as repo
from dsi360.infrastructure.repositories import tache as tache_repo
from dsi360.interface.routeurs.documents_communs import enregistrer_documents
from dsi360.interface.routeurs.liens_communs import enregistrer_liens
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
    EvaluationDemande,
    NoteCreation,
    NoteItem,
    PageActivites,
    ReordreTaches,
    ResultatAssignationLot,
    RevueDemande,
    Tache,
    TacheCreation,
    TacheMaj,
    TransitionDemande,
)
from dsi360.interface.securite import (
    ContexteActivite,
    exiger_acces,
    exiger_admin,
    exiger_agent_designable,
    exiger_champs_tache,
    exiger_role_activite,
    exiger_role_activite_courant,
)

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


def _resume(r: RowMapping, maintenant: datetime, importe: bool = False) -> dict[str, Any]:
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
        "contributeur": r["contributeur"] if "contributeur" in r else None,
        "responsable_id": r["resp_id"],
        "nb_commentaires": r["nb_commentaires"],
        "nb_non_vus": r["nb_non_vus"] if "nb_non_vus" in r else 0,
        # Le support voit d'un coup d'œil où se trouve chaque ticket, sans ouvrir les fiches.
        "niveau_support": _niveau_support(r, importe),
        "transfere_dbs": _transfere_dbs(r, importe),
    }


def _detail(
    module: str, r: RowMapping, maintenant: datetime, importe: bool = False
) -> dict[str, Any]:
    return {
        **_resume(r, maintenant, importe),
        "description": r["description"],
        "categorie_id": str(r["categorie_id"]) if r["categorie_id"] is not None else None,
        "impact": r["impact"],
        "urgence": r["urgence"],
        "sla_prise_en_charge_le": r["sla_prise_en_charge_le"],
        "resolu_le": r["resolu_le"],
        "cloture_le": r["cloture_le"],
        # On masque les issues réservées aux valideurs (elles passent par la décision, pas par un
        # changement d'état manuel) : l'UI n'offre que les transitions vraiment actionnables.
        "transitions_possibles": [
            e
            for e in transitions_possibles(module, r["statut"])
            if not transition_reservee(module, r["statut"], e)
        ],
        "etats": ordre_etats(module),
        # L'état attend-il la décision des valideurs ? L'écran dit alors pourquoi rien n'avance.
        "en_attente_validation": est_porte_validation(module, r["statut"]),
        "avancement": int(_donnees(r).get("avancement", 0)),
        **{champ: _donnees(r).get(champ) for champ in _CHAMPS_RFC},
        "periodicite": _donnees(r).get("periodicite"),
        "prochaine_revue": _donnees(r).get("prochaine_revue"),
        "derniere_revue": _donnees(r).get("derniere_revue"),
    }


# Champs RFC (changement, ITIL SI-12.04) stockés dans la colonne JSON `donnees`.
_CHAMPS_RFC = (
    "analyse_impact",
    "analyse_risque",
    "plan_deploiement",
    "plan_retour_arriere",
    "bilan_post_implementation",
)


# Niveau 3 = DBS, hors du système. La DSI ne tient que N1 et N2 : aucun compte ne porte le
# niveau 3 (ADR-0003 §3).
NIVEAU_DBS = 3
NIVEAU_DEFAUT = 1


def _niveau_support(r: RowMapping, importe: bool) -> int:
    """Niveau du ticket, **déduit** de son gestionnaire (ADR-0005).

    Le gestionnaire vient du fichier importé. Rapproché d'un compte DSI, le ticket est à son
    niveau ; sinon c'est DBS — tout ce qui n'est pas nous est DBS — et le ticket est au niveau 3.
    Les modules qui ne viennent pas de l'import n'ont pas de niveau de support.
    """
    if not importe:
        return NIVEAU_DEFAUT
    if r["resp_id"] is None:
        return NIVEAU_DBS
    niveau = r["resp_niveau"] if "resp_niveau" in r else None
    return int(niveau) if niveau is not None else NIVEAU_DEFAUT


def _transfere_dbs(r: RowMapping, importe: bool) -> bool:
    """Chez DBS : le gestionnaire du fichier n'est aucun des nôtres."""
    return importe and r["resp_id"] is None


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


async def _exiger_valideurs_ouverts(session: AsyncSession, ident: str) -> None:
    """Refuse d'ajouter/retirer un valideur dès qu'une décision est tombée.

    Une fois qu'un valideur a tranché, changer la liste fausserait le décompte d'approbation
    (une décision disparaîtrait de l'agrégation). La composition du comité est alors figée.
    """
    if await repo.des_valideurs_ont_decide(session, ident):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un valideur a déjà tranché : la liste des valideurs est figée.",
        )


def creer_routeur(
    module: str,
    acces: str,
    prefixe: str,
    tag: str,
    *,
    import_uniquement: bool = False,
    avec_taches: bool = False,
    avec_documents: bool = False,
    avec_revue: bool = False,
    avec_notes: bool = False,
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

    # Distribuer le travail (assigner, évaluer, désigner) revient à l'administrateur ; l'activité
    # est chargée une fois par la dépendance et voyage dans le contexte (cf. ADR-0003, docs/04).
    CtxAdmin = Annotated[  # noqa: N806
        ContexteActivite,
        Depends(exiger_role_activite(module, acces, {ADMIN}, bloquer_si_clos=True)),
    ]

    # Faire avancer le sujet revient à l'administrateur, au gestionnaire et aux contributeurs.
    #
    # Incidents et demandes font exception : ils viennent de l'import quotidien, et un ticket sans
    # gestionnaire rapproché n'aurait aucun acteur. Pour eux, l'accès au module suffit encore.
    requis_travail: set[str] = set() if import_uniquement else {ACTEUR}
    # Verrouillé après clôture : transitions, notes, tâches, documents ne bougent plus.
    CtxActeur = Annotated[  # noqa: N806
        ContexteActivite,
        Depends(exiger_role_activite(module, acces, requis_travail, bloquer_si_clos=True)),
    ]
    CourantActeur = Annotated[  # noqa: N806
        dict[str, Any],
        Depends(exiger_role_activite_courant(module, acces, requis_travail, bloquer_si_clos=True)),
    ]
    # Le dossier reste ouvert après clôture : RFC (dont le bilan post-implémentation) et liens.
    CtxDossier = Annotated[  # noqa: N806
        ContexteActivite, Depends(exiger_role_activite(module, acces, requis_travail))
    ]
    CourantDossier = Annotated[  # noqa: N806
        dict[str, Any], Depends(exiger_role_activite_courant(module, acces, requis_travail))
    ]

    # Aucun rôle exigé : il suffit de voir l'activité. La route tranche ensuite elle-même — mettre
    # à jour une tâche : tous les champs pour un acteur, le statut seul pour son assigné. Bloquée
    # après clôture : une tâche d'activité close ne se modifie plus (même son statut).
    CtxLecture = Annotated[  # noqa: N806
        ContexteActivite, Depends(exiger_role_activite(module, acces, bloquer_si_clos=True))
    ]

    async def charger_visible(
        session: AsyncSession, ident: str, courant: dict[str, Any]
    ) -> RowMapping:
        r = await repo.par_id(session, module, ident, moi=courant["id"])
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
            moi=courant["id"],
        )
        maintenant = datetime.now(UTC)
        return {
            "elements": [_resume(r, maintenant, import_uniquement) for r in lignes],
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

    async def detail_complet(
        r: RowMapping, session: AsyncSession, courant: dict[str, Any]
    ) -> dict[str, Any]:
        base = _detail(module, r, datetime.now(UTC), import_uniquement)
        base["historique"] = await audit.historique_statuts(session, module, r["reference"])
        base["contributeurs"] = [
            dict(c) for c in await repo.lister_contributeurs(session, r["id"])
        ]
        base["valideurs"] = [dict(c) for c in await repo.lister_valideurs(session, r["id"])]
        # Le serveur calcule les capacités ; l'écran obéit. La règle ne vit qu'ici.
        clos = est_etat_terminal(module, r["statut"])
        roles = await charger_roles(session, r, courant)
        base["permissions"] = capacites(roles, lecture_seule=import_uniquement, clos=clos)
        # Décision de l'appelant, s'il est valideur : l'écran fige alors ses boutons.
        base["ma_decision"] = next(
            (v["decision"] for v in base["valideurs"] if str(v["id"]) == courant["id"]), None
        )
        # Verrouillage : dès qu'un valideur a tranché (ou l'activité close), la liste est figée.
        base["valideurs_verrouilles"] = clos or any(
            v["decision"] is not None for v in base["valideurs"]
        )
        return base

    # Un incident ou une demande n'est pas pilotable ici, mais la DSI veut le suivre :
    # l'administrateur y désigne des contributeurs de chez nous — y compris quand le rapport a mis
    # DBS au gestionnaire. Le ticket entre dans leur file, sans qu'ils puissent le modifier.
    @routeur.post("/{ident}/contributeurs", response_model=ActiviteDetail)
    async def ajouter_contributeur(
        ident: str, corps: ContributeurDemande, ctx: CtxAdmin, session: Session
    ) -> dict[str, Any]:
        """Un contributeur a les droits de travail du gestionnaire : seul l'admin le désigne."""
        courant, avant = ctx.courant, ctx.activite
        await exiger_agent_designable(session, corps.utilisateur_id, acces)
        await repo.ajouter_contributeur(session, ident, corps.utilisateur_id)
        # Notifie le contributeur ajouté (sauf s'il s'ajoute lui-même).
        if corps.utilisateur_id != courant["id"]:
            await notifier(
                session,
                destinataire_id=corps.utilisateur_id,
                activite_id=str(avant["id"]),
                type_="ASSIGNATION",
                titre=f"Contributeur désigné — {avant['reference']}",
                message=f"Vous suivez désormais {avant['reference']} « {avant['titre']} ».",
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
        return await detail_complet(r, session, courant)

    @routeur.delete("/{ident}/contributeurs/{utilisateur_id}", response_model=ActiviteDetail)
    async def retirer_contributeur(
        ident: str, utilisateur_id: str, ctx: CtxAdmin, session: Session
    ) -> dict[str, Any]:
        courant, avant = ctx.courant, ctx.activite
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
        return await detail_complet(r, session, courant)

    # Incidents et demandes ne se pilotent pas ici : ils sont traités dans un autre système,
    # et l'import du lendemain effacerait toute modification. On observe, on n'agit pas.
    if not import_uniquement:
        # Déclaré avant /{ident} pour éviter que "assignation-lot" soit pris pour un identifiant.
        @routeur.post("/assignation-lot", response_model=ResultatAssignationLot)
        async def assigner_lot(
            corps: AssignationLot, courant: Courant, session: Session
        ) -> dict[str, int]:
            # Cette route ne porte pas sur une activité : la garde de rôle ne s'applique pas,
            # on exige l'administrateur directement. Le périmètre reste filtré ticket par ticket.
            exiger_admin(courant)
            await exiger_agent_designable(session, corps.responsable_id, acces)
            assignes = 0
            for ident in corps.ids:
                r = await repo.par_id(session, module, ident, moi=courant["id"])
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
        return await detail_complet(r, session, courant)

    # Incidents et demandes ne se pilotent pas ici : ils sont traités dans un autre système,
    # et l'import du lendemain effacerait toute modification. On observe, on n'agit pas.
    if not import_uniquement:
        @routeur.post("/{ident}/transition", response_model=ActiviteDetail)
        async def transitionner(
            ident: str, corps: TransitionDemande, ctx: CtxActeur, session: Session
        ) -> dict[str, Any]:
            """Faire avancer le sujet : gestionnaire, contributeurs et administrateur."""
            courant = ctx.courant
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
            except DossierIncomplet as exc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Le comité ne peut pas délibérer sur un dossier incomplet. "
                        f"Complétez d'abord : {', '.join(exc.manquantes)}."
                    ),
                ) from exc
            except TransitionReservee as exc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Cette étape se décide via les valideurs (approbation), "
                        "pas par un changement d'état manuel."
                    ),
                ) from exc
            except AucunValideur as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Désignez au moins un valideur avant de soumettre au comité.",
                ) from exc
            r = await charger_visible(session, ident, courant)
            return await detail_complet(r, session, courant)

        @routeur.post("/{ident}/assignation", response_model=ActiviteDetail)
        async def assigner(
            ident: str, corps: AssignationDemande, ctx: CtxAdmin, session: Session
        ) -> dict[str, Any]:
            """Confier l'activité à un gestionnaire. Seul l'administrateur distribue le travail."""
            courant, avant = ctx.courant, ctx.activite
            await exiger_agent_designable(session, corps.responsable_id, acces)
            await repo.assigner(session, ident, corps.responsable_id)
            # Notifie l'agent nouvellement assigné (sauf s'il s'assigne lui-même).
            if (
                corps.responsable_id is not None
                and corps.responsable_id != avant["resp_id"]
                and corps.responsable_id != courant["id"]
            ):
                await notifier(
                    session,
                    destinataire_id=corps.responsable_id,
                    activite_id=str(avant["id"]),
                    type_="ASSIGNATION",
                    titre=f"Activité assignée — {avant['reference']}",
                    message=f"{avant['reference']} « {avant['titre']} » vous a été assignée.",
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
            return await detail_complet(r, session, courant)

        @routeur.post("/{ident}/categorie", response_model=ActiviteDetail)
        async def changer_categorie(
            ident: str, corps: CategorieDemande, ctx: CtxAdmin, session: Session
        ) -> dict[str, Any]:
            """Catégorie, ou Type d'un changement : il pilote le CAB et dérive la priorité."""
            courant, avant = ctx.courant, ctx.activite
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
            return await detail_complet(r, session, courant)

        @routeur.post("/{ident}/valideurs", response_model=ActiviteDetail)
        async def ajouter_valideur(
            ident: str, corps: ContributeurDemande, ctx: CtxAdmin, session: Session
        ) -> dict[str, Any]:
            """Seul l'admin désigne les valideurs : sinon on s'auto-désigne, puis on s'approuve."""
            courant, avant = ctx.courant, ctx.activite
            await _exiger_valideurs_ouverts(session, ident)
            await exiger_agent_designable(session, corps.utilisateur_id, acces)
            await repo.ajouter_valideur(session, ident, corps.utilisateur_id)
            # Notifie le valideur désigné (sauf s'il se désigne lui-même).
            if corps.utilisateur_id != courant["id"]:
                await notifier(
                    session,
                    destinataire_id=corps.utilisateur_id,
                    activite_id=str(avant["id"]),
                    type_="VALIDATION",
                    titre=f"Validation demandée — {avant['reference']}",
                    message=f"Votre décision est attendue sur {avant['reference']} "
                    f"« {avant['titre']} ».",
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
            return await detail_complet(r, session, courant)

        @routeur.delete("/{ident}/valideurs/{utilisateur_id}", response_model=ActiviteDetail)
        async def retirer_valideur(
            ident: str, utilisateur_id: str, ctx: CtxAdmin, session: Session
        ) -> dict[str, Any]:
            courant, avant = ctx.courant, ctx.activite
            await _exiger_valideurs_ouverts(session, ident)
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
            return await detail_complet(r, session, courant)

        @routeur.post("/{ident}/decision", response_model=ActiviteDetail)
        async def decider(
            ident: str, corps: DecisionDemande, courant: Courant, session: Session
        ) -> dict[str, Any]:
            """Un valideur approuve ou rejette l'activité (ITIL : CAB/ECAB, demandes)."""
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
            # Enchaîne le workflow : unanimité → validé ; un rejet → rejeté (ITIL CAB/ECAB).
            await appliquer_decisions(session, module, ident, courant)
            r = await charger_visible(session, ident, courant)
            return await detail_complet(r, session, courant)

    if avec_revue:

        @routeur.post("/{ident}/revue", response_model=ActiviteDetail)
        async def planifier_revue(
            ident: str, corps: RevueDemande, ctx: CtxActeur, session: Session
        ) -> dict[str, Any]:
            courant = ctx.courant
            avant = await charger_visible(session, ident, courant)
            fragment = corps.model_dump(exclude_unset=True, mode="json")
            # Choisir une périodicité fixe la prochaine revue : inutile de resaisir une date.
            if fragment.get("periodicite") and "prochaine_revue" not in fragment:
                fragment["prochaine_revue"] = prochaine_revue(
                    fragment["periodicite"], datetime.now(UTC).date()
                ).isoformat()
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
            return await detail_complet(r, session, courant)

        @routeur.post("/{ident}/revue/effectuee", response_model=ActiviteDetail)
        async def marquer_revue_effectuee(
            ident: str, ctx: CtxActeur, session: Session
        ) -> dict[str, Any]:
            """Enregistre la revue du jour et reporte l'échéance suivante selon la périodicité.

            Attester qu'une revue a eu lieu engage la DSI : réservé aux acteurs du sujet.
            Sans périodicité, aucune cadence n'existe : on refuse plutôt que d'inventer une date.
            """
            courant = ctx.courant
            avant = await charger_visible(session, ident, courant)
            periodicite = _donnees(avant).get("periodicite")
            if not periodicite:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Définissez d'abord une périodicité pour cette revue.",
                )
            try:
                faite_le = datetime.now(UTC).date()
                suivante = prochaine_revue(str(periodicite), faite_le)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
                ) from exc
            fragment = {
                "derniere_revue": faite_le.isoformat(),
                "prochaine_revue": suivante.isoformat(),
            }
            # `revue_notifiee_le` est retiré : la nouvelle échéance doit pouvoir rappeler.
            await session.execute(
                text(
                    "UPDATE core.activite SET donnees = "
                    "(donnees - 'revue_notifiee_le') || cast(:f as jsonb) "
                    "WHERE id = cast(:id as uuid)"
                ),
                {"id": ident, "f": json.dumps(fragment)},
            )
            await audit.consigner(
                session,
                action="REVUE_EFFECTUEE",
                acteur_id=courant["id"],
                acteur_email=courant["email"],
                module=module,
                cible_type=module,
                cible_id=avant["reference"],
                ancienne={"prochaine_revue": _donnees(avant).get("prochaine_revue")},
                nouvelle=fragment,
            )
            await session.commit()
            r = await charger_visible(session, ident, courant)
            return await detail_complet(r, session, courant)

    if avec_notes:

        @routeur.get("/{ident}/notes", response_model=list[NoteItem])
        async def lister_notes(
            ident: str, courant: Courant, session: Session
        ) -> list[dict[str, Any]]:
            await charger_visible(session, ident, courant)
            lignes = (
                await session.execute(
                    text(
                        "SELECT n.id::text AS id, n.texte, n.contexte, "
                        "n.auteur_email AS auteur, n.cree_le "
                        "FROM core.note n WHERE n.activite_id = cast(:id as uuid) "
                        "ORDER BY n.cree_le DESC"
                    ),
                    {"id": ident},
                )
            ).mappings().all()
            return [dict(x) for x in lignes]

        @routeur.post(
            "/{ident}/notes", response_model=NoteItem, status_code=status.HTTP_201_CREATED
        )
        async def creer_note(
            ident: str, corps: NoteCreation, ctx: CtxActeur, session: Session
        ) -> dict[str, Any]:
            courant, avant = ctx.courant, ctx.activite
            ligne = (
                await session.execute(
                    text(
                        "INSERT INTO core.note (activite_id, texte, auteur_email) "
                        "VALUES (cast(:aid as uuid), :texte, :email) "
                        "RETURNING id::text AS id, texte, contexte, auteur_email AS auteur, cree_le"
                    ),
                    {"aid": ident, "texte": corps.texte.strip(), "email": courant["email"]},
                )
            ).mappings().one()
            await audit.consigner(
                session,
                action="CREATION",
                acteur_id=courant["id"],
                acteur_email=courant["email"],
                module=module,
                cible_type="note",
                cible_id=avant["reference"],
                nouvelle={"texte": corps.texte.strip()[:200]},
            )
            await session.commit()
            return dict(ligne)


    # Incidents et demandes ne se pilotent pas ici : ils sont traités dans un autre système,
    # et l'import du lendemain effacerait toute modification. On observe, on n'agit pas.
    if not import_uniquement:
        @routeur.post("/{ident}/evaluation", response_model=ActiviteDetail)
        async def evaluer(
            ident: str, corps: EvaluationDemande, ctx: CtxAdmin, session: Session
        ) -> dict[str, Any]:
            """Réévalue impact/urgence : recalcule la priorité et repositionne les échéances SLA.

            Fixer la priorité, c'est fixer l'engagement envers le demandeur : réservé à l'admin.
            """
            courant = ctx.courant
            try:
                await reevaluer(
                    session,
                    module,
                    ident,
                    impact=corps.impact,
                    urgence=corps.urgence,
                    acteur=courant,
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
                ) from exc
            await session.commit()
            r = await charger_visible(session, ident, courant)
            return await detail_complet(r, session, courant)

    if editable:

        @routeur.patch("/{ident}", response_model=ActiviteDetail)
        async def modifier(
            ident: str, corps: ActiviteMaj, ctx: CtxDossier, session: Session
        ) -> dict[str, Any]:
            """Titre, description, analyses RFC : c'est du travail, pas de la lecture.

            Après clôture, seul le dossier RFC reste éditable (le bilan post-implémentation se
            remplit *après* la mise en production) : titre et description sont alors refusés.
            """
            courant = ctx.courant
            champs = corps.model_dump(exclude_unset=True)
            if est_etat_terminal(module, ctx.activite["statut"]):
                hors_dossier = sorted(set(champs) - set(_CHAMPS_RFC))
                if hors_dossier:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Activité clôturée : seules les analyses/plans (RFC) restent "
                            f"modifiables (champs refusés : {', '.join(hors_dossier)})."
                        ),
                    )
            avant = await charger_visible(session, ident, courant)
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
            return await detail_complet(r, session, courant)

    # Lire reste ouvert à qui voit l'activité ; écrire est réservé aux acteurs de travail.
    if avec_taches:
        _enregistrer_taches(
            routeur, module, charger_visible, Courant, detail_complet, CourantActeur,
            CtxLecture, acces,
        )
        # Les modules à tâches ont aussi les liens utiles. Ils restent ouverts après clôture
        # (documenter un changement clos par un lien de suivi doit rester possible).
        enregistrer_liens(
            routeur,
            module=module,
            charger=charger_visible,
            Courant=Courant,
            Session=Session,
            CourantEcriture=CourantDossier,
        )
    if avec_documents:
        enregistrer_documents(
            routeur,
            module=module,
            charger=charger_visible,
            Courant=Courant,
            CourantEcriture=CourantActeur,
            avec_taches=avec_taches,
        )

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
        "nb_commentaires": r["nb_commentaires"],
        "nb_non_vus": r["nb_non_vus"] if "nb_non_vus" in r else 0,
    }


def _enregistrer_taches(
    routeur: APIRouter,
    module: str,
    charger_visible: Callable[[AsyncSession, str, dict[str, Any]], Awaitable[RowMapping]],
    Courant: Any,  # noqa: N803 - annotation FastAPI (Depends), même nom que la variable locale
    detail_complet: Callable[[RowMapping, AsyncSession, dict[str, Any]], Awaitable[dict[str, Any]]],
    CourantActeur: Any,  # noqa: N803
    CtxTache: Any,  # noqa: N803
    acces: str,
) -> None:
    """Endpoints de tâches d'un module d'activités (avancement + cycle de vie dérivés).

    Créer, supprimer et réordonner sont réservés aux acteurs de travail. La mise à jour reste
    ouverte au périmètre : c'est le contrôle champ par champ qui y tranche (l'assigné d'une tâche
    n'en change que le statut).
    """

    async def _charger_tache(
        session: AsyncSession, ident: str, tache_id: str, courant: dict[str, Any]
    ) -> RowMapping:
        await charger_visible(session, ident, courant)
        t = await tache_repo.par_id(session, tache_id, moi=courant["id"])
        if t is None or t["activite_id"] != ident:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tâche introuvable.")
        return t

    async def _verifier_agent(session: AsyncSession, agent_id: str | None) -> None:
        """On n'assigne une tâche qu'à un compte actif ayant l'accès au module (422 sinon)."""
        await exiger_agent_designable(session, agent_id, acces)

    @routeur.get("/{ident}/taches", response_model=list[Tache])
    async def lister_taches(
        ident: str, courant: Courant, session: Session
    ) -> list[dict[str, Any]]:
        await charger_visible(session, ident, courant)
        return [
            _tache_resume(t) for t in await tache_repo.lister(session, ident, moi=courant["id"])
        ]

    @routeur.post(
        "/{ident}/taches", response_model=ActiviteDetail, status_code=status.HTTP_201_CREATED
    )
    async def creer_tache_activite(
        ident: str, corps: TacheCreation, courant: CourantActeur, session: Session
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
        return await detail_complet(r, session, courant)

    @routeur.patch("/{ident}/taches/{tache_id}", response_model=ActiviteDetail)
    async def maj_tache_activite(
        ident: str, tache_id: str, corps: TacheMaj, ctx: CtxTache, session: Session
    ) -> dict[str, Any]:
        """Les acteurs modifient tout ; l'assigné de cette tâche n'en change que le statut."""
        courant = ctx.courant
        tache = await _charger_tache(session, ident, tache_id, courant)
        champs = corps.model_dump(exclude_unset=True)
        exiger_champs_tache(ctx.roles, tache, courant, champs)
        await _verifier_agent(session, champs.get("assigne_id"))
        if champs.get("titre") is not None:
            champs["titre"] = phrase_propre(champs["titre"])
        await maj_tache(session, dict(tache), module, champs, courant)
        await session.commit()
        r = await charger_visible(session, ident, courant)
        return await detail_complet(r, session, courant)

    @routeur.delete("/{ident}/taches/{tache_id}", response_model=ActiviteDetail)
    async def supprimer_tache_activite(
        ident: str, tache_id: str, courant: CourantActeur, session: Session
    ) -> dict[str, Any]:
        tache = await _charger_tache(session, ident, tache_id, courant)
        await supprimer_tache(session, dict(tache), module, courant)
        await session.commit()
        r = await charger_visible(session, ident, courant)
        return await detail_complet(r, session, courant)

    @routeur.patch("/{ident}/taches", response_model=ActiviteDetail)
    async def reordonner_taches_activite(
        ident: str, corps: ReordreTaches, courant: CourantActeur, session: Session
    ) -> dict[str, Any]:
        await charger_visible(session, ident, courant)
        await tache_repo.reordonner(session, ident, corps.ordre)
        await session.commit()
        r = await charger_visible(session, ident, courant)
        return await detail_complet(r, session, courant)
