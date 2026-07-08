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


def _gestionnaire_id(cache: dict[str, str], nom: str | None) -> str | None:
    """Rattache le gestionnaire du ticket à un compte DSI EXISTANT (jamais de création).

    Le rapprochement se fait par nom normalisé (prénom nom / nom prénom). Si le nom n'appartient à
    aucun utilisateur du système (typiquement un agent DBS), on renvoie ``None`` : le nom brut reste
    conservé dans ``donnees.gestionnaire`` (affiché, non modifiable) et un contributeur DSI pourra
    prendre le relais. Les comptes se créent uniquement depuis l'administration.
    """
    if nom is None or nom.strip() == "":
        return None
    return cache.get(_norme(nom))


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
    # Ré-importation : on met à jour le cycle de vie (statut, priorité, échéances…) mais on NE
    # TOUCHE PAS à l'état saisi dans l'app — responsable_id (gestionnaire assigné) est préservé,
    # tout comme les commentaires et les contributeurs (tables séparées). Le gestionnaire du
    # rapport source reste consultable dans donnees.gestionnaire.
    "ON CONFLICT (module, source_id) WHERE source_id IS NOT NULL DO UPDATE SET "
    " titre = excluded.titre, categorie_id = excluded.categorie_id, "
    " demandeur_externe_id = excluded.demandeur_externe_id, "
    " priorite = excluded.priorite, statut = excluded.statut, "
    " pris_en_charge_le = excluded.pris_en_charge_le, resolu_le = excluded.resolu_le, "
    " cloture_le = excluded.cloture_le, donnees = excluded.donnees "
    # On ne met à jour QUE si une donnée a réellement changé : sinon, ligne « inchangée ».
    " WHERE (core.activite.titre, core.activite.statut, core.activite.priorite, "
    "        core.activite.categorie_id, core.activite.demandeur_externe_id, "
    "        core.activite.pris_en_charge_le, "
    "        core.activite.resolu_le, core.activite.cloture_le, core.activite.donnees) "
    " IS DISTINCT FROM "
    "       (excluded.titre, excluded.statut, excluded.priorite, excluded.categorie_id, "
    "        excluded.demandeur_externe_id, excluded.pris_en_charge_le, "
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
        responsable_id = _gestionnaire_id(cache_gest, gest)

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
