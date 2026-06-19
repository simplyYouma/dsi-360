"""Jeu de données de démonstration varié : utilisateurs + activités sur tous les modules.

Idempotent côté utilisateurs (ON CONFLICT). Les activités sont ajoutées à chaque exécution
(références incrémentales), avec statuts / priorités / SLA / dates étalés pour que les écrans
(tableau de bord, analyses, listes, notifications) montrent des données réalistes.

Lancement : ``python -m dsi360.infrastructure.db.donnees_demo``.
"""

import asyncio
import json
import random
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg

from dsi360.config import get_settings
from dsi360.domain.activite import PREFIXE_REFERENCE, calculer_criticite, calculer_priorite
from dsi360.infrastructure.securite import hacher_mot_de_passe

random.seed(42)

UTILISATEURS = [
    ("a.toure@afgbank.ml", "Touré", "Aïcha", "DSI", "DSI"),
    ("m.diallo@afgbank.ml", "Diallo", "Moussa", "TECHNICIEN", "EXPLOIT"),
    ("f.keita@afgbank.ml", "Keïta", "Fanta", "CHEF_SERVICE", "DSI"),
    ("o.sanogo@afgbank.ml", "Sanogo", "Oumar", "CHEF_PROJET", "DSI"),
    ("k.coulibaly@afgbank.ml", "Coulibaly", "Kadia", "METIER", "METIER"),
    ("s.traore@afgbank.ml", "Traoré", "Salif", "DSI", "DG"),
]

TITRES: dict[str, list[str]] = {
    "incident": [
        "Panne messagerie Exchange", "Lenteur application OAS", "Coupure réseau agence Niaréla",
        "Échec sauvegarde nocturne", "Imprimante guichet HS", "Saturation disque serveur SI",
        "Erreur batch interbancaire", "Accès VPN instable", "Téléphonie IP en panne",
        "Indisponibilité Payway",
    ],
    "demande": [
        "Création compte agent", "Habilitation module crédit", "Installation antivirus poste",
        "Ouverture VPN prestataire", "Nouveau poste de travail", "Assistance Excel reporting",
        "Réinitialisation mot de passe", "Accès partage RH",
    ],
    "changement": [
        "Mise à jour pare-feu", "Migration base PostgreSQL", "Déploiement correctif core banking",
        "Bascule lien opérateur", "Montée de version OAS", "Changement certificat TLS",
    ],
    "audit": [
        "Renforcer la revue des accès", "Tracer les opérations sensibles", "Plan reprise à formaliser",
        "Cloisonner les environnements", "Chiffrer les sauvegardes", "Revue des comptes dormants",
    ],
    "risque": [
        "Indisponibilité datacenter", "Fuite de données clients", "Dépendance fournisseur unique",
        "Obsolescence d'un applicatif", "Cyberattaque par rançongiciel", "Perte de compétence clé",
    ],
    "cybersecurite": [
        "Revue des comptes administrateurs", "Vulnérabilité critique serveur web", "Activation MFA agences",
        "Habilitation sensible à valider", "Correctif système d'exploitation", "Contrôle IAM trimestriel",
    ],
    "gouvernance": [
        "COPIL trimestriel DSI", "Comité sécurité mensuel", "Décision DG budget cloud",
        "Engagement sur les SLA", "Plan d'actions audit BCEAO",
    ],
    "projet": [
        "Migration cœur bancaire", "Refonte du portail agences", "Déploiement MFA groupe",
        "Datacenter de secours (PRA)", "Dématérialisation des dossiers crédit",
        "Mise en conformité BCEAO", "Modernisation du réseau interagences",
        "Nouveau SI décisionnel", "Migration messagerie cloud", "Refonte du site institutionnel",
        "Centralisation de la sauvegarde", "Automatisation des rapprochements",
    ],
}

STATUTS: dict[str, list[str]] = {
    "incident": ["Nouveau", "Ouvert", "Ouvert", "Résolu", "Clôturé", "Annulé", "Réouvert"],
    "demande": ["Nouvelle", "Qualifiée", "En cours", "En cours", "En validation", "Résolue", "Clôturée", "Rejetée"],
    "changement": ["Brouillon", "Soumis", "Évaluation", "CAB", "Validé", "Planifié", "En implémentation", "Implémenté", "Clôturé"],
    "audit": ["Ouverte", "Plan d'action", "En cours", "En cours", "En validation de clôture", "Clôturée"],
    "risque": ["Identifié", "Évalué", "Traitement", "Maîtrisé", "Accepté", "Revue"],
    "cybersecurite": ["Ouvert", "En traitement", "En traitement", "Corrigé", "Clôturé", "Accepté"],
    "gouvernance": ["À engager", "En cours", "En cours", "Réalisé", "Reporté"],
    "projet": ["Cadrage", "En cours", "En cours", "Suspendu", "Clôturé"],
}

TERMINAUX = {"Clôturé", "Clôturée", "Résolu", "Résolue", "Annulé", "Rejeté", "Réalisé"}
SPONSORS = ["Direction Générale", "DSI", "Direction des Risques", "Direction Métier"]


def _dsn() -> str:
    return get_settings().database_url.replace("+asyncpg", "")


async def _assurer_utilisateurs(conn: asyncpg.Connection) -> list[str]:
    empreinte = hacher_mot_de_passe("changez-moi")
    for email, nom, prenom, profil, direction in UTILISATEURS:
        await conn.execute(
            "INSERT INTO core.utilisateur"
            "(email, nom, prenom, profil_id, direction_id, source_auth, mot_de_passe_hash, "
            " doit_changer_mdp) VALUES ($1,$2,$3,"
            " (SELECT id FROM core.profil WHERE code=$4),"
            " (SELECT id FROM core.direction WHERE code=$5),'LOCAL',$6,false) "
            "ON CONFLICT (email) DO NOTHING",
            email, nom, prenom, profil, direction, empreinte,
        )
    return [r["id"] for r in await conn.fetch("SELECT id FROM core.utilisateur")]


async def _categories(conn: asyncpg.Connection, module: str) -> list[str]:
    return [r["id"] for r in await conn.fetch(
        "SELECT id FROM core.categorie WHERE module=$1", module
    )]


async def creer_donnees() -> None:
    maintenant = datetime.now(UTC)
    annee = maintenant.year
    conn = await asyncpg.connect(_dsn())
    total = 0
    try:
        utilisateurs = await _assurer_utilisateurs(conn)
        directions = [r["code"] for r in await conn.fetch("SELECT code FROM core.direction")]
        demandeur = utilisateurs[0]

        for module, titres in TITRES.items():
            prefixe = PREFIXE_REFERENCE[module]
            base = await conn.fetchval(
                "SELECT count(*) FROM core.activite WHERE module=$1 AND reference LIKE $2",
                module, f"{prefixe}-{annee}-%",
            )
            cats = await _categories(conn, module)
            seq = base or 0
            for titre in titres:
                # Idempotence : on ne recrée pas un libellé déjà présent pour ce module.
                deja = await conn.fetchval(
                    "SELECT 1 FROM core.activite WHERE module=$1 AND titre=$2 LIMIT 1",
                    module, titre,
                )
                if deja:
                    continue
                seq += 1
                reference = f"{prefixe}-{annee}-{seq:05d}"
                statut = random.choice(STATUTS[module])
                impact = random.randint(1, 5)
                urgence = random.randint(1, 5)
                cree_le = maintenant - timedelta(days=random.randint(0, 55), hours=random.randint(0, 23))

                donnees: dict[str, Any]
                if module == "risque":
                    priorite = None
                    donnees = {
                        "probabilite": impact,
                        "impact": urgence,
                        "criticite": calculer_criticite(impact, urgence),
                    }
                elif module == "projet":
                    priorite = None
                    donnees = {
                        "sponsor": random.choice(SPONSORS),
                        "budget": random.choice(
                            [5_000_000, 8_500_000, 15_000_000, 25_000_000, 42_000_000,
                             60_000_000, 90_000_000, 120_000_000]
                        ),
                        "date_debut": cree_le.date().isoformat(),
                        "date_fin": (cree_le + timedelta(days=random.randint(60, 240))).date().isoformat(),
                        "avancement": random.choice([0, 10, 25, 40, 55, 70, 85, 100]),
                    }
                else:
                    priorite = calculer_priorite(impact, urgence)
                    donnees = {}

                terminal = statut in TERMINAUX
                # SLA réparti : passé (dépassé), proche (approche), futur (à l'heure).
                if terminal:
                    sla_res = cree_le + timedelta(hours=random.choice([4, 8, 48]))
                    resolu = cree_le + timedelta(days=random.randint(1, 5))
                    cloture = resolu
                else:
                    choix = random.random()
                    if choix < 0.3:
                        sla_res = maintenant - timedelta(hours=random.randint(1, 48))
                    elif choix < 0.5:
                        sla_res = maintenant + timedelta(minutes=random.randint(15, 110))
                    else:
                        sla_res = maintenant + timedelta(days=random.randint(1, 6))
                    resolu = None
                    cloture = None

                await conn.execute(
                    "INSERT INTO core.activite"
                    "(reference, module, titre, description, direction_id, categorie_id, "
                    " demandeur_id, responsable_id, impact, urgence, priorite, statut, "
                    " sla_prise_en_charge_le, sla_resolution_le, cree_le, resolu_le, cloture_le, donnees)"
                    " VALUES ($1,$2,$3,$4,"
                    " (SELECT id FROM core.direction WHERE code=$5),"
                    " $6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18::jsonb)",
                    reference, module, titre, "Donnée de démonstration.",
                    random.choice(directions),
                    random.choice(cats) if cats and module not in ("projet",) else None,
                    demandeur, random.choice(utilisateurs),
                    impact if module not in ("projet",) else None,
                    urgence if module not in ("projet",) else None,
                    priorite, statut,
                    cree_le + timedelta(minutes=30) if not terminal else None,
                    sla_res, cree_le, resolu, cloture, json.dumps(donnees),
                )
                total += 1
        print(f"{total} activités de démonstration créées.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(creer_donnees())
