"""Module Applications : l'inventaire applicatif (le patrimoine logiciel).

Une application n'est pas une activité : ni workflow, ni SLA, ni valideur. Ce routeur est donc
autonome, sans passer par la fabrique `activites_communs` — exactement comme l'inventaire matériel.

Ce que le module cherche à rendre visible, au-delà de la liste : de qui l'on dépend (éditeurs),
ce qui sort de nos murs (hébergement), et surtout ce dont plus personne ne répond (sans
administrateur, sans relais). Un inventaire applicatif ne vaut que par ces trous-là.
"""

import re
from collections import Counter
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.applications import (
    creer_application,
    maj_application,
    nom_normalise,
    supprimer_application,
)
from dsi360.infrastructure.db import session_scope
from dsi360.infrastructure.export import vers_csv, vers_xlsx
from dsi360.infrastructure.repositories import application as repo
from dsi360.interface.schemas import (
    AnalysesApplications,
    ApplicationCreation,
    ApplicationDetail,
    ApplicationMaj,
    PageApplications,
    ReferentielCreation,
    ReferentielItem,
    StatsApplications,
)
from dsi360.interface.securite import exiger_acces, exiger_admin

_ACCES = "applications"
_TAILLE = 15

routeur = APIRouter(prefix="/applications", tags=["applications"])
Session = Annotated[AsyncSession, Depends(session_scope)]
Courant = Annotated[dict[str, Any], Depends(exiger_acces(_ACCES))]

_UUID_BRUT = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

#: Nom d'écran des valeurs codées. La base garde un code stable, l'écran lit du français.
LIBELLE_HEBERGEMENT = {"INTERNE": "Interne (nos serveurs)", "EXTERNE": "Externe (tiers)"}
LIBELLE_STATUT = {"EN_SERVICE": "En service", "EN_PROJET": "En projet", "ARRETE": "Arrêtée"}


def _liste_noms(brut: Any) -> str:
    """« Awa Touré · Mady Wague » — plusieurs personnes tiennent dans une cellule de tableur."""
    return " · ".join(str(p.get("nom") or "") for p in repo.responsables(brut) if p.get("nom"))


def _resume(r: RowMapping) -> dict[str, Any]:
    return {
        "id": r["id"],
        "reference": r["reference"],
        "nom": r["nom"],
        "processus_metier": r["processus_metier"],
        "version": r["version"],
        "editeur": r["editeur"],
        "hebergement": r["hebergement"],
        "interfacage": r["interfacage"],
        "statut": r["statut"],
        "administrateurs": repo.responsables(r["administrateurs"]),
        "administrateurs_secours": repo.responsables(r["administrateurs_secours"]),
        "nb_comptes_actifs": r["nb_comptes_actifs"],
        "actif": r["actif"],
    }


async def _detail(session: AsyncSession, r: RowMapping) -> dict[str, Any]:
    return {
        "historique": await _historique(session, r),
        **_resume(r),
        "fonctionnalites": r["fonctionnalites"],
        "editeur_id": r["editeur_id"],
        "proprietaire": r["proprietaire"],
        "pays_donnees": r["pays_donnees"],
        "date_debut": r["date_debut"],
        "date_fin": r["date_fin"],
        "lien": r["lien"],
        "serveur_application": r["serveur_application"],
        "serveur_base": r["serveur_base"],
        "port": r["port"],
        "source": r["source"],
        "cree_le": r["cree_le"],
        "maj_le": r["maj_le"],
    }


# La fiche est journalisée sous son nom : on relit sous ce même repère.
_HISTORIQUE = text(
    "SELECT j.action, j.horodatage, j.acteur_email AS acteur, "
    "j.ancienne_valeur AS anciennes, j.nouvelle_valeur AS nouvelles FROM audit.journal j "
    "WHERE j.module = 'applications' AND j.cible_type = 'application' "
    "AND j.cible_id = :nom ORDER BY j.id DESC LIMIT 15"
)

#: Nom d'écran des champs journalisés — l'historique parle français, pas colonne SQL.
_LIBELLE_CHAMP = {
    "nom": "nom",
    "processus_metier": "processus métier",
    "fonctionnalites": "fonctionnalités",
    "version": "version",
    "editeur": "éditeur",
    "hebergement": "hébergement",
    "pays_donnees": "pays des données",
    "interfacage": "interfaçage",
    "statut": "statut",
    "proprietaire": "propriétaire",
    "date_debut": "date de début",
    "date_fin": "date de fin",
    "nb_comptes_actifs": "comptes actifs",
    "lien": "lien",
    "serveur_application": "serveur d'application",
    "serveur_base": "serveur de base de données",
    "port": "port",
    "administrateur": "administrateur",
    "administrateur_secours": "administrateur de secours",
    "actif": "en service",
}


def _valeur_lisible(valeur: Any, cle: str) -> str:
    if valeur is None or valeur == "":
        return "—"
    if isinstance(valeur, bool):
        return "oui" if valeur else "non"
    texte_brut = str(valeur)
    if _UUID_BRUT.fullmatch(texte_brut.lower()):
        return "…"
    if cle == "hebergement":
        return LIBELLE_HEBERGEMENT.get(texte_brut, texte_brut)
    if cle == "statut":
        return LIBELLE_STATUT.get(texte_brut, texte_brut)
    return texte_brut if len(texte_brut) <= 80 else texte_brut[:77] + "…"


def _texte_changement(anciennes: Any, nouvelles: Any) -> str | None:
    """« administrateur : Awa Touré → Mady Wague » — la reprise en main, lisible."""
    if not isinstance(nouvelles, dict):
        return None
    avant = anciennes if isinstance(anciennes, dict) else {}
    fragments: list[str] = []
    for cle, apres in nouvelles.items():
        libelle = _LIBELLE_CHAMP.get(cle, cle.replace("_", " "))
        avant_txt = _valeur_lisible(avant.get(cle), cle)
        apres_txt = _valeur_lisible(apres, cle)
        if avant_txt == apres_txt:
            continue
        fragments.append(
            f"{libelle} : {avant_txt} → {apres_txt}" if cle in avant else f"{libelle} : {apres_txt}"
        )
    return " · ".join(fragments) or None


async def _historique(session: AsyncSession, r: RowMapping) -> list[dict[str, Any]]:
    lignes = await session.execute(_HISTORIQUE, {"nom": r["nom"]})
    return [
        {
            "action": e["action"],
            "horodatage": e["horodatage"],
            "acteur": e["acteur"],
            "detail": _texte_changement(e["anciennes"], e["nouvelles"]),
        }
        for e in lignes.mappings().all()
    ]


async def _charger(session: AsyncSession, ident: str) -> RowMapping:
    r = await repo.par_id(session, ident)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application introuvable.")
    return r


async def _valider_responsables(session: AsyncSession, champs: dict[str, Any]) -> None:
    """Les comptes désignés doivent exister — le serveur fait foi, jamais la liste de l'écran."""
    demandes: list[str] = []
    for cle in ("administrateurs", "administrateurs_secours"):
        for personne in champs.get(cle) or []:
            ident = personne.get("utilisateur_id")
            if ident is None:
                continue
            if not _UUID_BRUT.fullmatch(str(ident).lower()):
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY, "Une personne désignée est invalide."
                )
            demandes.append(str(ident))
    if not demandes:
        return
    connus = await repo.comptes_existants(session, demandes)
    if set(demandes) - connus:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Une personne désignée n'a pas de compte."
        )


async def _valider_editeur(session: AsyncSession, champs: dict[str, Any]) -> None:
    """Un identifiant inconnu doit répondre 422 en clair, pas une erreur d'intégrité en 500."""
    ident = champs.get("editeur_id")
    if ident is None:
        return
    if not _UUID_BRUT.fullmatch(str(ident).lower()):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "L'éditeur indiqué est invalide.")
    existe = await session.scalar(
        text(f"SELECT 1 FROM {repo.TABLE_EDITEUR} WHERE id = cast(:id as uuid)"), {"id": ident}
    )
    if existe is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "L'éditeur indiqué n'existe pas."
        )


async def _refuser_nom_deja_pris(
    session: AsyncSession, nom: str | None, ident_courant: str | None
) -> None:
    """Le nom identifie l'application : deux fiches scinderaient son suivi en silence.

    On interroge sur le nom **normalisé**, celui qui sera réellement écrit : chercher la forme
    brute laisserait passer « generateur   de test » face à « generateur de test », et le doublon
    ressortirait en erreur d'intégrité plutôt qu'en message clair.
    """
    propre = nom_normalise(nom)
    if not propre:
        return
    existante = await repo.par_nom(session, propre)
    if existante is not None and existante["id"] != ident_courant:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"L'application « {propre} » figure déjà à l'inventaire.",
        )


@routeur.get("", response_model=PageApplications)
async def lister(
    courant: Courant,
    session: Session,
    page: Annotated[int, Query(ge=1)] = 1,
    q: Annotated[str | None, Query(max_length=80)] = None,
    editeur_id: Annotated[str | None, Query()] = None,
    hebergement: Annotated[str | None, Query()] = None,
    statut: Annotated[str | None, Query()] = None,
    interfacage: Annotated[str | None, Query()] = None,
    #: Un nom d'administrateur, ou `AUCUN` pour « personne ne s'en occupe ».
    administrateur: Annotated[str | None, Query(max_length=160)] = None,
    actif: Annotated[bool | None, Query()] = True,
) -> dict[str, Any]:
    lignes, total = await repo.lister(
        session,
        page=page,
        taille=_TAILLE,
        q=q,
        editeur_id=editeur_id,
        hebergement=hebergement,
        statut=statut,
        interfacage=interfacage,
        administrateur=administrateur,
        actif=actif,
    )
    return {
        "elements": [_resume(r) for r in lignes],
        "total": total,
        "page": page,
        "taille": _TAILLE,
    }


@routeur.get("/stats", response_model=StatsApplications)
async def stats(courant: Courant, session: Session) -> dict[str, int]:
    """Compteurs de l'en-tête : effectif, hébergement, et les applications sans responsable."""
    return await repo.compter(session)


def _agreger(libelles: list[str], plafond: int = 10) -> list[dict[str, Any]]:
    """Compte par libellé, trie, replie la queue dans « Autres ».

    Le repli est annoncé par son libellé : un graphique qui tait ce qu'il coupe ment.
    """
    tries: list[tuple[str, int]] = sorted(
        Counter(libelles).items(), key=lambda kv: (-kv[1], kv[0])
    )
    if len(tries) <= plafond:
        return [{"libelle": libelle, "nombre": nombre} for libelle, nombre in tries]
    tete, queue = tries[:plafond], tries[plafond:]
    return [
        *({"libelle": libelle, "nombre": nombre} for libelle, nombre in tete),
        {"libelle": f"Autres ({len(queue)})", "nombre": sum(n for _, n in queue)},
    ]


@routeur.get("/analyses", response_model=AnalysesApplications)
async def analyses_applications(courant: Courant, session: Session) -> dict[str, Any]:
    """Le patrimoine logiciel en chiffres : dépendances, hébergement, continuité.

    Tout se calcule sur les applications **en service** : ce qu'on a décommissionné ne dit plus
    rien de nos dépendances d'aujourd'hui.
    """
    actives = [r for r in await repo.lister_tout(session) if r["actif"]]
    return {
        "total": len(actives),
        "par_editeur": _agreger([r["editeur"] or "Éditeur non renseigné" for r in actives]),
        "par_hebergement": _agreger(
            [
                LIBELLE_HEBERGEMENT.get(r["hebergement"], "Non renseigné")
                if r["hebergement"]
                else "Non renseigné"
                for r in actives
            ]
        ),
        "par_statut": _agreger(
            [LIBELLE_STATUT.get(r["statut"], r["statut"]) for r in actives]
        ),
        # Qui porte quoi : la charge d'administration, et sa concentration sur quelques personnes.
        # Une application à deux administrateurs compte pour chacun d'eux : c'est bien une charge
        # portée par les deux.
        "par_administrateur": _agreger(
            [
                p["nom"]
                for r in actives
                for p in (
                    repo.responsables(r["administrateurs"]) or [{"nom": "Sans administrateur"}]
                )
                if p.get("nom")
            ]
        ),
        # Une application sans relais s'arrête avec la personne qui la tient. Ce n'est pas une
        # faute de saisie, c'est un risque de continuité — on le nomme.
        "sans_secours": _agreger(
            [r["nom"] for r in actives if not repo.responsables(r["administrateurs_secours"])],
            plafond=20,
        ),
    }


_ENTETES_EXPORT = [
    "Réf",
    "Application",
    "Processus métier",
    "Principales fonctionnalités",
    "Version",
    "Éditeur",
    "Hébergement",
    "Pays des données",
    "Interfaçage",
    "Statut",
    "Propriétaire",
    "Date de début",
    "Date de fin",
    "Comptes actifs",
    "Lien",
    "Serveur d'application",
    "Serveur de base de données",
    "Port",
    "Administrateur",
    "Administrateur de secours",
    "En service",
    "Origine",
    "Créée le",
    "Mise à jour le",
]


@routeur.get("/export")
async def exporter(
    courant: Courant,
    session: Session,
    format: Annotated[str, Query(alias="format")] = "csv",
) -> Response:
    """L'inventaire applicatif complet : toutes les colonnes tenues, pas seulement l'écran."""
    lignes = await repo.lister_tout(session)
    donnees = [
        [
            r["reference"],
            r["nom"],
            r["processus_metier"] or "",
            r["fonctionnalites"] or "",
            r["version"] or "",
            r["editeur"] or "",
            LIBELLE_HEBERGEMENT.get(r["hebergement"] or "", ""),
            r["pays_donnees"] or "",
            r["interfacage"] or "",
            LIBELLE_STATUT.get(r["statut"], r["statut"]),
            r["proprietaire"] or "",
            r["date_debut"].strftime("%d/%m/%Y") if r["date_debut"] else "",
            r["date_fin"].strftime("%d/%m/%Y") if r["date_fin"] else "",
            r["nb_comptes_actifs"] if r["nb_comptes_actifs"] is not None else "",
            r["lien"] or "",
            r["serveur_application"] or "",
            r["serveur_base"] or "",
            r["port"] or "",
            _liste_noms(r["administrateurs"]),
            _liste_noms(r["administrateurs_secours"]),
            "Oui" if r["actif"] else "Non",
            r["source"],
            r["cree_le"].strftime("%d/%m/%Y %H:%M"),
            r["maj_le"].strftime("%d/%m/%Y %H:%M"),
        ]
        for r in lignes
    ]
    if format == "xlsx":
        contenu = vers_xlsx(_ENTETES_EXPORT, donnees, "Applications")
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = "xlsx"
    else:
        contenu = vers_csv(_ENTETES_EXPORT, donnees)
        media = "text/csv"
        ext = "csv"
    return Response(
        content=contenu,
        media_type=media,
        headers={"Content-Disposition": f"attachment; filename=applications.{ext}"},
    )


@routeur.get("/{ident}", response_model=ApplicationDetail)
async def detail(ident: str, courant: Courant, session: Session) -> dict[str, Any]:
    return await _detail(session, await _charger(session, ident))


@routeur.post("", response_model=ApplicationDetail, status_code=status.HTTP_201_CREATED)
async def creer(corps: ApplicationCreation, courant: Courant, session: Session) -> dict[str, Any]:
    """Inscrire une application à l'inventaire — réservé à l'administrateur.

    Même partage des rôles que pour le parc matériel (ADR-0003), et le serveur fait foi : masquer
    le bouton à l'écran ne serait pas une barrière.
    """
    exiger_admin(courant)
    await _refuser_nom_deja_pris(session, corps.nom, None)
    champs = corps.model_dump(exclude_none=True)
    await _valider_editeur(session, champs)
    await _valider_responsables(session, champs)
    ident = await creer_application(session, champs, courant)
    await session.commit()
    return await _detail(session, await _charger(session, ident))


@routeur.patch("/{ident}", response_model=ApplicationDetail)
async def modifier(
    ident: str, corps: ApplicationMaj, courant: Courant, session: Session
) -> dict[str, Any]:
    exiger_admin(courant)
    avant = await _charger(session, ident)
    champs = corps.model_dump(exclude_unset=True)
    if "nom" in champs:
        await _refuser_nom_deja_pris(session, champs["nom"], ident)
    await _valider_editeur(session, champs)
    await _valider_responsables(session, champs)
    # `avant` porte les responsables au format d'affichage : le journal s'en sert pour dire
    # « qui c'était » avant de dire « qui c'est ».
    precedent: dict[str, Any] = dict(avant)
    precedent["administrateurs"] = repo.responsables(avant["administrateurs"])
    precedent["administrateurs_secours"] = repo.responsables(avant["administrateurs_secours"])
    await maj_application(session, precedent, champs, courant)
    await session.commit()
    return await _detail(session, await _charger(session, ident))


@routeur.delete("/{ident}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer(ident: str, courant: Courant, session: Session) -> None:
    """Suppression définitive, réservée à l'administrateur.

    Pour retirer une application du parc sans perdre son historique, on la passe plutôt à
    « hors service » (`actif = false`) : c'est ce que veut dire décommissionner.
    """
    exiger_admin(courant)
    avant = await _charger(session, ident)
    await supprimer_application(session, dict(avant), courant)
    await session.commit()


# --- Référentiel des éditeurs ----------------------------------------------------------------


@routeur.get("/referentiels/editeurs", response_model=list[ReferentielItem])
async def lister_editeurs(courant: Courant, session: Session) -> list[dict[str, Any]]:
    return [dict(r) for r in await repo.lister_editeurs(session)]


@routeur.post(
    "/referentiels/editeurs", response_model=ReferentielItem, status_code=status.HTTP_201_CREATED
)
async def ajouter_editeur(
    corps: ReferentielCreation, courant: Courant, session: Session
) -> dict[str, Any]:
    exiger_admin(courant)
    ident = await repo.trouver_ou_creer_editeur(session, corps.libelle)
    await session.commit()
    return {"id": ident, "libelle": " ".join(corps.libelle.split()), "actif": True}


@routeur.delete("/referentiels/editeurs/{ident}", status_code=status.HTTP_204_NO_CONTENT)
async def retirer_editeur(ident: str, courant: Courant, session: Session) -> None:
    """Retire un éditeur du référentiel.

    Refusé s'il reste des applications à son nom : le supprimer les détacherait sans le dire.
    """
    exiger_admin(courant)
    if await repo.editeur_utilise(session, ident):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Cet éditeur porte encore des applications — impossible de le supprimer.",
        )
    if not await repo.supprimer_editeur(session, ident):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Éditeur introuvable.")
    await session.commit()
