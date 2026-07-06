"""Module Gouvernance DSI : COPIL, comités, décisions DG, engagements, plans d'actions.

Cycle : À engager -> En cours -> Réalisé (+ Reporté).
"""

from dsi360.interface.routeurs.activites_communs import creer_routeur

routeur = creer_routeur(
    module="gouvernance",
    acces="gouvernance",
    prefixe="/gouvernance",
    tag="gouvernance",
    avec_documents=True,
    avec_revue=True,
)
