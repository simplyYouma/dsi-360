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
    "probleme": {
        "Nouveau": ["En cours d'analyse"],
        "En cours d'analyse": ["Résolu"],
        "Résolu": ["Clôturé", "Réouvert"],
        "Réouvert": ["En cours d'analyse"],
        "Clôturé": ["Réouvert"],
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
}


def etat_initial(module: str) -> str:
    """Premier état du cycle de vie d'un module (clé d'insertion d'ordre)."""
    etats = TRANSITIONS.get(module)
    if not etats:
        raise ValueError(f"Module inconnu : {module}")
    return next(iter(etats))


def transitions_possibles(module: str, etat: str) -> list[str]:
    etats = TRANSITIONS.get(module)
    if etats is None:
        raise ValueError(f"Module inconnu : {module}")
    if etat not in etats:
        raise ValueError(f"État inconnu pour {module} : {etat}")
    return etats[etat]


def transition_autorisee(module: str, depuis: str, vers: str) -> bool:
    return vers in transitions_possibles(module, depuis)
