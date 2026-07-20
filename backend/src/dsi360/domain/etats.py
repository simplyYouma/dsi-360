"""Machines à états par module (cycles de vie ITIL) — **source de vérité unique** des statuts.

Cf. docs/02-DOMAIN-MODEL §3.

Trois notions distinctes, à ne jamais confondre :

1. **Le statut** — l'étape du cycle de vie, propre au module (« Ouvert », « CAB », « Maîtrisé »).
   C'est ce qui est stocké et ce qu'on fait avancer. Une transition n'est autorisée que si l'état
   cible figure dans les suites de l'état courant.

2. **La phase** — le regroupement commun aux huit modules : ``EN_COURS`` / ``TERMINE`` /
   ``ABANDONNE``. C'est l'axe des filtres, des compteurs et des statistiques. Chaque statut déclare
   sa phase **ici, une seule fois** : aucun autre fichier ne redevine le sens d'un statut par
   comparaison de chaînes.

3. **Le verrou** (``est_etat_terminal``) — un état *sans suite* : le dossier ne bouge plus, il
   passe en lecture seule. Ce n'est PAS la phase : « Résolu » est en phase ``TERMINE`` (il ne
   compte plus comme en cours) mais reste modifiable, puisqu'il peut encore être clôturé ou rouvert.

Le **retard SLA** ne figure pas ici : c'est une horloge, pas une étape. Un ticket en retard est
presque toujours en cours. Il se croise avec la phase, il ne la remplace pas.

Le ``ton`` porte la nuance visuelle (couleur du badge). Il vit dans la même table que la phase pour
que le sens d'un statut se lise à un seul endroit.
"""

from typing import Final, NamedTuple

# --- Phases : l'axe commun à tous les modules (filtres, compteurs, statistiques) ---
EN_COURS: Final = "en_cours"
TERMINE: Final = "termine"
ABANDONNE: Final = "abandonne"
#: Phases où le dossier ne réclame plus de travail.
PHASES_FINIES: Final = frozenset({TERMINE, ABANDONNE})

# --- Tons : la nuance visuelle d'un statut (couleur du badge), déclarée avec lui ---
NOUVEAU: Final = "nouveau"  # vient d'arriver, personne n'y a touché
ACTIF: Final = "actif"  # du travail en cours chez nous
ATTENTE: Final = "attente"  # suspendu à la décision ou à l'avis d'un tiers
RECUL: Final = "recul"  # le dossier revient en arrière ou s'arrête
SUCCES: Final = "succes"  # abouti
ECHEC: Final = "echec"  # n'aboutira pas


class Etat(NamedTuple):
    """Un statut : ses suites autorisées, sa phase, et son ton visuel."""

    suites: tuple[str, ...]
    phase: str
    ton: str


# module -> { statut: Etat(suites, phase, ton) }
# L'ordre des clés donne l'ordre chronologique du cycle de vie (affiché sur la fiche).
ETATS: dict[str, dict[str, Etat]] = {
    "incident": {
        "Nouveau": Etat(("Ouvert", "Annulé"), EN_COURS, NOUVEAU),
        "Ouvert": Etat(("Résolu", "Annulé"), EN_COURS, ACTIF),
        "Résolu": Etat(("Clôturé", "Réouvert"), TERMINE, SUCCES),
        "Réouvert": Etat(("Ouvert", "Résolu"), EN_COURS, RECUL),
        # Un incident clôturé reste réouvrable : le problème peut resurgir.
        "Clôturé": Etat(("Réouvert",), TERMINE, SUCCES),
        "Annulé": Etat((), ABANDONNE, ECHEC),
    },
    "demande": {
        "Nouvelle": Etat(("Qualifiée", "Rejetée"), EN_COURS, NOUVEAU),
        "Qualifiée": Etat(("En cours", "Rejetée"), EN_COURS, ACTIF),
        "En cours": Etat(("En validation",), EN_COURS, ACTIF),
        "En validation": Etat(("Résolue", "Rejetée"), EN_COURS, ATTENTE),
        "Résolue": Etat(("Clôturée", "Réouverte"), TERMINE, SUCCES),
        "Réouverte": Etat(("En cours",), EN_COURS, RECUL),
        # Une demande clôturée reste réouvrable : le besoin peut revenir.
        "Clôturée": Etat(("Réouverte",), TERMINE, SUCCES),
        "Rejetée": Etat((), ABANDONNE, ECHEC),
    },
    "changement": {
        "Brouillon": Etat(("Soumis",), EN_COURS, NOUVEAU),
        "Soumis": Etat(("Évaluation",), EN_COURS, ATTENTE),
        "Évaluation": Etat(("CAB", "ECAB"), EN_COURS, ATTENTE),
        "CAB": Etat(("Validé", "Rejeté"), EN_COURS, ATTENTE),
        "ECAB": Etat(("Validé", "Rejeté"), EN_COURS, ATTENTE),
        # Validé n'est pas une fin : six étapes restent avant la clôture.
        "Validé": Etat(("Planifié",), EN_COURS, ACTIF),
        "Planifié": Etat(("En implémentation",), EN_COURS, ACTIF),
        "En implémentation": Etat(("Implémenté", "Retour arrière"), EN_COURS, ACTIF),
        # Implémenté non plus : la revue post-implémentation est obligatoire (ITIL SI-12.04).
        "Implémenté": Etat(("Revue post-implémentation",), EN_COURS, ACTIF),
        "Revue post-implémentation": Etat(("Clôturé",), EN_COURS, ATTENTE),
        "Retour arrière": Etat(("Clôturé",), EN_COURS, RECUL),
        "Rejeté": Etat((), ABANDONNE, ECHEC),
        "Clôturé": Etat((), TERMINE, SUCCES),
    },
    "projet": {
        "Cadrage": Etat(("En cours",), EN_COURS, NOUVEAU),
        "En cours": Etat(("Suspendu", "Clôturé"), EN_COURS, ACTIF),
        "Suspendu": Etat(("En cours",), EN_COURS, RECUL),
        "Clôturé": Etat((), TERMINE, SUCCES),
    },
    "audit": {
        "Ouverte": Etat(("Plan d'action",), EN_COURS, NOUVEAU),
        "Plan d'action": Etat(("En cours",), EN_COURS, ACTIF),
        "En cours": Etat(("En validation de clôture",), EN_COURS, ACTIF),
        "En validation de clôture": Etat(("Clôturée", "En cours"), EN_COURS, ATTENTE),
        "Clôturée": Etat((), TERMINE, SUCCES),
    },
    "risque": {
        "Identifié": Etat(("Évalué",), EN_COURS, NOUVEAU),
        "Évalué": Etat(("Traitement",), EN_COURS, ACTIF),
        "Traitement": Etat(("Maîtrisé", "Accepté"), EN_COURS, ACTIF),
        # Un risque maîtrisé ou accepté ne réclame plus de travail : il quitte les listes actives
        # et y revient de lui-même quand sa revue périodique arrive à échéance.
        "Maîtrisé": Etat(("Revue",), TERMINE, SUCCES),
        "Accepté": Etat(("Revue",), TERMINE, SUCCES),
        "Revue": Etat(("Traitement",), EN_COURS, ATTENTE),
    },
    "cybersecurite": {
        # Ton ACTIF et non NOUVEAU : « Ouvert » désigne la deuxième étape d'un incident. Un même
        # libellé doit garder le même sens partout, sinon l'écran — qui affiche souvent un badge
        # sans connaître le module — ne peut pas trancher. Une vulnérabilité ouverte est de toute
        # façon un sujet actif.
        "Ouvert": Etat(("En traitement", "Accepté"), EN_COURS, ACTIF),
        "En traitement": Etat(("Corrigé", "Accepté"), EN_COURS, ACTIF),
        "Corrigé": Etat(("Clôturé", "Réouvert"), TERMINE, SUCCES),
        # Vulnérabilité acceptée : décision assumée, plus de travail attendu.
        "Accepté": Etat(("Clôturé",), TERMINE, SUCCES),
        "Réouvert": Etat(("En traitement",), EN_COURS, RECUL),
        "Clôturé": Etat((), TERMINE, SUCCES),
    },
    "gouvernance": {
        "À engager": Etat(("En cours",), EN_COURS, NOUVEAU),
        "En cours": Etat(("Réalisé", "Reporté"), EN_COURS, ACTIF),
        "Reporté": Etat(("En cours",), EN_COURS, RECUL),
        "Réalisé": Etat((), TERMINE, SUCCES),
    },
}


def _module(module: str) -> dict[str, Etat]:
    etats = ETATS.get(module)
    if etats is None:
        raise ValueError(f"Module inconnu : {module}")
    return etats


def etat_initial(module: str) -> str:
    """Premier état du cycle de vie d'un module (clé d'insertion d'ordre)."""
    etats = _module(module)
    if not etats:
        raise ValueError(f"Module sans état : {module}")
    return next(iter(etats))


def ordre_etats(module: str) -> list[str]:
    """Liste ordonnée des états du module (ordre chronologique du cycle de vie)."""
    return list(_module(module).keys())


def transitions_possibles(module: str, etat: str) -> list[str]:
    etats = _module(module)
    if etat not in etats:
        raise ValueError(f"État inconnu pour {module} : {etat}")
    return list(etats[etat].suites)


def transition_autorisee(module: str, depuis: str, vers: str) -> bool:
    return vers in transitions_possibles(module, depuis)


# --- Phase : l'axe des filtres et des compteurs ---------------------------------------------------


def phase(module: str, etat: str) -> str:
    """Phase d'un statut : ``EN_COURS`` / ``TERMINE`` / ``ABANDONNE``.

    Un statut inconnu est traité comme en cours (prudence : on ne classe pas d'office un dossier
    parmi les affaires réglées).
    """
    etats = ETATS.get(module)
    if etats is None or etat not in etats:
        return EN_COURS
    return etats[etat].phase


def ton(module: str, etat: str) -> str:
    """Ton visuel d'un statut (couleur du badge), déclaré avec lui."""
    etats = ETATS.get(module)
    if etats is None or etat not in etats:
        return ACTIF
    return etats[etat].ton


def statuts_de_phase(*phases: str, module: str | None = None) -> list[str]:
    """Statuts appartenant à ces phases, pour un module ou pour tous (ordonnés, sans doublon).

    Sert aux requêtes SQL : plus aucune liste de statuts n'est écrite en dur ailleurs.
    """
    sources = [_module(module)] if module is not None else list(ETATS.values())
    retenus = {nom for etats in sources for nom, e in etats.items() if e.phase in phases}
    return sorted(retenus)


def est_termine(module: str, etat: str) -> bool:
    """Le dossier ne réclame plus de travail (abouti ou abandonné)."""
    return phase(module, etat) in PHASES_FINIES


# --- Verrou : « sans suite » = lecture seule (distinct de la phase) -------------------------------


def etats_terminaux(module: str) -> list[str]:
    """États sans suite possible : le dossier ne bouge plus du tout."""
    return [nom for nom, e in _module(module).items() if not e.suites]


def est_etat_terminal(module: str, etat: str) -> bool:
    """Vrai si l'état n'a plus aucune suite : l'activité est close (clôturé, rejeté, réalisé…).

    Signal de « lecture seule » : une activité dans un tel état ne se modifie plus (hors
    discussion, dossier RFC et liens). Un état inconnu est traité comme non terminal (prudence).

    À ne pas confondre avec la phase : « Résolu » est en phase ``TERMINE`` — il ne compte plus
    comme en cours — mais reste modifiable, puisqu'il peut être clôturé ou rouvert.
    """
    etats = ETATS.get(module)
    if etats is None or etat not in etats:
        return False
    return not etats[etat].suites


# --- Portes de validation ------------------------------------------------------------------------

# États où l'activité attend la décision des valideurs (approbation ITIL), avec la cible en cas
# d'approbation unanime et la cible en cas de rejet. Permet d'enchaîner automatiquement le workflow
# dès que les valideurs ont tranché (CAB/ECAB, validation de demande…).
# module -> (états en attente, cible si tous approuvent, cible si au moins un rejette)
GATES_VALIDATION: dict[str, tuple[frozenset[str], str, str]] = {
    "changement": (frozenset({"CAB", "ECAB"}), "Validé", "Rejeté"),
    "demande": (frozenset({"En validation"}), "Résolue", "Rejetée"),
    "audit": (frozenset({"En validation de clôture"}), "Clôturée", "En cours"),
}


def est_porte_validation(module: str, statut: str) -> bool:
    """Vrai si l'état attend la décision des valideurs (CAB/ECAB, validation de demande/clôture).

    Depuis un tel état, aucune transition manuelle n'est offerte : la sortie ne vient que de
    l'agrégation des décisions. L'écran s'en sert pour dire *pourquoi* rien n'avance.
    """
    gate = GATES_VALIDATION.get(module)
    return gate is not None and statut in gate[0]


def transition_reservee(module: str, depuis: str, vers: str) -> bool:
    """Vrai si la transition est une issue de validation, réservée à la décision des valideurs.

    L'approbation/le rejet en CAB/ECAB (et la validation d'une demande) ne se déclenchent pas
    manuellement : ils résultent de l'agrégation des décisions des valideurs. Empêche qu'un simple
    accès au module suffise à « valider » ou « rejeter » en poussant l'état à la main.
    """
    gate = GATES_VALIDATION.get(module)
    if gate is None:
        return False
    en_attente, cible_ok, cible_ko = gate
    return depuis in en_attente and vers in (cible_ok, cible_ko)


def cible_apres_decisions(module: str, statut: str, decisions: list[str | None]) -> str | None:
    """État cible après agrégation des décisions des valideurs, ou ``None`` si aucune bascule.

    Règles : au moins un ``REJETE`` → cible de rejet ; au moins un valideur et **tous** ``APPROUVE``
    → cible d'approbation ; sinon (décisions encore en attente, ou aucun valideur) → ``None``.
    La cible n'est retenue que si la transition est autorisée par la machine à états.
    """
    gate = GATES_VALIDATION.get(module)
    if gate is None:
        return None
    en_attente, cible_ok, cible_ko = gate
    if statut not in en_attente or not decisions:
        return None
    if any(d == "REJETE" for d in decisions):
        cible = cible_ko
    elif all(d == "APPROUVE" for d in decisions):
        cible = cible_ok
    else:
        return None
    return cible if transition_autorisee(module, statut, cible) else None
