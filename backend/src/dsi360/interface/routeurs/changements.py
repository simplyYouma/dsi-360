"""Module Changements (ITIL) : routeur sur la fabrique commune. Cycle RFC -> CAB/ECAB -> clôture."""

from dsi360.interface.routeurs.activites_communs import creer_routeur

routeur = creer_routeur(
    module="changement",
    acces="changements",
    prefixe="/changements",
    tag="changements",
    avec_taches=True,
    avec_documents=True,
    editable=True,
)
