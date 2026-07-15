"""Granularité d'un axe de temps selon l'étendue de la période choisie.

Trois pas seulement, à la demande métier : **jour** (avec le nom du jour) → **mois** → **année**.
Ces fonctions sont pures et partagées par les analyses et le tableau de bord, pour que l'axe et les
libellés soient identiques d'un onglet à l'autre.
"""

from datetime import datetime, timedelta

_MOIS_FR = (
    "janv.", "févr.", "mars", "avr.", "mai", "juin",
    "juil.", "août", "sept.", "oct.", "nov.", "déc.",
)
_JOURS_FR = ("lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim.")

# `heure`/`semaine` restent pris en charge par les fonctions (usages historiques), mais
# `granularite()` ne renvoie que jour/mois/année.
UNIT_SQL = {"heure": "hour", "jour": "day", "semaine": "week", "mois": "month", "annee": "year"}
FMT_SQL = {
    "heure": "YYYY-MM-DD HH24",
    "jour": "YYYY-MM-DD",
    "semaine": "YYYY-MM-DD",
    "mois": "YYYY-MM",
    "annee": "YYYY",
}


def granularite(span_jours: int) -> str:
    if span_jours <= 31:
        return "jour"
    if span_jours <= 731:
        return "mois"
    return "annee"


def tronquer(unit: str, d: datetime) -> datetime:
    minuit = d.replace(minute=0, second=0, microsecond=0)
    if unit == "heure":
        return minuit
    minuit = minuit.replace(hour=0)
    if unit == "jour":
        return minuit
    if unit == "semaine":
        return minuit - timedelta(days=minuit.weekday())
    if unit == "mois":
        return minuit.replace(day=1)
    return minuit.replace(month=1, day=1)


def ajouter(unit: str, d: datetime) -> datetime:
    if unit == "heure":
        return d + timedelta(hours=1)
    if unit == "jour":
        return d + timedelta(days=1)
    if unit == "semaine":
        return d + timedelta(days=7)
    if unit == "mois":
        return d.replace(year=d.year + (d.month == 12), month=(d.month % 12) + 1)
    return d.replace(year=d.year + 1)


def cle_bucket(unit: str, d: datetime) -> str:
    if unit == "heure":
        return d.strftime("%Y-%m-%d %H")
    if unit in ("jour", "semaine"):
        return d.strftime("%Y-%m-%d")
    if unit == "mois":
        return d.strftime("%Y-%m")
    return d.strftime("%Y")


def libelle_bucket(unit: str, d: datetime) -> str:
    if unit == "heure":
        return f"{d.hour:02d} h"
    if unit == "jour":
        return f"{_JOURS_FR[d.weekday()]} {d.day:02d}/{d.month:02d}"
    if unit == "semaine":
        return f"sem. {d.day:02d}/{d.month:02d}"
    if unit == "mois":
        return f"{_MOIS_FR[d.month - 1]} {d.year % 100:02d}"
    return str(d.year)


def suite_buckets(unit: str, debut: datetime, fin: datetime, limite: int = 400) -> list[datetime]:
    """Liste des débuts de bucket couvrant [debut, fin], bornée à `limite` pas."""
    dep, der = tronquer(unit, debut), tronquer(unit, fin)
    seaux: list[datetime] = []
    cur = dep
    while cur <= der and len(seaux) < limite:
        seaux.append(cur)
        cur = ajouter(unit, cur)
    return seaux or [dep]
