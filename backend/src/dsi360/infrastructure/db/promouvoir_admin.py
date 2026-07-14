"""Crée ou promeut un compte **administrateur**, avec mot de passe défini directement.

Sert à ouvrir l'accès administrateur sans dépendre de l'e-mail : utile au premier démarrage, ou
quand le relais SMTP n'est pas encore branché (aucun lien d'activation ne partirait). Contrairement
aux comptes ordinaires — créés sans mot de passe, activés par lien — ici l'exploitant fixe lui-même
le mot de passe, en conscience, sur la machine.

- Compte inexistant  → créé, profil ADMIN, direction DSI, mot de passe posé, actif.
- Compte existant    → promu ADMIN, réactivé, mot de passe redéfini.
Dans les deux cas ``doit_changer_mdp = false`` : l'exploitant vient de choisir le mot de passe, on
ne le force pas à le rechanger à la première connexion.

Usage (depuis infra\\local, config chargée par env.ps1) :
    python -m dsi360.infrastructure.db.promouvoir_admin --email a.b@afgbank.ml
    python -m dsi360.infrastructure.db.promouvoir_admin --email a.b@afgbank.ml --mot-de-passe ...

Sans ``--mot-de-passe``, il est demandé sans écho (jamais dans l'historique du terminal).
"""

import argparse
import asyncio
import getpass
import sys

import asyncpg

from dsi360.config import get_settings
from dsi360.infrastructure.securite import hacher_mot_de_passe

_MDP_MIN = 8


def _dsn() -> str:
    return get_settings().database_url.replace("+asyncpg", "")


async def promouvoir(email: str, mot_de_passe: str) -> None:
    email = email.strip().lower()
    conn = await asyncpg.connect(_dsn())
    try:
        profil_id = await conn.fetchval("SELECT id FROM core.profil WHERE code = 'ADMIN'")
        if profil_id is None:
            print("REFUS : le profil ADMIN est absent. Lancez d'abord les migrations (migrer.ps1).")
            sys.exit(1)
        direction_id = await conn.fetchval("SELECT id FROM core.direction WHERE code = 'DSI'")
        empreinte = hacher_mot_de_passe(mot_de_passe)

        existant = await conn.fetchval(
            "SELECT id FROM core.utilisateur WHERE lower(email) = $1", email
        )
        if existant is None:
            await conn.execute(
                "INSERT INTO core.utilisateur "
                "(email, nom, prenom, profil_id, direction_id, source_auth, mot_de_passe_hash, "
                " doit_changer_mdp, actif) "
                "VALUES ($1, 'Administrateur', 'DSI 360', $2, $3, 'LOCAL', $4, false, true)",
                email, profil_id, direction_id, empreinte,
            )
            print(f"Compte administrateur CRÉÉ : {email}")
        else:
            await conn.execute(
                "UPDATE core.utilisateur "
                "SET profil_id = $2, mot_de_passe_hash = $3, doit_changer_mdp = false, "
                "    actif = true, echecs_connexion = 0, verrouille_jusqu_a = NULL "
                "WHERE id = $1",
                existant, profil_id, empreinte,
            )
            print(f"Compte PROMU administrateur : {email}")
    finally:
        await conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Crée ou promeut un administrateur DSI 360.")
    ap.add_argument("--email", required=True, help="E-mail du compte administrateur.")
    ap.add_argument("--mot-de-passe", help="Mot de passe (sinon demandé sans écho).")
    args = ap.parse_args()

    mdp = args.mot_de_passe or getpass.getpass("Nouveau mot de passe administrateur : ")
    if len(mdp) < _MDP_MIN:
        print(f"REFUS : mot de passe trop court (au moins {_MDP_MIN} caractères).")
        sys.exit(1)
    if args.mot_de_passe is None:
        if mdp != getpass.getpass("Confirmez le mot de passe : "):
            print("REFUS : les deux saisies diffèrent.")
            sys.exit(1)

    asyncio.run(promouvoir(args.email, mdp))
    print("Terminé. Vous pouvez vous connecter avec cet e-mail et ce mot de passe.")


if __name__ == "__main__":
    main()
