"""Module Gouvernance : COPIL, comités, décisions DG, engagements, plans d'actions.

Cycle : À engager -> En cours -> Réalisé (+ Reporté).

Trois traits le distinguent des autres modules pilotés :

- il se **range par département** de la DSI (Production et Applicatif, Réseau et Infrastructure),
  ce qui sert à lire et à analyser, jamais à cloisonner les accès ;
- son **avancement se déclare à la main**, par le gestionnaire, avec justification obligatoire —
  contrairement aux projets et aux changements, où il se déduit des tâches terminées ;
- il porte ses **risques et impacts** en clair, deux textes plutôt qu'une cotation : un sujet de
  COPIL se raconte, il n'a pas la nature d'une fiche du registre des risques IT.
"""

from dsi360.interface.routeurs.activites_communs import creer_routeur

routeur = creer_routeur(
    module="gouvernance",
    acces="gouvernance",
    prefixe="/gouvernance",
    tag="gouvernance",
    avec_documents=True,
    avec_revue=True,
    avec_liens=True,
    # Éditable : c'est ce qui ouvre le PATCH, par lequel passent les risques et les impacts.
    editable=True,
    avec_departement=True,
    avec_avancement_manuel=True,
)
