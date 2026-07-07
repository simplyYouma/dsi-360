"""Machines à états par module (cycles de vie ITIL). Transitions par défaut, paramétrables ensuite.

Cf. docs/02-DOMAIN-MODEL §3. Une transition n'est autorisée que si l'état cible figure dans la
liste des suites possibles de l'état courant.
"""

# module -> { état: [états suivants autorisés] }
TRANSITIONS: dict[str, dict[str, list[str]]] = {
    "incident": {
        "Nouveau": ["Ouvert", "Annulé"],
        "Ouvert": ["Résolu", "Annulé"],
        "Résolu": ["Clôturé", "Réouvert"],
        "Réouvert": ["Ouvert", "Résolu"],
        "Clôturé": ["Réouvert"],
        "Annulé": [],
    },
    "demande": {
        "Nouvelle": ["Qualifiée", "Rejetée"],
        "Qualifiée": ["En cours", "Rejetée"],
        "En cours": ["En validation"],
        "En validation": ["Résolue", "Rejetée"],
        "Résolue": ["Clôturée", "Réouverte"],
        "Réouverte": ["En cours"],
        "Clôturée": ["Réouverte"],
        "Rejetée": [],
    },
    "changement": {
        "Brouillon": ["Soumis"],
        "Soumis": ["Évaluation"],
        "Évaluation": ["CAB", "ECAB"],
        "CAB": ["Validé", "Rejeté"],
        "ECAB": ["Validé", "Rejeté"],
        "Validé": ["Planifié"],
        "Planifié": ["En implémentation"],
        "En implémentation": ["Implémenté", "Retour arrière"],
        "Implémenté": ["Revue post-implémentation"],
        "Revue post-implémentation": ["Clôturé"],
        "Retour arrière": ["Clôturé"],
        "Rejeté": [],
        "Clôturé": [],
    },
    "projet": {
        "Cadrage": ["En cours"],
        "En cours": ["Suspendu", "Clôturé"],
        "Suspendu": ["En cours"],
        "Clôturé": [],
    },
    "audit": {
        "Ouverte": ["Plan d'action"],
        "Plan d'action": ["En cours"],
        "En cours": ["En validation de clôture"],
        "En validation de clôture": ["Clôturée", "En cours"],
        "Clôturée": [],
    },
    "risque": {
        "Identifié": ["Évalué"],
        "Évalué": ["Traitement"],
        "Traitement": ["Maîtrisé", "Accepté"],
        "Maîtrisé": ["Revue"],
        "Accepté": ["Revue"],
        "Revue": ["Traitement"],
    },
    "cybersecurite": {
        "Ouvert": ["En traitement", "Accepté"],
        "En traitement": ["Corrigé", "Accepté"],
        "Corrigé": ["Clôturé", "Réouvert"],
        "Accepté": ["Clôturé"],
        "Réouvert": ["En traitement"],
        "Clôturé": [],
    },
    "gouvernance": {
        "À engager": ["En cours"],
        "En cours": ["Réalisé", "Reporté"],
        "Reporté": ["En cours"],
        "Réalisé": [],
    },
}


def etat_initial(module: str) -> str:
    """Premier état du cycle de vie d'un module (clé d'insertion d'ordre)."""
    etats = TRANSITIONS.get(module)
    if not etats:
        raise ValueError(f"Module inconnu : {module}")
    return next(iter(etats))


def ordre_etats(module: str) -> list[str]:
    """Liste ordonnée des états du module (ordre chronologique du cycle de vie)."""
    etats = TRANSITIONS.get(module)
    if etats is None:
        raise ValueError(f"Module inconnu : {module}")
    return list(etats.keys())


# Statuts considérés « plus en cours » (réglé / rejeté / clôturé / annulé…), tous modules.
# Indépendant des transitions (un Clôturé reste « terminé » même si réouvrable).
STATUTS_TERMINAUX: frozenset[str] = frozenset(
    {
        "Résolu",
        "Résolue",
        "Clôturé",
        "Clôturée",
        "Annulé",
        "Rejeté",
        "Rejetée",
        "Réalisé",
        "Implémenté",
    }
)


def etats_terminaux(module: str) -> list[str]:
    """États sans suite possible (clôturé, rejeté, annulé…) : l'activité n'est plus en cours."""
    etats = TRANSITIONS.get(module)
    if etats is None:
        raise ValueError(f"Module inconnu : {module}")
    return [etat for etat, suites in etats.items() if not suites]


def transitions_possibles(module: str, etat: str) -> list[str]:
    etats = TRANSITIONS.get(module)
    if etats is None:
        raise ValueError(f"Module inconnu : {module}")
    if etat not in etats:
        raise ValueError(f"État inconnu pour {module} : {etat}")
    return etats[etat]


def transition_autorisee(module: str, depuis: str, vers: str) -> bool:
    return vers in transitions_possibles(module, depuis)


# Portes de validation : états où l'activité attend la décision des valideurs (approbation ITIL),
# avec la cible en cas d'approbation unanime et la cible en cas de rejet. Permet d'enchaîner
# automatiquement le workflow dès que les valideurs ont tranché (CAB/ECAB, validation de demande…).
# module -> (états en attente, cible si tous approuvent, cible si au moins un rejette)
GATES_VALIDATION: dict[str, tuple[frozenset[str], str, str]] = {
    "changement": (frozenset({"CAB", "ECAB"}), "Validé", "Rejeté"),
    "demande": (frozenset({"En validation"}), "Résolue", "Rejetée"),
    "audit": (frozenset({"En validation de clôture"}), "Clôturée", "En cours"),
}


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
