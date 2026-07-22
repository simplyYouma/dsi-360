"""Catalogue des modules (clés d'accès) et accès par défaut par profil (RBAC, cf. docs/04 §2).

Ces valeurs alimentent la table core.acces_role au seed ; elles restent **paramétrables** ensuite
depuis l'administration. Les actions sensibles (validation CAB/ECAB, clôture, paramétrage) sont
gardées en dur côté API, indépendamment de cette matrice.
"""

# Clés de modules (alignées sur la navigation du front).
MODULES: tuple[str, ...] = (
    "tableau-de-bord",
    "analyses",
    "incidents",
    "demandes",
    "projets",
    "changements",
    "audit",
    "risques",
    "cybersecurite",
    "gouvernance",
    # Parc matériel (immobilisations IT). Hors des neuf modules du cahier : ajout assumé.
    "inventaire",
    "administration",
)

# Profils métier de la DSI (code, libellé, transverse = voit au-delà de son périmètre), cf.
# docs/adr/0003. Ce n'est qu'un **point de départ** : l'administration crée, renomme et supprime
# des profils. Aucun code ne doit dépendre de cette liste — sauf ADMIN, protégé côté API.
PROFIL_ADMIN = "ADMIN"

PROFILS: tuple[tuple[str, str, bool], ...] = (
    (PROFIL_ADMIN, "Administrateur", True),
    ("SUPPORT_APP_HELPDESK", "IT Support Applicatif et HelpDesk", False),
    ("RESEAU_TELECOM", "Réseau télécom", False),
    ("SYSTEME_RESEAU_TELECOM", "Système et Réseau télécom", False),
    ("SUPPORT_APP", "IT Support Applicatif", False),
)

# Tout l'opérationnel, hors administration : le socle commun des profils métier. Ils se distinguent
# par leur périmètre de travail, et bientôt par leurs actions (ADR-0003 §4).
_OPERATIONNEL = [m for m in MODULES if m != "administration"]

# Accès par défaut : profil -> modules autorisés. Paramétrable ensuite depuis l'administration.
ACCES_PAR_PROFIL_DEFAUT: dict[str, list[str]] = {
    code: list(MODULES) if code == PROFIL_ADMIN else list(_OPERATIONNEL)
    for code, _, _ in PROFILS
}
