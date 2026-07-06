"""Module Audit & Recommandations : routeur sur la fabrique commune.

Cycle : Ouverte -> Plan d'action -> En cours -> En validation de clôture -> Clôturée.
La « source » (Audit Groupe, Interne, BCEAO, Contrôle Permanent…) est portée par la catégorie.
"""

from dsi360.interface.routeurs.activites_communs import creer_routeur

routeur = creer_routeur(
    module="audit", acces="audit", prefixe="/audit", tag="audit", avec_documents=True
)
