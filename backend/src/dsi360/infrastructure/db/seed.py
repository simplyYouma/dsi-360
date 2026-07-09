"""Seed des référentiels et du compte administrateur initial. Idempotent (réexécutable).

Lancement : ``python -m dsi360.infrastructure.db.seed``.
"""

import asyncio

import asyncpg

from dsi360.config import get_settings
from dsi360.config.acces import ACCES_PAR_PROFIL_DEFAUT, PROFILS
from dsi360.infrastructure.securite import hacher_mot_de_passe

# La plateforme ne sert que la DSI (ADR-0003 §2). DBS reçoit les escalades N3, hors du système.
DIRECTIONS: list[tuple[str, str]] = [
    ("DSI", "Direction des Systèmes d'Information"),
]

# Catégories par défaut, par module (paramétrables ensuite).
CATEGORIES: dict[str, list[tuple[str, str]]] = {
    "incident": [
        ("RESEAU", "Réseau"),
        ("APPLICATIF", "Applicatif"),
        ("MATERIEL", "Matériel"),
        ("SECURITE", "Sécurité"),
    ],
    "demande": [
        ("COMPTE", "Création de compte"),
        ("HABILITATION", "Habilitations"),
        ("LOGICIEL", "Installation logicielle"),
        ("VPN", "Ouverture VPN"),
        ("MATERIEL", "Matériel informatique"),
        ("ASSISTANCE", "Assistance"),
    ],
    "changement": [("STANDARD", "Standard"), ("NORMAL", "Normal"), ("URGENT", "Urgent")],
    "audit": [
        ("GROUPE", "Audit Groupe"),
        ("INTERNE", "Audit Interne"),
        ("BCEAO", "BCEAO"),
        ("CP", "Contrôle Permanent"),
    ],
    "risque": [
        ("DISPO", "Disponibilité"),
        ("CONF", "Confidentialité"),
        ("INTEG", "Intégrité"),
    ],
    "cybersecurite": [
        ("HABILITATION", "Habilitation sensible"),
        ("COMPTE_ADMIN", "Compte administrateur"),
        ("REVUE_ACCES", "Revue d'accès"),
        ("VULNERABILITE", "Vulnérabilité"),
        ("CORRECTIF", "Correctif"),
        ("MFA", "MFA"),
        ("IAM", "Contrôle IAM"),
    ],
    "gouvernance": [
        ("COPIL", "COPIL"),
        ("COMITE", "Comité DSI"),
        ("DECISION_DG", "Décision DG"),
        ("ENGAGEMENT", "Engagement"),
        ("PLAN_ACTION", "Plan d'actions"),
    ],
}


def _dsn() -> str:
    return get_settings().database_url.replace("+asyncpg", "")


async def seed() -> None:
    s = get_settings()
    conn = await asyncpg.connect(_dsn())
    try:
        for code, libelle, transverse in PROFILS:
            await conn.execute(
                "INSERT INTO core.profil(code, libelle, transverse) VALUES ($1, $2, $3) "
                "ON CONFLICT (code) DO UPDATE SET libelle = excluded.libelle, "
                "transverse = excluded.transverse",
                code,
                libelle,
                transverse,
            )
        for code, libelle in DIRECTIONS:
            await conn.execute(
                "INSERT INTO core.direction(code, libelle) VALUES ($1, $2) "
                "ON CONFLICT (code) DO NOTHING",
                code,
                libelle,
            )
        for module, cats in CATEGORIES.items():
            for code, libelle in cats:
                await conn.execute(
                    "INSERT INTO core.categorie(module, code, libelle) VALUES ($1, $2, $3) "
                    "ON CONFLICT (module, code) DO NOTHING",
                    module,
                    code,
                    libelle,
                )
        for profil, modules in ACCES_PAR_PROFIL_DEFAUT.items():
            for acces in modules:
                await conn.execute(
                    "INSERT INTO core.acces_role(profil_code, acces) VALUES ($1, $2) "
                    "ON CONFLICT DO NOTHING",
                    profil,
                    acces,
                )

        existe = await conn.fetchval(
            "SELECT 1 FROM core.utilisateur WHERE email = $1", s.seed_admin_email
        )
        if existe is None:
            profil_id = await conn.fetchval("SELECT id FROM core.profil WHERE code = 'ADMIN'")
            direction_id = await conn.fetchval("SELECT id FROM core.direction WHERE code = 'DSI'")
            await conn.execute(
                "INSERT INTO core.utilisateur"
                "(email, nom, prenom, profil_id, direction_id, source_auth, mot_de_passe_hash, "
                "doit_changer_mdp) VALUES ($1, $2, $3, $4, $5, 'LOCAL', $6, true)",
                s.seed_admin_email,
                "Administrateur",
                "DSI 360",
                profil_id,
                direction_id,
                hacher_mot_de_passe(s.seed_admin_password),
            )
            print(f"Compte administrateur créé : {s.seed_admin_email}")
        else:
            print(f"Compte administrateur déjà présent : {s.seed_admin_email}")
        print("Seed terminé.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
