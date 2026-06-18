"""Module Cybersécurité : habilitations, comptes admin, vulnérabilités, MFA, IAM.

Cycle : Ouvert -> En traitement -> Corrigé -> Clôturé (+ Accepté / Réouvert).
"""

from dsi360.interface.routeurs.activites_communs import creer_routeur

routeur = creer_routeur(
    module="cybersecurite", acces="cybersecurite", prefixe="/cybersecurite", tag="cybersecurite"
)
