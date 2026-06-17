"""Catalogue des modules (clés d'accès) et accès par défaut par profil (RBAC, cf. docs/04 §2).

Ces valeurs alimentent la table core.acces_role au seed ; elles restent **paramétrables** ensuite
depuis l'administration. Les actions sensibles (validation CAB/ECAB, clôture, paramétrage) sont
gardées en dur côté API, indépendamment de cette matrice.
"""

# Clés de modules (alignées sur la navigation du front).
MODULES: tuple[str, ...] = (
    "tableau-de-bord",
    "incidents",
    "demandes",
    "projets",
    "changements",
    "audit",
    "risques",
    "cybersecurite",
    "gouvernance",
    "administration",
)

# Profils (code, libellé, transverse = voit au-delà de son périmètre).
PROFILS: tuple[tuple[str, str, bool], ...] = (
    ("ADMIN", "Administrateur", True),
    ("DSI", "DSI", True),
    ("CHEF_SERVICE", "Chef de Service", False),
    ("CHEF_PROJET", "Chef de Projet", False),
    ("TECHNICIEN", "Technicien", False),
    ("METIER", "Métier", False),
    ("DG", "Direction Générale", True),
)

# Accès par défaut : profil -> modules autorisés.
ACCES_PAR_PROFIL_DEFAUT: dict[str, list[str]] = {
    "ADMIN": list(MODULES),
    "DSI": [m for m in MODULES if m != "administration"],
    "CHEF_SERVICE": [
        "tableau-de-bord",
        "incidents",
        "demandes",
        "projets",
        "changements",
        "audit",
        "risques",
    ],
    "CHEF_PROJET": ["tableau-de-bord", "projets", "changements"],
    "TECHNICIEN": ["tableau-de-bord", "incidents", "demandes", "changements"],
    "METIER": ["tableau-de-bord", "demandes"],
    "DG": ["tableau-de-bord", "gouvernance", "audit", "risques"],
}
