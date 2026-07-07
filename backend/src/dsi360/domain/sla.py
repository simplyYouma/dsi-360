"""Moteur SLA : échéances de prise en charge / résolution selon la priorité, et statut d'une
échéance (à l'heure / en approche / dépassé). Pur et paramétrable. Cf. docs/02-DOMAIN-MODEL §2.
"""

from datetime import datetime, timedelta
from typing import Literal, NamedTuple

StatutSla = Literal["a_lheure", "approche", "depasse"]


class CiblesSla(NamedTuple):
    prise_en_charge_minutes: int
    resolution_minutes: int


# SLA par défaut par priorité P1..P5 (prise en charge, résolution), en minutes. Paramétrable.
# Sert de repli quand un module n'a pas (encore) de règles propres en base.
SLA_DEFAUT: dict[int, CiblesSla] = {
    1: CiblesSla(15, 4 * 60),
    2: CiblesSla(30, 8 * 60),
    3: CiblesSla(2 * 60, 2 * 24 * 60),
    4: CiblesSla(24 * 60, 5 * 24 * 60),
    5: CiblesSla(2 * 24 * 60, 10 * 24 * 60),
}

# Modules dont les cibles SLA (P1..P5) sont paramétrables par module dans l'administration.
# Les autres (projet, risque, audit, gouvernance) suivent une logique d'échéance propre.
MODULES_SLA: tuple[str, ...] = ("incident", "demande", "changement", "cybersecurite")


class Echeances(NamedTuple):
    prise_en_charge_le: datetime
    resolution_le: datetime


def echeances(
    priorite: int, debut: datetime, matrice: dict[int, CiblesSla] = SLA_DEFAUT
) -> Echeances:
    cibles = matrice.get(priorite)
    if cibles is None:
        raise ValueError(f"Priorité inconnue : {priorite}")
    return Echeances(
        prise_en_charge_le=debut + timedelta(minutes=cibles.prise_en_charge_minutes),
        resolution_le=debut + timedelta(minutes=cibles.resolution_minutes),
    )


def statut_sla(echeance: datetime, maintenant: datetime, fenetre_approche: timedelta) -> StatutSla:
    """Compare l'instant courant à l'échéance.

    - dépassé : l'échéance est passée ;
    - approche : il reste moins que la fenêtre d'alerte ;
    - à l'heure : sinon.
    """
    if maintenant >= echeance:
        return "depasse"
    if echeance - maintenant <= fenetre_approche:
        return "approche"
    return "a_lheure"
