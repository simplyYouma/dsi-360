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
    "administration",
)

# Profils (code, libellé, transverse = voit au-delà de son périmètre). Tous les utilisateurs sont
# de la DSI ; le Gestionnaire traite les activités, la DG a une vue de restitution.
PROFILS: tuple[tuple[str, str, bool], ...] = (
    ("ADMIN", "Administrateur", True),
    ("DSI", "DSI", True),
    ("GESTIONNAIRE", "Gestionnaire", False),
    ("DG", "Direction Générale", True),
)

# Accès par défaut : profil -> modules autorisés.
ACCES_PAR_PROFIL_DEFAUT: dict[str, list[str]] = {
    "ADMIN": list(MODULES),
    "DSI": [m for m in MODULES if m != "administration"],
    # Le gestionnaire traite tout l'opérationnel (hors administration).
    "GESTIONNAIRE": [m for m in MODULES if m != "administration"],
    "DG": ["tableau-de-bord", "analyses", "gouvernance", "audit", "risques"],
}
