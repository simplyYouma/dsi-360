"""Module Incidents : routeur construit sur la fabrique commune d'activités."""

from dsi360.interface.routeurs.activites_communs import creer_routeur

routeur = creer_routeur(
    module="incident",
    acces="incidents",
    prefixe="/incidents",
    tag="incidents",
    import_uniquement=True,
    avec_documents=True,
    avec_escalade=True,
)
