"""Ingestion du rapport quotidien de tickets : réconciliation + upsert idempotent.

Pour chaque ligne : on reconnaît (ou crée) le demandeur (agent de la banque), on rattache le
gestionnaire à un compte DSI si le nom correspond, on garantit la catégorie, puis on upserte
l'activité par (module, n° de ticket). Recharger le même fichier met à jour, ne duplique pas.
"""

import json
import unicodedata
from datetime import timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.domain.activite import PREFIXE_REFERENCE
from dsi360.domain.texte import nom_propre, phrase_propre
from dsi360.infrastructure import audit
from dsi360.infrastructure.ingestion import analyser_classeur


def _norme(nom: str) -> str:
    base = " ".join(str(nom or "").strip().lower().split())
    return "".join(c for c in unicodedata.normalize("NFKD", base) if not unicodedata.combining(c))


async def _index_gestionnaires(session: AsyncSession) -> dict[str, str]:
    """Nom normalisé (prénom nom et nom prénom) -> id utilisateur, pour rattacher le gestionnaire."""
    requete = text("SELECT id::text, prenom, nom FROM core.utilisateur")
    lignes = (await session.execute(requete)).all()
    index: dict[str, str] = {}
    for ident, prenom, nom in lignes:
        index[_norme(f"{prenom} {nom}")] = ident
        index[_norme(f"{nom} {prenom}")] = ident
    return index


_CREER_AGENT = text(
    "INSERT INTO core.utilisateur "
    "(email, nom, prenom, profil_id, direction_id, source_auth, doit_changer_mdp) VALUES ("
    " :email, :nom, :prenom, "
    " (SELECT id FROM core.profil WHERE code = 'TECHNICIEN'), "
    " (SELECT id FROM core.direction WHERE code = 'DSI'), 'LOCAL', true) "
    "ON CONFLICT (email) DO NOTHING RETURNING id::text"
)


async def _gestionnaire_id(session: AsyncSession, cache: dict[str, str], nom: str | None) -> str | None:
    """Le gestionnaire EST un agent DSI : on rattache au compte existant, sinon on le crée.

    Source unique : les utilisateurs et les gestionnaires des tickets désignent les mêmes personnes.
    """
    if nom is None or nom.strip() == "":
        return None
    cle = _norme(nom)
    if cle in cache:
        return cache[cle]
    parts = (nom_propre(nom) or nom).split()
    prenom = parts[0]
    nom_famille = " ".join(parts[1:]) or parts[0]
    email = f"{cle.replace(' ', '.')}@afgbank.ml"
    ident = await session.scalar(_CREER_AGENT, {"email": email, "nom": nom_famille, "prenom": prenom})
    if ident is None:  # email déjà pris (homonyme/slug identique) : on récupère le compte
        ident = await session.scalar(
            text("SELECT id::text FROM core.utilisateur WHERE email = :e"), {"e": email}
        )
    cache[cle] = str(ident)
    return str(ident)


async def _demandeur_id(session: AsyncSession, cache: dict[str, str], nom: str | None) -> str | None:
    if nom is None or nom.strip() == "":
        return None
    cle = _norme(nom)
    if cle in cache:
        return cache[cle]
    ident = await session.scalar(
        text(
            "INSERT INTO core.demandeur (nom_complet) VALUES (:nom) "
            "ON CONFLICT (lower(nom_complet)) DO UPDATE SET maj_le = now() "
            "RETURNING id::text"
        ),
        {"nom": nom_propre(nom)},
    )
    cache[cle] = str(ident)
    return str(ident)


def libelle_propre(valeur: str) -> str:
    """Réécriture lisible : espaces normalisés + initiale de chaque mot en majuscule."""
    return " ".join(valeur.split()).title()


async def _categorie_id(
    session: AsyncSession, cache: dict[str, str], module: str, libelle: str | None
) -> str | None:
    if libelle is None or libelle.strip() == "":
        return None
    # Reconnaissance insensible à la casse via le code (majuscules) ; libellé proprement réécrit.
    code = " ".join(libelle.split()).upper()[:60]
    cle = f"{module}:{code}"
    if cle in cache:
        return cache[cle]
    ident = await session.scalar(
        text(
            "INSERT INTO core.categorie (module, code, libelle) VALUES (:m, :c, :l) "
            "ON CONFLICT (module, code) DO UPDATE SET libelle = excluded.libelle "
            "RETURNING id::text"
        ),
        {"m": module, "c": code, "l": libelle_propre(libelle)},
    )
    cache[cle] = str(ident)
    return str(ident)


_UPSERT = text(
    "INSERT INTO core.activite "
    "(reference, module, titre, categorie_id, demandeur_externe_id, responsable_id, "
    " priorite, statut, cree_le, pris_en_charge_le, resolu_le, cloture_le, donnees, source, source_id) "
    "VALUES (:reference, :module, :titre, cast(:categorie_id as uuid), "
    " cast(:demandeur_externe_id as uuid), cast(:responsable_id as uuid), "
    " :priorite, :statut, :cree_le, :pris_en_charge_le, :resolu_le, :cloture_le, "
    " cast(:donnees as jsonb), 'IMPORT_SD', :source_id) "
    "ON CONFLICT (module, source_id) WHERE source_id IS NOT NULL DO UPDATE SET "
    " titre = excluded.titre, categorie_id = excluded.categorie_id, "
    " demandeur_externe_id = excluded.demandeur_externe_id, responsable_id = excluded.responsable_id, "
    " priorite = excluded.priorite, statut = excluded.statut, "
    " pris_en_charge_le = excluded.pris_en_charge_le, resolu_le = excluded.resolu_le, "
    " cloture_le = excluded.cloture_le, donnees = excluded.donnees "
    # On ne met à jour QUE si une donnée a réellement changé : sinon, ligne « inchangée ».
    " WHERE (core.activite.titre, core.activite.statut, core.activite.priorite, "
    "        core.activite.categorie_id, core.activite.demandeur_externe_id, "
    "        core.activite.responsable_id, core.activite.pris_en_charge_le, "
    "        core.activite.resolu_le, core.activite.cloture_le, core.activite.donnees) "
    " IS DISTINCT FROM "
    "       (excluded.titre, excluded.statut, excluded.priorite, excluded.categorie_id, "
    "        excluded.demandeur_externe_id, excluded.responsable_id, excluded.pris_en_charge_le, "
    "        excluded.resolu_le, excluded.cloture_le, excluded.donnees) "
    # cree=True => insertion ; cree=False => mise à jour ; aucune ligne => inchangée.
    "RETURNING (xmax = 0) AS cree"
)


async def importer_tickets(
    session: AsyncSession, contenu: bytes, acteur: dict[str, Any]
) -> dict[str, Any]:
    tickets = analyser_classeur(contenu)
    cache_gest = await _index_gestionnaires(session)  # comptes existants -> évite les doublons
    cache_dem: dict[str, str] = {}
    cache_cat: dict[str, str] = {}

    crees = maj = inchanges = 0
    par_module = {"incident": 0, "demande": 0}
    demandeurs_avant = await session.scalar(text("SELECT count(*) FROM core.demandeur")) or 0
    agents_avant = await session.scalar(text("SELECT count(*) FROM core.utilisateur")) or 0

    for t in tickets:
        gest = t["gestionnaire"]
        responsable_id = await _gestionnaire_id(session, cache_gest, gest)

        donnees = {
            "sous_categorie": t["sous_categorie"],
            "gestionnaire": gest,
            "demandeur": t["demandeur"],
            "ttr_minutes": t["ttr_minutes"],
            "ttrespond_minutes": t["ttrespond_minutes"],
        }
        cree_le = t["date_demande"]
        pris = (
            cree_le + timedelta(minutes=t["ttrespond_minutes"])
            if cree_le is not None and t["ttrespond_minutes"]
            else None
        )
        resolu = t["date_fermeture"] if t["issue"] in ("resolu", "cloture") else None
        cloture = t["date_fermeture"] if t["issue"] == "cloture" else None

        cree = await session.scalar(
            _UPSERT,
            {
                "reference": f"{PREFIXE_REFERENCE[t['module']]}-{t['source_id']}",
                "module": t["module"],
                "titre": phrase_propre(t["titre"]),
                "categorie_id": await _categorie_id(session, cache_cat, t["module"], t["categorie"]),
                "demandeur_externe_id": await _demandeur_id(session, cache_dem, t["demandeur"]),
                "responsable_id": responsable_id,
                "priorite": t["priorite"],
                "statut": t["statut"],
                "cree_le": cree_le,
                "pris_en_charge_le": pris,
                "resolu_le": resolu,
                "cloture_le": cloture,
                "donnees": json.dumps(donnees),
                "source_id": t["source_id"],
            },
        )
        if cree is None:
            inchanges += 1
        elif cree:
            crees += 1
        else:
            maj += 1
        par_module[t["module"]] += 1

    apres_dem = await session.scalar(text("SELECT count(*) FROM core.demandeur")) or 0
    apres_agents = await session.scalar(text("SELECT count(*) FROM core.utilisateur")) or 0
    demandeurs_crees = apres_dem - demandeurs_avant
    gestionnaires_crees = apres_agents - agents_avant

    await audit.consigner(
        session,
        action="IMPORT",
        acteur_id=acteur["id"],
        acteur_email=acteur["email"],
        module="ingestion",
        cible_type="rapport_tickets",
        cible_id=f"{len(tickets)} tickets",
        nouvelle={
            "crees": crees,
            "mis_a_jour": maj,
            "inchanges": inchanges,
            "demandeurs_crees": demandeurs_crees,
            "gestionnaires_crees": gestionnaires_crees,
        },
    )
    await session.commit()

    return {
        "total": len(tickets),
        "incidents": par_module["incident"],
        "demandes": par_module["demande"],
        "crees": crees,
        "mis_a_jour": maj,
        "inchanges": inchanges,
        "demandeurs_crees": demandeurs_crees,
        "gestionnaires_crees": gestionnaires_crees,
    }
