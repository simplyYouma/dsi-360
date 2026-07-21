"""Rappels d'échéance : trois alertes par échéance — deux avant, une le jour même.

Couvre **toutes** les échéances du produit, d'un seul mécanisme :

===========  ========================================  ==========================
Nature       Source                                    Paliers
===========  ========================================  ==========================
sla          ``activite.sla_resolution_le``            50 %, 80 %, 100 % du délai
tache        ``tache.echeance``                        J-3, J-1, jour J
jalon        ``jalon.echeance``                        J-7, J-2, jour J
projet       ``activite.donnees->>'date_fin'``         J-15, J-3, jour J
revue        ``activite.donnees->>'prochaine_revue'``  J-15, J-3, jour J
===========  ========================================  ==========================

**Pourquoi le SLA se compte en pourcentage et non en jours.** Un délai SLA va de 15 minutes
(P1 critique) à 5 jours (P4). Un palier fixe ne peut pas convenir aux deux : « J-3 » ne se
déclencherait jamais sur un SLA de 4 h, et « 2 h avant » prévient beaucoup trop tard sur un SLA
de 5 jours — c'était le défaut de l'ancien scanner, qui n'avait qu'un seul palier à 2 h. La part
du temps consommé, elle, a le même sens à toutes les priorités.

**Pourquoi les autres se comptent en jours.** Ce sont des dates posées à l'avance, sans durée de
référence : seul le temps qu'il reste pour agir compte. Les paliers s'élargissent avec l'horizon
de l'objet — une tâche se rattrape en un jour, une fin de projet non.

Un palier déjà envoyé ne repart pas (cf. ``core.rappel_echeance``). Si plusieurs paliers sont dus
d'un coup — échéance créée tardivement, ordonnanceur arrêté un moment — **un seul e-mail part**,
celui du palier le plus récent : les autres sont marqués consommés. On prévient, on ne harcèle pas.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import cast

from sqlalchemy import CursorResult, text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.notifications import notifier
from dsi360.config import get_settings
from dsi360.domain import etats
from dsi360.domain.activite import lien_activite
from dsi360.infrastructure import email_modeles
from dsi360.infrastructure.db import get_sessionmaker

#: Paliers en jours avant l'échéance, du plus tôt au plus tard. Le dernier (0) est le jour même.
PALIERS_JOURS: dict[str, tuple[int, int, int]] = {
    "tache": (3, 1, 0),
    "jalon": (7, 2, 0),
    "projet": (15, 3, 0),
    "revue": (15, 3, 0),
}
#: Paliers SLA en part du délai consommée (cf. en-tête du module).
PALIERS_SLA: tuple[float, float, float] = (0.5, 0.8, 1.0)

#: Codes de palier, dans l'ordre chronologique.
_CODES = ("avant_2", "avant_1", "jour_j")

#: Au-delà de ce retard, un palier est consommé SANS e-mail.
#:
#: Sans ce garde-fou, la première exécution après une mise en production enverrait d'un coup un
#: rappel pour chaque échéance déjà passée — des dizaines de courriels d'un seul tenant, pour des
#: dossiers dont personne n'ignore le retard. Même effet après un arrêt prolongé de l'ordonnanceur.
#: Un rappel n'a de valeur que s'il est encore une nouvelle ; passé ce délai, la liste « En retard »
#: et le tableau de bord font le travail.
FENETRE_RATTRAPAGE = timedelta(days=7)

_LIBELLE_NATURE = {
    "sla": "Échéance de résolution",
    "tache": "Échéance de tâche",
    "jalon": "Jalon de projet",
    "projet": "Fin de projet",
    "revue": "Revue périodique",
}


@dataclass(frozen=True)
class Echeance:
    """Une échéance à surveiller, quelle que soit sa nature."""

    nature: str
    cible_id: str
    echeance: datetime
    #: Début du décompte — seulement pour le SLA, dont les paliers sont proportionnels.
    depart: datetime | None
    destinataire_id: str
    activite_id: str
    module: str
    reference: str
    objet: str


def _instants(e: Echeance) -> list[datetime]:
    """Instants de déclenchement des trois paliers, du plus tôt au plus tard."""
    if e.nature == "sla" and e.depart is not None:
        total = (e.echeance - e.depart).total_seconds()
        if total <= 0:
            return [e.echeance] * 3
        return [e.depart + timedelta(seconds=total * p) for p in PALIERS_SLA]
    jours = PALIERS_JOURS.get(e.nature, (3, 1, 0))
    return [e.echeance - timedelta(days=j) for j in jours]


def paliers_dus(e: Echeance, maintenant: datetime) -> list[str]:
    """Codes des paliers atteints, du plus tôt au plus récent. Vide si aucun n'est encore dû."""
    return [code for code, quand in zip(_CODES, _instants(e), strict=True) if maintenant >= quand]


def trop_ancien(e: Echeance, palier: str, maintenant: datetime) -> bool:
    """Ce palier est-il dû depuis trop longtemps pour qu'un rappel ait encore un sens ?"""
    quand = dict(zip(_CODES, _instants(e), strict=True))[palier]
    return maintenant - quand > FENETRE_RATTRAPAGE


def _reste(e: Echeance, maintenant: datetime) -> str:
    """Temps restant, en clair. Dit franchement quand l'échéance est déjà passée."""
    delta = e.echeance - maintenant
    secondes = delta.total_seconds()
    if secondes < 0:
        secondes = -secondes
        prefixe = "dépassée depuis "
    else:
        prefixe = "dans "
    if secondes < 3600:
        return f"{prefixe}{max(1, int(secondes // 60))} min"
    if secondes < 86400:
        return f"{prefixe}{int(secondes // 3600)} h"
    return f"{prefixe}{int(secondes // 86400)} j"


def _phases_sql(*phases: str) -> str:
    """Condition « le statut appartient à ces phases », dérivée de `domain.etats`."""
    noms = sorted(etats.statuts_de_phase(*phases))
    valeurs = ", ".join("'" + n.replace("'", "''") + "'" for n in noms)
    return f"a.statut IN ({valeurs})"


# Une échéance n'a de sens que sur un dossier encore en cours.
#
# C'est le STATUT qui en décide, pas les horodatages : seuls « Résolu » et « Clôturé » posent un
# `resolu_le` / `cloture_le`. « Rejeté », « Annulé », « Réalisé », « Maîtrisé » n'en posent aucun
# et passaient donc le filtre — un ticket annulé continuait de réclamer son SLA indéfiniment.
# Les horodatages restent testés en complément : un dossier résolu ne se relance pas non plus.
_ACTIF = f"({_phases_sql(etats.EN_COURS)} AND a.cloture_le IS NULL AND a.resolu_le IS NULL)"

# Exception assumée pour la revue périodique : un risque « Maîtrisé » ou « Accepté » est en phase
# terminée, mais c'est précisément sa revue qui doit le ramener dans les écrans. On n'écarte donc
# ici que l'abandon (rejeté, annulé) et la clôture définitive.
_REVUABLE = f"(NOT ({_phases_sql(etats.ABANDONNE)}) AND a.cloture_le IS NULL)"


def _destinataires(*roles: str) -> str:
    """Qui prévenir : les rôles porteurs de l'échéance, PLUS les contributeurs du dossier.

    Un contributeur travaille sur le dossier — il doit voir venir l'échéance comme les autres.
    Le ``UNION`` dédoublonne : une même personne cumulant deux rôles n'est prévenue qu'une fois.
    Produit une ligne par destinataire ; ``d.dest`` peut être NULL et se filtre côté appelant.
    """
    return (
        "CROSS JOIN LATERAL ("
        f"  SELECT unnest(ARRAY[{', '.join(roles)}]) AS dest"
        "  UNION"
        "  SELECT aa.utilisateur_id FROM core.activite_acteur aa"
        "   WHERE aa.activite_id = a.id AND aa.role = 'CONTRIBUTEUR'"
        ") d"
    )

_SQL_SLA = f"""
SELECT 'sla' AS nature, a.id::text AS cible_id, a.sla_resolution_le AS echeance,
       a.cree_le AS depart, d.dest::text AS destinataire_id,
       a.id::text AS activite_id, a.module, a.reference, a.titre AS objet
FROM core.activite a
{_destinataires("coalesce(a.responsable_id, a.demandeur_id)")}
WHERE {_ACTIF} AND a.sla_resolution_le IS NOT NULL AND a.cree_le IS NOT NULL
  AND d.dest IS NOT NULL
"""

# L'échéance d'une tâche concerne son porteur, le responsable du dossier — chef de projet ou
# gestionnaire du changement, qui répond du planning d'ensemble — et les contributeurs.
_SQL_TACHE = f"""
SELECT 'tache' AS nature, t.id::text AS cible_id, t.echeance::timestamptz AS echeance,
       NULL::timestamptz AS depart, d.dest::text AS destinataire_id,
       a.id::text AS activite_id, a.module, a.reference, t.titre AS objet
FROM core.tache t
JOIN core.activite a ON a.id = t.activite_id
{_destinataires("t.assigne_id", "a.responsable_id")}
WHERE t.echeance IS NOT NULL AND d.dest IS NOT NULL
  AND t.statut <> 'Terminée' AND {_ACTIF}
"""

_SQL_JALON = f"""
SELECT 'jalon' AS nature, j.id::text AS cible_id, j.echeance::timestamptz AS echeance,
       NULL::timestamptz AS depart, d.dest::text AS destinataire_id,
       a.id::text AS activite_id, a.module, a.reference, j.titre AS objet
FROM core.jalon j
JOIN core.activite a ON a.id = j.activite_id
{_destinataires("a.responsable_id")}
WHERE j.echeance IS NOT NULL AND j.atteint = false
  AND d.dest IS NOT NULL AND {_ACTIF}
"""

_SQL_PROJET = f"""
SELECT 'projet' AS nature, a.id::text AS cible_id,
       (a.donnees->>'date_fin')::date::timestamptz AS echeance,
       NULL::timestamptz AS depart, d.dest::text AS destinataire_id,
       a.id::text AS activite_id, a.module, a.reference, a.titre AS objet
FROM core.activite a
{_destinataires("a.responsable_id")}
WHERE a.module = 'projet' AND nullif(a.donnees->>'date_fin', '') IS NOT NULL
  AND d.dest IS NOT NULL AND {_ACTIF}
"""

_SQL_REVUE = f"""
SELECT 'revue' AS nature, a.id::text AS cible_id,
       (a.donnees->>'prochaine_revue')::date::timestamptz AS echeance,
       NULL::timestamptz AS depart, d.dest::text AS destinataire_id,
       a.id::text AS activite_id, a.module, a.reference, a.titre AS objet
FROM core.activite a
{_destinataires("a.responsable_id")}
WHERE nullif(a.donnees->>'prochaine_revue', '') IS NOT NULL
  AND d.dest IS NOT NULL AND {_REVUABLE}
"""

_SOURCES = (_SQL_SLA, _SQL_TACHE, _SQL_JALON, _SQL_PROJET, _SQL_REVUE)

_MARQUER = text(
    "INSERT INTO core.rappel_echeance "
    "(cible_type, cible_id, destinataire_id, echeance, palier) "
    "VALUES (:nature, cast(:cible as uuid), cast(:dest as uuid), :echeance, :palier) "
    "ON CONFLICT DO NOTHING RETURNING palier"
)


async def _collecter(session: AsyncSession) -> list[Echeance]:
    echeances: list[Echeance] = []
    for requete in _SOURCES:
        for r in (await session.execute(text(requete))).mappings().all():
            if r["echeance"] is None:
                continue
            echeances.append(
                Echeance(
                    nature=str(r["nature"]),
                    cible_id=str(r["cible_id"]),
                    echeance=_en_utc(r["echeance"]),
                    depart=_en_utc(r["depart"]) if r["depart"] is not None else None,
                    destinataire_id=str(r["destinataire_id"]),
                    activite_id=str(r["activite_id"]),
                    module=str(r["module"]),
                    reference=str(r["reference"]),
                    objet=str(r["objet"]),
                )
            )
    return echeances


def _en_utc(valeur: datetime | date) -> datetime:
    """Les dates nues (tâche, jalon) deviennent le début de journée, en UTC comme le reste."""
    if not isinstance(valeur, datetime):
        return datetime(valeur.year, valeur.month, valeur.day, tzinfo=UTC)
    return valeur if valeur.tzinfo is not None else valeur.replace(tzinfo=UTC)


async def scanner_rappels(maintenant: datetime | None = None) -> dict[str, int]:
    """Envoie les rappels d'échéance dus.

    Retourne le nombre d'échéances vues, de rappels émis, et de paliers consommés sans envoi
    (trop anciens — cf. `FENETRE_RATTRAPAGE`).
    """
    instant = maintenant or datetime.now(UTC)
    envoyes = 0
    ignores = 0
    async with get_sessionmaker()() as session:
        echeances = await _collecter(session)
        for e in echeances:
            dus = paliers_dus(e, instant)
            if not dus:
                continue
            # Tous les paliers atteints sont consommés ; seul le plus récent donne lieu à un envoi.
            nouveaux = []
            for palier in dus:
                marque = await session.scalar(
                    _MARQUER,
                    {
                        "nature": e.nature,
                        "cible": e.cible_id,
                        "dest": e.destinataire_id,
                        "echeance": e.echeance,
                        "palier": palier,
                    },
                )
                if marque is not None:
                    nouveaux.append(palier)
            if not nouveaux:
                continue
            # Un palier trop ancien est consommé sans e-mail : il a été marqué juste au-dessus,
            # donc il ne repartira pas — mais on n'annonce pas comme une nouvelle un retard
            # vieux d'un mois.
            if trop_ancien(e, nouveaux[-1], instant):
                ignores += 1
                continue
            await _prevenir(session, e, instant)
            envoyes += 1
        await session.commit()
    return {"vues": len(echeances), "envoyes": envoyes, "ignores": ignores}


async def _prevenir(session: AsyncSession, e: Echeance, maintenant: datetime) -> None:
    nature = _LIBELLE_NATURE.get(e.nature, "Échéance")
    atteinte = maintenant >= e.echeance
    reste = _reste(e, maintenant)
    quand = e.echeance.strftime("%d/%m/%Y")
    titre = f"{nature} {'atteinte' if atteinte else 'proche'} — {e.reference}"
    message = f"« {e.objet} » ({e.reference}) — échéance du {quand}, {reste}."
    url = lien_activite(get_settings().url_app, e.module, e.activite_id)

    # Le SLA garde son gabarit dédié (il porte la cible et le verdict) ; les autres échéances ont
    # le leur. Dans les deux cas un vrai gabarit de marque, jamais un message nu.
    if e.nature == "sla":
        courriel = email_modeles.alerte_sla(
            reference=e.reference,
            titre_activite=e.objet,
            depasse=atteinte,
            echeance=e.echeance.strftime("%d/%m/%Y à %Hh%M"),
            url=url,
        )
        type_ = "SLA_DEPASSE" if atteinte else "SLA_APPROCHE"
    else:
        courriel = email_modeles.alerte_echeance(
            nature=nature,
            objet=e.objet,
            reference=e.reference,
            echeance=quand,
            reste=reste,
            atteinte=atteinte,
            url=url,
        )
        type_ = "ECHEANCE"

    await notifier(
        session,
        destinataire_id=e.destinataire_id,
        activite_id=e.activite_id,
        type_=type_,
        titre=titre,
        message=message,
        courriel=courriel,
    )


_PURGE = text(
    "DELETE FROM core.rappel_echeance WHERE envoye_le < now() - make_interval(days => :j)"
)


async def purger_rappels(jours: int = 400) -> int:
    """Oublie les rappels anciens : la table ne sert qu'à ne pas notifier deux fois."""
    async with get_sessionmaker()() as session:
        resultat = await session.execute(_PURGE, {"j": jours})
        await session.commit()
        return int(cast(CursorResult[object], resultat).rowcount or 0)
