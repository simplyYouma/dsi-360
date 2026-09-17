"""Module EOD : les soirées de fin de journée du core banking.

Un routeur dédié, et non la fabrique commune (`activites_communs.creer_routeur`), pour la même
raison que les projets et les changements en ont un : la soirée porte un objet propre — son
**déroulé pointé**, vingt-huit étapes horodatées — que le socle générique ne connaît pas. Tout ce
qui est commun (discussion, pièces jointes, journal d'audit, notifications, SLA) reste mutualisé.

Deux partis pris, qui se voient dans les routes :

* **Ouvrir une soirée ne demande qu'une date.** Titre, référence, priorité et déroulé sont déduits.
  Un formulaire de plus, à 20 h, pendant que le core banking attend, ne serait pas rempli.
* **Qui ouvre la soirée la conduit.** Sans gestionnaire désigné, l'ouvrant devient responsable :
  sinon personne n'aurait le droit de pointer la première étape avant qu'un administrateur ne
  passe — au milieu de la nuit.
"""

import json
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.activites import (
    ActiviteIntrouvable,
    TransitionInterdite,
    supprimer_activite,
    transition,
)
from dsi360.application.autorisations import ACTEUR, capacites, charger_roles
from dsi360.application.eod import (
    HeureIllisible,
    IncidentIncomplet,
    JourneeDejaOuverte,
    cloture_conseillee,
    justification_manquante,
    ouvrir_journee,
    pointage,
    preparer_observation,
    preparer_relance,
    rafraichir_avancement,
)
from dsi360.domain.eod import ANOMALIE_OBS, INCIDENT, MODULE, ordre_section
from dsi360.domain.etats import est_etat_terminal, est_termine, transitions_possibles
from dsi360.domain.sla import statut_sla
from dsi360.domain.texte import phrase_propre
from dsi360.infrastructure import audit
from dsi360.infrastructure.db import session_scope
from dsi360.infrastructure.export import vers_csv, vers_xlsx
from dsi360.infrastructure.repositories import activite as repo
from dsi360.infrastructure.repositories import eod as eod_repo
from dsi360.interface.routeurs.activites_communs import (
    colonnes_export,
    horodate_export,
    valeurs_export,
)
from dsi360.interface.schemas import (
    CreationReponse,
    EodCreation,
    EodDetail,
    EtapeEod,
    EtapeEodCreation,
    EtapeEodMaj,
    EtapeModeleEod,
    ObservationEodCreation,
    PageEod,
    PointageEod,
    StatsListe,
    TransitionDemande,
)
from dsi360.interface.securite import (
    exiger_acces,
    exiger_admin,
    exiger_agent_designable,
    exiger_role_activite_courant,
)

_ACCES = "eod"
_TAILLE = 15

routeur = APIRouter(prefix="/eod", tags=["eod"])
Session = Annotated[AsyncSession, Depends(session_scope)]
Courant = Annotated[dict[str, Any], Depends(exiger_acces(_ACCES))]
#: Pointer, corriger, clore : le gestionnaire de la soirée, ses contributeurs, l'administrateur.
Acteur = Annotated[dict[str, Any], Depends(exiger_role_activite_courant(MODULE, _ACCES, {ACTEUR}))]


def _donnees(r: RowMapping) -> dict[str, Any]:
    valeur = r["donnees"]
    if isinstance(valeur, str):
        valeur = json.loads(valeur)
    return dict(valeur) if isinstance(valeur, dict) else {}


def _heure(valeur: datetime | None) -> str:
    """« 20H29 » — la notation du rapport de la banque, pas un horodatage ISO."""
    return "" if valeur is None else valeur.astimezone().strftime("%HH%M")


def _ligne_journal(o: RowMapping | dict[str, Any]) -> str:
    """Une observation, telle qu'elle se lit dans la colonne « Observations » du rapport.

    L'incident d'agence sort en tête avec l'heure de relance et l'agence — les deux questions que
    la hiérarchie pose en premier quand une nuit a dérapé. Une note ordinaire se contente de
    l'heure à laquelle elle a été consignée.
    """
    if o["nature"] == INCIDENT:
        return f"{_heure(o['relance_le'])} · {o['agence']} — {o['texte']}"
    if o["nature"] == ANOMALIE_OBS:
        # Le mot en tête : dans une colonne qui mêle notes et anomalies, c'est lui qu'on cherche.
        return f"{_heure(o['cree_le'])} · ANOMALIE — {o['texte']}"
    return f"{_heure(o['cree_le'])} — {o['texte']}"


def _responsable(r: RowMapping) -> dict[str, str] | None:
    if r["resp_email"] is None:
        return None
    return {"prenom": r["resp_prenom"], "nom": r["resp_nom"], "email": r["resp_email"]}


def _resume(r: RowMapping, maintenant: datetime) -> dict[str, Any]:
    d = _donnees(r)
    return {
        "id": r["id"],
        "reference": r["reference"],
        "titre": r["titre"],
        "journee": d.get("journee"),
        "statut": r["statut"],
        "categorie": r["categorie"],
        "categorie_id": r["categorie_id"],
        "responsable": _responsable(r),
        "responsable_id": r["resp_id"],
        "priorite": r["priorite"],
        "sla_resolution_le": r["sla_resolution_le"],
        "statut_sla": _statut_sla(r, maintenant),
        "avancement": int(d.get("avancement", 0)),
        "cree_le": r["cree_le"],
        "nb_commentaires": r["nb_commentaires"],
        "nb_non_vus": r["nb_non_vus"],
    }


#: Fenêtre d'alerte avant l'échéance. Une heure, et non deux comme ailleurs : une soirée se joue
#: sur quelques heures — prévenir deux heures avant reviendrait à prévenir dès le début.
_FENETRE_APPROCHE = timedelta(hours=1)


def _statut_sla(r: RowMapping, maintenant: datetime) -> str:
    """Situation du délai, ou « terminé » quand la soirée est close : le compteur ne court plus."""
    if est_termine(MODULE, r["statut"]):
        return "termine"
    if r["sla_resolution_le"] is None:
        return "a_lheure"
    return statut_sla(r["sla_resolution_le"], maintenant, _FENETRE_APPROCHE)


def _etape(
    ligne: RowMapping, journal: dict[str, list[dict[str, Any]]] | None = None
) -> dict[str, Any]:
    etape: dict[str, Any] = dict(ligne)
    etape["observations"] = (journal or {}).get(str(ligne["id"]), [])
    return etape


async def _journal(session: AsyncSession, activite_id: str) -> dict[str, list[dict[str, Any]]]:
    """Le journal de la soirée, rangé par étape.

    Une seule requête pour les vingt-huit étapes : aller chercher les observations étape par étape
    ferait vingt-huit allers-retours pour ouvrir un écran que l'opérateur rouvre toute la nuit.
    """
    par_etape: dict[str, list[dict[str, Any]]] = {}
    for o in await eod_repo.observations(session, activite_id):
        par_etape.setdefault(str(o["etape_id"]), []).append(dict(o))
    return par_etape


async def _charger(session: AsyncSession, ident: str, courant: dict[str, Any]) -> RowMapping:
    r = await repo.par_id(session, MODULE, ident, moi=courant["id"])
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Soirée introuvable.")
    if not courant["transverse"] and r["direction"] is not None:
        if r["direction"] != courant["direction"]:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Soirée introuvable.")
    return r


async def _detail_complet(
    session: AsyncSession, r: RowMapping, courant: dict[str, Any]
) -> dict[str, Any]:
    """Détail, déroulé, et ce que l'appelant a le droit d'y faire.

    Le serveur calcule, l'écran obéit : les permissions et la clôture conseillée sont décidées
    ici, jamais rejouées côté navigateur.
    """
    maintenant = datetime.now(UTC)
    journal = await _journal(session, str(r["id"]))
    etapes = [_etape(e, journal) for e in await eod_repo.lister(session, str(r["id"]))]
    statuts = [str(e["statut"]) for e in etapes]
    agregat = await eod_repo.agregats(session, [str(r["id"])])
    mesures = agregat.get(
        str(r["id"]),
        {
            "nb_etapes": 0,
            "reste": 0,
            "anomalies": 0,
            "incidents": 0,
            "debut_effectif": None,
            "fin_effective": None,
        },
    )
    clos = est_etat_terminal(MODULE, r["statut"])
    return {
        **_resume(r, maintenant),
        **mesures,
        "description": r["description"],
        "etapes": etapes,
        "transitions_possibles": transitions_possibles(MODULE, r["statut"]),
        "cloture_conseillee": cloture_conseillee(statuts, int(mesures["anomalies"])),
        "permissions": capacites(await charger_roles(session, r, courant), clos=clos),
    }


# --- Déroulé de référence -------------------------------------------------------------------


@routeur.get("/modele", response_model=list[EtapeModeleEod])
async def lister_modele(_courant: Courant, session: Session) -> list[dict[str, Any]]:
    """Le déroulé que chaque soirée reçoit à son ouverture."""
    return [dict(m) for m in await eod_repo.lister_modele(session, actifs_seuls=False)]


@routeur.get("/agences", response_model=list[str])
async def lister_agences(_courant: Courant, session: Session) -> list[str]:
    """Le réseau d'agences, proposé à la saisie d'un incident.

    Servi par le module EOD et non par l'inventaire, bien que la liste soit la même : l'opérateur
    de garde n'a pas nécessairement accès au parc, et lui refuser la liste des agences à 1 h du
    matin pour une question de droits sur un autre module serait absurde.
    """
    return await eod_repo.agences(session)


@routeur.get("/stats", response_model=StatsListe)
async def stats(courant: Courant, session: Session) -> dict[str, int]:
    direction = None if courant["transverse"] else courant["direction"]
    return await repo.compter_etats(session, MODULE, direction=direction)


# --- Les soirées ------------------------------------------------------------------------------


@routeur.get("", response_model=PageEod)
async def lister(
    courant: Courant,
    session: Session,
    page: Annotated[int, Query(ge=1)] = 1,
    statut: Annotated[str | None, Query()] = None,
    responsable_id: Annotated[str | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=80)] = None,
    etat: Annotated[str | None, Query()] = None,
    retard: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    direction = None if courant["transverse"] else courant["direction"]
    lignes, total = await repo.lister(
        session,
        MODULE,
        direction=direction,
        statut=statut,
        page=page,
        taille=_TAILLE,
        responsable_id=responsable_id,
        q=q,
        etat=etat,
        retard=retard,
        moi=courant["id"],
    )
    maintenant = datetime.now(UTC)
    mesures = await eod_repo.agregats(session, [str(r["id"]) for r in lignes])
    elements = []
    for r in lignes:
        resume = _resume(r, maintenant)
        resume.update(mesures.get(str(r["id"]), {}))
        elements.append(resume)
    return {"elements": elements, "total": total, "page": page, "taille": _TAILLE}


@routeur.post("", response_model=CreationReponse, status_code=status.HTTP_201_CREATED)
async def ouvrir(corps: EodCreation, courant: Courant, session: Session) -> dict[str, str]:
    """Ouvre la soirée d'une date et y pose le déroulé de référence.

    Désigner quelqu'un d'autre que soi reste le geste de l'administrateur : distribuer le travail
    ne s'improvise pas. Mais *prendre* la soirée qu'on ouvre, si — c'est ce que fait l'opérateur
    de garde, et le lui refuser bloquerait la nuit.
    """
    if corps.responsable_id is not None and corps.responsable_id != courant["id"]:
        exiger_admin(courant)
        await exiger_agent_designable(session, corps.responsable_id, _ACCES)
    try:
        ident, reference, poses = await ouvrir_journee(
            session,
            journee=corps.journee,
            categorie_id=corps.categorie_id,
            # Aucune direction : la soirée est celle de la banque, pas d'un service. Une activité
            # sans direction reste visible de tous (cf. `_visible`), ce qui est exactement le but —
            # l'EOD se lit du support à la Direction Générale.
            direction_id=None,
            responsable_id=corps.responsable_id or courant["id"],
            impact=corps.impact,
            urgence=corps.urgence,
            acteur=courant,
        )
    except JourneeDejaOuverte as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La soirée {exc.reference} couvre déjà cette journée.",
        ) from exc
    if poses == 0:
        # Le déroulé de référence est vide : la soirée existe mais n'a rien à pointer. Le dire
        # ici évite de chercher du côté de l'écran ce qui manque en base (migration non jouée).
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"La soirée {reference} est ouverte, mais le déroulé de référence est vide : "
                "aucune étape à pointer. Vérifiez core.eod_modele_etape."
            ),
        )
    return {"id": ident}


#: Ce que l'export ajoute au socle commun : ce qui ne se lit que sur une soirée.
_COLONNES_EOD: tuple[tuple[str, str], ...] = (
    ("Journée comptable", "journee"),
    ("Étapes", "nb_etapes"),
    ("Anomalies", "anomalies"),
    # Distincte des anomalies, et pas déductible d'elles : une agence peut être relancée sans que
    # l'étape finisse en anomalie, et une anomalie de batch ne touche parfois aucune agence.
    # C'est la colonne qui répond à « quelles agences nous coûtent nos nuits ».
    ("Relances d'agence", "incidents"),
    ("Début effectif", "debut_effectif"),
    ("Fin effective", "fin_effective"),
)


@routeur.get("/export")
async def exporter(
    courant: Courant,
    session: Session,
    format: Annotated[str, Query(alias="format")] = "csv",
) -> Response:
    """Toutes les soirées, pour les comparer entre elles.

    C'est ce fichier qui répond aux questions qu'on ne pouvait pas poser au tableau Word : combien
    de nuits ont porté des réserves ce trimestre, à quelle heure la banque rouvre en moyenne,
    quelles soirées ont dépassé leur délai.
    """
    direction = None if courant["transverse"] else courant["direction"]
    lignes = await repo.lister_tout(session, MODULE, direction=direction)
    maintenant = datetime.now(UTC)
    fins = await audit.dernieres_transitions(session, MODULE)
    mesures = await eod_repo.agregats(session, [str(r["id"]) for r in lignes])
    colonnes = [
        *colonnes_export(
            MODULE,
            import_uniquement=False,
            avec_taches=False,
            avec_revue=False,
            avec_avancement_manuel=True,
            # Une soirée ne se commente pas : la colonne vaudrait 0 sur toutes les lignes.
            avec_discussion=False,
        ),
        *_COLONNES_EOD,
    ]
    entetes = [entete for entete, _ in colonnes]
    donnees: list[list[Any]] = []
    for r in lignes:
        mesure = mesures.get(str(r["id"]), {})
        valeurs = valeurs_export(r, maintenant, False, fins.get(r["reference"]))
        valeurs |= {
            "journee": horodate_export(_donnees(r).get("journee")),
            "nb_etapes": mesure.get("nb_etapes", 0),
            "anomalies": mesure.get("anomalies", 0),
            "incidents": mesure.get("incidents", 0),
            "debut_effectif": horodate_export(mesure.get("debut_effectif")),
            "fin_effective": horodate_export(mesure.get("fin_effective")),
        }
        donnees.append([valeurs.get(cle, "") for _, cle in colonnes])
    if format == "xlsx":
        return Response(
            content=vers_xlsx(entetes, donnees, "soirees-eod"),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=eod-export.xlsx"},
        )
    return Response(
        content=vers_csv(entetes, donnees),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=eod-export.csv"},
    )


@routeur.delete("/{ident}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer_soiree(ident: str, courant: Courant, session: Session) -> None:
    """Suppression définitive d'une soirée, réservée à l'administrateur.

    Une nuit ouverte sur la mauvaise date bloque la bonne — l'unicité porte sur la journée
    comptable — et la corriger n'est pas possible : c'est elle qui fait l'identité de la soirée.
    Sans ce geste, il fallait vivre avec une soirée fantôme dans les statistiques. Ce qu'elle
    contenait passe au journal d'audit avant de disparaître.
    """
    exiger_admin(courant)
    r = await _charger(session, ident, courant)
    await supprimer_activite(session, dict(r), MODULE, courant)
    await session.commit()


@routeur.get("/{ident}", response_model=EodDetail)
async def detail(ident: str, courant: Courant, session: Session) -> dict[str, Any]:
    return await _detail_complet(session, await _charger(session, ident, courant), courant)


@routeur.post("/{ident}/transition", response_model=EodDetail)
async def transitionner(
    ident: str, corps: TransitionDemande, courant: Acteur, session: Session
) -> dict[str, Any]:
    """Fait avancer la soirée. Clore une nuit inachevée demande de dire pourquoi.

    Le serveur ne s'oppose pas à une clôture anticipée : une soirée peut être arrêtée pour de
    bonnes raisons, et un refus laisserait la nuit ouverte indéfiniment dans les listes. Mais il
    exige alors la note — sans elle, les étapes restées « À faire » ne se relisent pas.
    """
    await _charger(session, ident, courant)
    statuts = await eod_repo.statuts(session, ident)
    anomalies = int((await eod_repo.agregats(session, [ident])).get(ident, {}).get("anomalies", 0))
    inachevee = cloture_conseillee(statuts, anomalies) is None
    cloture = corps.vers in {"Clôturé", "Clôturé avec réserves", "Annulé"}
    if cloture and inachevee and not (corps.note or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Des étapes ne sont pas réglées : une note est requise pour clore "
                f"la soirée en « {corps.vers} »."
            ),
        )
    try:
        await transition(session, MODULE, ident, corps.vers, courant)
    except ActiviteIntrouvable as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Introuvable.") from exc
    except TransitionInterdite as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"Transition interdite : {exc}"
        ) from exc
    if (corps.note or "").strip():
        await session.execute(
            text(
                "INSERT INTO core.note (activite_id, texte, contexte, auteur_email) "
                "VALUES (cast(:aid as uuid), :texte, :ctx, :email)"
            ),
            {
                "aid": ident,
                "texte": (corps.note or "").strip(),
                "ctx": corps.vers,
                "email": courant["email"],
            },
        )
        await session.commit()
    return await _detail_complet(session, await _charger(session, ident, courant), courant)


# --- Le déroulé pointé ------------------------------------------------------------------------


@routeur.get("/{ident}/etapes", response_model=list[EtapeEod])
async def lister_etapes(ident: str, courant: Courant, session: Session) -> list[dict[str, Any]]:
    await _charger(session, ident, courant)
    journal = await _journal(session, ident)
    return [_etape(e, journal) for e in await eod_repo.lister(session, ident)]


@routeur.post("/{ident}/etapes", response_model=EodDetail, status_code=status.HTTP_201_CREATED)
async def ajouter_etape(
    ident: str, corps: EtapeEodCreation, courant: Acteur, session: Session
) -> dict[str, Any]:
    """Ajoute une étape à cette soirée seulement — une vérification exceptionnelle, un rattrapage.

    Elle n'entre pas dans le déroulé de référence : ce qui se fait une fois ne doit pas réapparaître
    tous les soirs. Faire entrer une étape dans le quotidien est une décision, prise ailleurs.
    """
    await _charger(session, ident, courant)
    ligne = await eod_repo.creer(
        session,
        ident,
        {
            "section": phrase_propre(corps.section) or corps.section,
            "libelle": corps.libelle.strip(),
            "nature": corps.nature,
        },
    )
    await audit.consigner(
        session,
        action="CREATION",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module=MODULE,
        cible_type="eod_etape",
        cible_id=str(ligne["id"]),
        nouvelle={"section": ligne["section"], "libelle": ligne["libelle"]},
    )
    await rafraichir_avancement(session, ident)
    return await _detail_complet(session, await _charger(session, ident, courant), courant)


@routeur.patch("/{ident}/etapes/{etape_id}", response_model=EodDetail)
async def modifier_etape(
    ident: str, etape_id: str, corps: EtapeEodMaj, courant: Acteur, session: Session
) -> dict[str, Any]:
    """Corrige une étape : son verdict, ses heures, ce qu'on y a lu.

    Une anomalie ou un « non applicable » sans explication est refusé : six semaines plus tard,
    personne ne saura ce qui a coincé ce soir-là — et c'est précisément ce qu'on vient chercher
    dans l'historique. L'explication est une **observation** — une ligne de journal signée et
    horodatée — et elle peut venir dans le même appel que le verdict : la demander dans un second
    temps ferait échouer le premier geste pour une raison découverte après coup.
    """
    await _charger(session, ident, courant)
    avant = await eod_repo.par_id(session, etape_id, ident)
    if avant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Étape introuvable.")

    champs = corps.model_dump(exclude_unset=True)
    for hors_colonne in ("vider_debut", "vider_fin", "observation"):
        champs.pop(hors_colonne, None)
    if corps.vider_debut:
        champs["debut"] = None
    if corps.vider_fin:
        champs["fin"] = None

    # On vérifie AVANT d'écrire : refuser le verdict après avoir consigné l'observation laisserait
    # au journal une ligne qui explique une décision qui n'a pas eu lieu.
    statut = champs.get("statut", avant["statut"])
    au_journal = await eod_repo.compter_observations(session, etape_id)
    if justification_manquante(str(statut), au_journal + (1 if corps.observation else 0)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"« {statut} » demande une explication : consignez une observation.",
        )
    if corps.observation is not None:
        await _consigner(session, ident, etape_id, corps.observation, courant)
    if not champs:
        return await _detail_complet(session, await _charger(session, ident, courant), courant)

    await eod_repo.maj(session, etape_id, champs)
    await audit.consigner(
        session,
        action="MODIFICATION",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module=MODULE,
        cible_type="eod_etape",
        cible_id=etape_id,
        ancienne={"statut": avant["statut"]},
        nouvelle={k: str(v) for k, v in champs.items()},
    )
    await rafraichir_avancement(session, ident)
    return await _detail_complet(session, await _charger(session, ident, courant), courant)


# --- Le journal d'une étape -------------------------------------------------------------------
#
# Append-only, sans route de modification ni de suppression. Une observation qui se corrige après
# coup ne prouve plus rien — et c'est bien une preuve qu'on vient chercher au matin. L'erreur se
# rattrape par l'observation suivante, qui la date et la signe (principe n° 4).


async def _consigner(
    session: AsyncSession,
    ident: str,
    etape_id: str,
    corps: ObservationEodCreation,
    acteur: dict[str, Any],
) -> dict[str, Any]:
    """Écrit une ligne au journal d'une étape, heure de relance résolue, et la journalise.

    Les deux refus possibles disent ce qui manque plutôt que « requête invalide » : à 1 h du matin,
    un message qui n'indique pas le champ fautif coûte un appel au support.
    """
    try:
        champs = preparer_observation(
            nature=corps.nature,
            agence=corps.agence,
            relance=corps.relance,
            texte=corps.texte,
            acteur=acteur,
            maintenant=datetime.now(UTC),
        )
    except HeureIllisible as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"L'heure de relance « {exc.saisie} » ne se lit pas. "
                "Attendu : 01H12, 01:12 ou 0112."
            ),
        ) from exc
    except IncidentIncomplet as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Un incident d'agence doit préciser {exc.manque}.",
        ) from exc

    ligne = await eod_repo.creer_observation(
        session, etape_id=etape_id, activite_id=ident, champs=champs
    )
    await audit.consigner(
        session,
        action="CREATION",
        acteur_id=acteur["id"],
        acteur_email=acteur["email"],
        module=MODULE,
        cible_type="eod_observation",
        cible_id=str(ligne["id"]),
        nouvelle={
            "etape": etape_id,
            "nature": str(ligne["nature"]),
            "agence": ligne["agence"] or "",
            "relance": _heure(ligne["relance_le"]),
            "texte": str(ligne["texte"]),
        },
    )
    # Un incident d'agence, c'est une relance : elle prend sa place dans le déroulé, juste sous
    # l'étape qu'elle rejoue, En cours depuis l'heure consignée. C'est la ligne « RELANCE » du
    # rapport de la banque — avec un début, une fin et un verdict, comme toute étape.
    if str(ligne["nature"]) == INCIDENT:
        parent = await eod_repo.par_id(session, etape_id, ident)
        if parent is not None:
            relance = await eod_repo.creer(
                session, ident, preparer_relance(dict(parent), dict(ligne))
            )
            await audit.consigner(
                session,
                action="CREATION",
                acteur_id=acteur["id"],
                acteur_email=acteur["email"],
                module=MODULE,
                cible_type="eod_etape",
                cible_id=str(relance["id"]),
                nouvelle={
                    "section": str(relance["section"]),
                    "libelle": str(relance["libelle"]),
                    "relance_de": etape_id,
                },
            )
    return dict(ligne)


@routeur.post(
    "/{ident}/etapes/{etape_id}/observations",
    response_model=EodDetail,
    status_code=status.HTTP_201_CREATED,
)
async def ajouter_observation(
    ident: str,
    etape_id: str,
    corps: ObservationEodCreation,
    courant: Acteur,
    session: Session,
) -> dict[str, Any]:
    """Consigne ce qui vient de se passer sur une étape, et sur quelle agence s'il y a incident.

    C'est le geste qui manquait. Sur « PART 3 — EOD till Post MARKBOD for all branches », une
    agence bloque à 01H12, on relance ; une autre bloque à 01H40, on relance encore. Chaque relance
    est une ligne : l'agence, l'heure, ce qui a été fait. Le champ unique d'avant gardait la
    dernière phrase tapée et effaçait les précédentes — au matin, il ne restait rien à relire.
    """
    await _charger(session, ident, courant)
    if await eod_repo.par_id(session, etape_id, ident) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Étape introuvable.")
    await _consigner(session, ident, etape_id, corps, courant)
    return await _detail_complet(session, await _charger(session, ident, courant), courant)


@routeur.post("/{ident}/etapes/{etape_id}/pointer", response_model=EodDetail)
async def pointer_etape(
    ident: str, etape_id: str, corps: PointageEod, courant: Acteur, session: Session
) -> dict[str, Any]:
    """« Démarrer » / « Terminer » : la plateforme pose l'heure, l'opérateur ne la tape pas.

    C'est le geste de la nuit. Une heure retapée de mémoire une heure plus tard est une heure
    fausse — et c'est le principal défaut du tableau que cet écran remplace.
    """
    await _charger(session, ident, courant)
    avant = await eod_repo.par_id(session, etape_id, ident)
    if avant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Étape introuvable.")
    fixes = pointage(corps.quoi, dict(avant), datetime.now(UTC))
    await eod_repo.maj(session, etape_id, fixes)
    await audit.consigner(
        session,
        action="MODIFICATION",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module=MODULE,
        cible_type="eod_etape",
        cible_id=etape_id,
        ancienne={"statut": avant["statut"]},
        # Terminer une étape en anomalie ne touche pas à son verdict : `fixes` ne porte alors pas
        # de statut, et c'est celui d'avant qui reste vrai.
        nouvelle={"pointage": corps.quoi, "statut": fixes.get("statut", avant["statut"])},
    )
    await rafraichir_avancement(session, ident)
    return await _detail_complet(session, await _charger(session, ident, courant), courant)


@routeur.delete("/{ident}/etapes/{etape_id}", response_model=EodDetail)
async def supprimer_etape(
    ident: str, etape_id: str, courant: Acteur, session: Session
) -> dict[str, Any]:
    await _charger(session, ident, courant)
    avant = await eod_repo.par_id(session, etape_id, ident)
    if avant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Étape introuvable.")
    await eod_repo.supprimer(session, etape_id)
    await audit.consigner(
        session,
        action="SUPPRESSION",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module=MODULE,
        cible_type="eod_etape",
        cible_id=etape_id,
        ancienne={"section": avant["section"], "libelle": avant["libelle"]},
    )
    await rafraichir_avancement(session, ident)
    return await _detail_complet(session, await _charger(session, ident, courant), courant)


# --- Le rapport du soir -----------------------------------------------------------------------

#: Les quatre colonnes de leur tableau — et pas une de plus. La section n'est pas une colonne :
#: c'est un bandeau qui coupe la liste (cf. `_lignes_rapport`).
_ENTETES_RAPPORT = ["Étape", "Début", "Fin", "Statut / Observations"]


def _lignes_rapport(
    etapes: list[RowMapping], journal: dict[str, list[dict[str, Any]]]
) -> tuple[list[list[Any]], set[int]]:
    """Les lignes du rapport dans la forme où la hiérarchie le lit depuis toujours.

    Un bandeau par section (PART 1, PART 2…) sur toute la largeur, puis ses étapes. La dernière
    colonne dit le verdict — ou, quand il y a quelque chose à dire, le journal à la place : sur
    « Post EOFI_1 », c'est « Branch 018 Error code:AE-VALS-053 » qu'on lit, pas « Anomalie ».
    Rend aussi les rangs des bandeaux, pour que le classeur les fusionne et les teinte.
    """
    lignes: list[list[Any]] = []
    bandeaux: set[int] = set()
    section_courante: str | None = None
    for e in sorted(etapes, key=lambda x: (ordre_section(str(x["section"])), int(x["ordre"]))):
        if e["section"] != section_courante:
            section_courante = str(e["section"])
            bandeaux.add(len(lignes))
            lignes.append([section_courante, "", "", ""])
        if e["nature"] == "valeur":
            debut, fin = (e["valeur"] or ""), ""
        else:
            debut, fin = _heure(e["debut"]), _heure(e["fin"])
        # Le journal entier, une ligne par observation : c'est lui le compte rendu de la nuit.
        # N'en garder que la dernière — ce que faisait l'ancien champ de notes — effacerait les
        # relances successives, c'est-à-dire précisément ce que la hiérarchie vient lire.
        consigne = "\n".join(_ligne_journal(o) for o in journal.get(str(e["id"]), []))
        verdict = "" if e["statut"] == "À faire" else str(e["statut"])
        lignes.append([e["libelle"], debut, fin, consigne or verdict])
    return lignes, bandeaux


@routeur.get("/{ident}/rapport")
async def rapport(
    ident: str,
    courant: Courant,
    session: Session,
    format: Annotated[str, Query(alias="format")] = "xlsx",
) -> Response:
    """Le rapport du soir, dans la forme où la hiérarchie le lit depuis toujours.

    Tant que ce tableau se retapait à la main chaque nuit, il se trompait d'heures et sautait des
    lignes. Il est maintenant produit à partir de ce qui a été pointé : reprendre exactement sa
    mise en forme est ce qui permet de basculer sans rien changer aux habitudes de lecture.
    """
    r = await _charger(session, ident, courant)
    etapes = await eod_repo.lister(session, ident)
    journal = await _journal(session, ident)
    lignes, bandeaux = _lignes_rapport(etapes, journal)

    d = _donnees(r)
    nom = f"eod-{d.get('journee') or r['reference']}"
    # Nom d'onglet : un classeur refuse « / » (et « \ ? * [ ] »), or le titre d'une soirée porte
    # une date à la française. On garde la date, en la réécrivant avec des tirets.
    onglet = f"EOD {str(d.get('journee') or r['reference']).replace('/', '-')}"
    if format == "csv":
        return Response(
            content=vers_csv(_ENTETES_RAPPORT, lignes),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={nom}.csv"},
        )
    return Response(
        # `retour_ligne` : une étape qui a vu trois agences bloquer porte trois lignes dans sa
        # cellule. Sans habillage, Excel les afficherait bout à bout, tronquées à la première.
        content=vers_xlsx(_ENTETES_RAPPORT, lignes, onglet, retour_ligne=True, bandeaux=bandeaux),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={nom}.xlsx"},
    )
