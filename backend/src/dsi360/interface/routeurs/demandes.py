"""Module Demandes de service : routeur construit sur la fabrique commune d'activités."""

from dsi360.interface.routeurs.activites_communs import creer_routeur

routeur = creer_routeur(
    module="demande",
    acces="demandes",
    prefixe="/demandes",
    tag="demandes",
    import_uniquement=True,
)
