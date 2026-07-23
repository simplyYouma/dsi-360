"""Module Inventaire : le parc matériel de la DSI (immobilisations IT).

Un équipement n'est pas une activité : ni workflow, ni SLA, ni valideur. Ce routeur est donc
autonome, sans passer par la fabrique `activites_communs`.

L'amortissement n'est jamais stocké : il se calcule à la lecture (`domain/amortissement`), sinon
la valeur nette comptable serait fausse dès le lendemain de son enregistrement.
"""

import re
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import RowMapping, text
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
    AnalysesParc,
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
    """Nom du détenteur : celui du compte rapproché, sinon celui saisi librement.

    On n'affiche jamais le matricule brut à la place d'un nom : il est exposé à part
    (`matricule`), pour qu'on voie qu'un rattachement reste à faire.
    """
    if r["det_prenom"] is not None:
        return f"{r['det_prenom']} {r['det_nom']}"
    # Détenteur hors système (agence, prestataire) : un nom, sans compte derrière.
    externe: str | None = r["detenteur_externe"]
    return externe


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


async def _detail(session: AsyncSession, r: RowMapping) -> dict[str, Any]:
    a = _amortissement(r)
    return {
        "historique": await _historique(session, r),
        **_resume(r),
        "emplacement_id": r["emplacement_id"],
        "departement_id": r["departement_id"],
        "detenteur_id": r["detenteur_id"],
        "detenteur_externe": r["detenteur_externe"],
        "taux": _nombre(r["taux"]),
        "duree_annees": r["duree_annees"],
        "source": r["source"],
        "dotation_annuelle": a.dotation_annuelle,
        "amortissement_cumule": a.cumul,
        "fin_amortissement": a.fin,
        "totalement_amorti": a.totalement_amorti,
        "amortissement_incoherent": a.incoherent,
    }


# La fiche est journalisée sous son code immo (sinon sa désignation) : on relit sous les deux
# repères, un équipement pouvant recevoir son code après coup.
_HISTORIQUE = text(
    "SELECT j.action, j.horodatage, j.acteur_email AS acteur, "
    "j.ancienne_valeur AS anciennes, j.nouvelle_valeur AS nouvelles FROM audit.journal j "
    "WHERE j.module = 'inventaire' AND j.cible_type = 'equipement' "
    "AND j.cible_id IN (:code, :designation) ORDER BY j.id DESC LIMIT 15"
)

#: Nom d'écran des champs journalisés — l'historique parle français, pas colonne SQL.
_LIBELLE_CHAMP = {
    "designation": "désignation",
    "code_immo": "code immo",
    "numero_serie": "n° de série",
    "modele": "modèle",
    "emplacement": "emplacement",
    "departement": "département",
    "detenteur": "détenteur",
    "matricule_brut": "matricule",
    "taux": "taux d'amortissement",
    "date_acquisition": "date d'acquisition",
    "duree_annees": "durée",
    "valeur_acquisition": "valeur d'acquisition",
    "actif": "en service",
    # Constats d'inventaire : posés par les campagnes, relus dans l'historique de la fiche.
    "etat": "état constaté",
    "campagne": "campagne",
}

#: Unité d'un champ chiffré. Un taux se lit « 25 % », pas « 25.000 » : la base stocke des
#: décimales de précision, l'écran n'a que faire de leurs zéros.
_UNITE_CHAMP = {"taux": "%", "duree_annees": "ans", "valeur_acquisition": "FCFA"}

_UUID_BRUT = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
#: Espace fine insécable : le séparateur de milliers français, qui ne coupe pas le nombre.
_FINE = " "


def _nombre_fr(valeur: float) -> str:
    """« 25.000 » -> « 25 », « 12.5 » -> « 12,5 », « 29712835 » -> « 29 712 835 »."""
    if valeur == int(valeur):
        return f"{int(valeur):,}".replace(",", _FINE)
    return (
        f"{valeur:,.3f}".rstrip("0").rstrip(".").replace(",", _FINE).replace(".", ",")
    )


def _valeur_lisible(valeur: Any, cle: str | None = None) -> str:
    if valeur is None or valeur == "":
        return "—"
    if isinstance(valeur, bool):
        return "oui" if valeur else "non"
    texte_brut = str(valeur)
    # Les toutes premières écritures du journal portaient des identifiants : illisibles,
    # on les tait plutôt que d'afficher un uuid.
    if _UUID_BRUT.fullmatch(texte_brut.lower()):
        return "…"
    unite = _UNITE_CHAMP.get(cle or "")
    if unite is not None:
        # Le journal mêle des Decimal sérialisés (« 25.000 ») et des flottants (20.0) : on
        # ramène les deux à la même écriture, sinon le même taux paraît avoir changé.
        try:
            return f"{_nombre_fr(float(texte_brut))}{_FINE}{unite}"
        except ValueError:
            return texte_brut
    return texte_brut


def _texte_changement(anciennes: Any, nouvelles: Any) -> str | None:
    """« emplacement : Siège → Agence Kayes » — l'acheminement du matériel, lisible."""
    if not isinstance(nouvelles, dict):
        return None
    avant = anciennes if isinstance(anciennes, dict) else {}
    fragments = []
    for cle, v in nouvelles.items():
        if cle not in _LIBELLE_CHAMP:
            continue
        ancienne, nouvelle = _valeur_lisible(avant.get(cle), cle), _valeur_lisible(v, cle)
        # Comparaison sur le texte affiché : « 25.000 » et « 25.0 » sont le même taux, et une
        # ligne « taux : 25 % → 25 % » ne raconterait rien.
        if ancienne != nouvelle:
            fragments.append(f"{_LIBELLE_CHAMP[cle]} : {ancienne} → {nouvelle}")
    return " · ".join(fragments) or None


async def _historique(session: AsyncSession, r: RowMapping) -> list[dict[str, Any]]:
    lignes = await session.execute(
        _HISTORIQUE, {"code": r["code_immo"] or "", "designation": r["designation"]}
    )
    return [
        {
            "action": x["action"],
            "horodatage": x["horodatage"],
            "acteur": x["acteur"],
            "detail": _texte_changement(x["anciennes"], x["nouvelles"]),
        }
        for x in lignes.mappings().all()
    ]


async def _charger(session: AsyncSession, ident: str) -> RowMapping:
    r = await repo.par_id(session, ident)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Équipement introuvable.")
    return r


#: Références acceptées au PATCH/POST : table où l'identifiant doit exister, et nom d'écran.
_CIBLES_REFERENCE = {
    "emplacement_id": ("core.emplacement", "L'emplacement"),
    "departement_id": ("core.departement_equipement", "Le département"),
    "detenteur_id": ("core.utilisateur", "Le détenteur"),
}


async def _valider_references(session: AsyncSession, champs: dict[str, Any]) -> None:
    """Un identifiant inconnu doit répondre 422 en clair, pas une erreur d'intégrité en 500.

    Le front n'envoie que des ids issus de ses listes, mais le serveur fait foi : rien
    n'empêche un appel direct à l'API avec un id forgé.
    """
    for cle, (table, quoi) in _CIBLES_REFERENCE.items():
        ident = champs.get(cle)
        if ident is None:
            continue
        if not _UUID_BRUT.fullmatch(str(ident).lower()):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, f"{quoi} indiqué est invalide."
            )
        existe = await session.scalar(
            text(f"SELECT 1 FROM {table} WHERE id = cast(:id as uuid)"), {"id": ident}
        )
        if existe is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, f"{quoi} indiqué n'existe pas."
            )


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


def _agreger(
    lignes: list[tuple[str, float | None, float | None]], plafond: int = 10
) -> list[dict[str, Any]]:
    """Agrège (libellé, VA, VNC) par libellé, trie, replie la queue dans « Autres ».

    Le repli est annoncé par son libellé : un graphique qui tait ce qu'il coupe ment.
    """
    groupes: dict[str, dict[str, Any]] = {}
    for libelle, va, vnc in lignes:
        g = groupes.setdefault(
            libelle,
            {"libelle": libelle, "nombre": 0, "valeur_acquisition": 0.0, "valeur_nette": 0.0},
        )
        g["nombre"] += 1
        g["valeur_acquisition"] += va or 0.0
        g["valeur_nette"] += vnc or 0.0
    tries = sorted(groupes.values(), key=lambda g: (-g["nombre"], g["libelle"]))
    if len(tries) <= plafond:
        return tries
    tete, queue = tries[:plafond], tries[plafond:]
    autres = {
        "libelle": f"Autres ({len(queue)})",
        "nombre": sum(g["nombre"] for g in queue),
        "valeur_acquisition": sum(g["valeur_acquisition"] for g in queue),
        "valeur_nette": sum(g["valeur_nette"] for g in queue),
    }
    return [*tete, autres]


def _tranche(
    libelle: str, membres: list[tuple[RowMapping, amortissement.Amortissement]]
) -> dict[str, Any]:
    return {
        "libelle": libelle,
        "nombre": len(membres),
        "valeur_acquisition": sum(_nombre(r["valeur_acquisition"]) or 0.0 for r, _ in membres),
        "valeur_nette": sum(a.valeur_nette or 0.0 for _, a in membres),
    }


#: Tranches d'âge du matériel : bornes en années, du plus récent au plus ancien.
_TRANCHES_AGE = [
    ("Moins de 3 ans", 0.0, 3.0),
    ("3 à 6 ans", 3.0, 6.0),
    ("Plus de 6 ans", 6.0, 999.0),
]


@routeur.get("/analyses", response_model=AnalysesParc)
async def analyses_parc(courant: Courant, session: Session) -> dict[str, Any]:
    """Le parc en chiffres (lot 4) : localisation, valeur au bilan, obsolescence.

    Tout se calcule à la lecture sur le parc **actif** — une VNC stockée serait fausse dès le
    lendemain, exactement comme sur la fiche.
    """
    actifs = [r for r in await repo.lister_tout(session) if r["actif"]]
    situations = [(r, _amortissement(r)) for r in actifs]

    aujourd_hui = date.today()
    par_age = [
        _tranche(
            libelle,
            [
                (r, a)
                for r, a in situations
                if r["date_acquisition"] is not None
                and borne_min <= (aujourd_hui - r["date_acquisition"]).days / 365.25 < borne_max
            ],
        )
        for libelle, borne_min, borne_max in _TRANCHES_AGE
    ]
    sans_date = [(r, a) for r, a in situations if r["date_acquisition"] is None]
    if sans_date:
        par_age.append(_tranche("Sans date", sans_date))

    return {
        "parc_actif": len(actifs),
        "valeur_acquisition": round(
            sum(_nombre(r["valeur_acquisition"]) or 0.0 for r in actifs), 2
        ),
        "valeur_nette": round(sum(a.valeur_nette or 0.0 for _, a in situations), 2),
        "totalement_amortis": sum(1 for _, a in situations if a.totalement_amorti),
        "sans_donnee_comptable": sum(1 for _, a in situations if a.valeur_nette is None),
        "par_emplacement": _agreger(
            [
                (
                    r["emplacement"] or "Sans emplacement",
                    _nombre(r["valeur_acquisition"]),
                    a.valeur_nette,
                )
                for r, a in situations
            ]
        ),
        "par_departement": _agreger(
            [
                (
                    r["departement"] or "Sans département",
                    _nombre(r["valeur_acquisition"]),
                    a.valeur_nette,
                )
                for r, a in situations
            ]
        ),
        "par_age": par_age,
    }


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
    return await _detail(session, await _charger(session, ident))


@routeur.post("", response_model=EquipementDetail, status_code=status.HTTP_201_CREATED)
async def creer(corps: EquipementCreation, courant: Courant, session: Session) -> dict[str, Any]:
    """Créer un équipement : l'administrateur tient le parc, les autres le consultent.

    Même partage des rôles que pour l'assignation des activités (ADR-0003) — et le serveur fait
    foi : masquer le bouton à l'écran ne serait pas une barrière.
    """
    exiger_admin(courant)
    await _refuser_code_deja_pris(session, corps.code_immo, None)
    await _valider_references(session, corps.model_dump(exclude_none=True))
    ident = await creer_equipement(session, corps.model_dump(exclude_none=True), courant)
    await session.commit()
    return await _detail(session, await _charger(session, ident))


@routeur.patch("/{ident}", response_model=EquipementDetail)
async def modifier(
    ident: str, corps: EquipementMaj, courant: Courant, session: Session
) -> dict[str, Any]:
    exiger_admin(courant)
    avant = await _charger(session, ident)
    champs = corps.model_dump(exclude_unset=True)
    # Un matériel sorti du parc reste modifiable : on corrige une désignation ou un emplacement
    # de sortie longtemps après coup. Le journal garde qui a changé quoi — c'est lui qui protège
    # l'information, pas un verrou qui figerait aussi les erreurs.
    if "code_immo" in champs:
        await _refuser_code_deja_pris(session, champs["code_immo"], ident)
    await _valider_references(session, champs)
    await maj_equipement(session, dict(avant), champs, courant)
    await session.commit()
    return await _detail(session, await _charger(session, ident))


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
