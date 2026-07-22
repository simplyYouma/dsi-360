"""Ingestion du rapport quotidien de tickets : réconciliation + upsert idempotent.

Pour chaque ligne : on reconnaît (ou crée) le demandeur (agent de la banque), on rattache le
gestionnaire à un compte DSI si le nom correspond, on garantit la catégorie, puis on upserte
l'activité par (module, n° de ticket). Recharger le même fichier met à jour, ne duplique pas.
"""

import json
import unicodedata
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.domain.activite import PREFIXE_REFERENCE
from dsi360.domain.sla import CiblesSla, echeances
from dsi360.domain.texte import nom_propre, nom_significatif, phrase_propre
from dsi360.infrastructure import audit
from dsi360.infrastructure.ingestion import analyser_classeur
from dsi360.infrastructure.repositories import sla as sla_repo


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
    aucun utilisateur du système, c'est un agent DBS : on renvoie ``None``, le ticket n'a donc pas
    de responsable chez nous et se lit en N3 (ADR-0005). Le nom brut reste affiché depuis
    ``donnees.gestionnaire``. Les comptes se créent uniquement depuis l'administration.
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
    " priorite, statut, cree_le, pris_en_charge_le, resolu_le, cloture_le, "
    " sla_prise_en_charge_le, sla_resolution_le, donnees, source, source_id) "
    "VALUES (:reference, :module, :titre, cast(:categorie_id as uuid), "
    " cast(:demandeur_externe_id as uuid), cast(:responsable_id as uuid), "
    " :priorite, :statut, :cree_le, :pris_en_charge_le, :resolu_le, :cloture_le, "
    " :sla_prise_en_charge_le, :sla_resolution_le, "
    " cast(:donnees as jsonb), 'IMPORT_SD', :source_id) "
    # Ré-importation : le fichier fait autorité. Ces tickets sont traités dans un autre système ;
    # DSI 360 en reflète l'état. Le gestionnaire suit donc le rapport — un compte DSI si le nom est
    # rapproché, personne sinon (le ticket est chez DBS). Les commentaires, contributeurs et
    # documents vivent dans des tables séparées : ils ne sont jamais touchés.
    "ON CONFLICT (module, source_id) WHERE source_id IS NOT NULL DO UPDATE SET "
    " titre = excluded.titre, categorie_id = excluded.categorie_id, "
    " demandeur_externe_id = excluded.demandeur_externe_id, "
    " responsable_id = excluded.responsable_id, "
    " priorite = excluded.priorite, statut = excluded.statut, "
    " pris_en_charge_le = excluded.pris_en_charge_le, resolu_le = excluded.resolu_le, "
    " cloture_le = excluded.cloture_le, "
    " sla_prise_en_charge_le = excluded.sla_prise_en_charge_le, "
    " sla_resolution_le = excluded.sla_resolution_le, donnees = excluded.donnees "
    # On ne met à jour QUE si une donnée a réellement changé : sinon, ligne « inchangée ».
    # Les échéances SLA entrent dans la comparaison : sinon un ticket que le rapport ne fait plus
    # bouger resterait sans échéance pour toujours.
    " WHERE (core.activite.titre, core.activite.statut, core.activite.priorite, "
    "        core.activite.categorie_id, core.activite.demandeur_externe_id, "
    "        core.activite.responsable_id, core.activite.pris_en_charge_le, "
    "        core.activite.resolu_le, core.activite.cloture_le, core.activite.donnees, "
    "        core.activite.sla_prise_en_charge_le, core.activite.sla_resolution_le) "
    " IS DISTINCT FROM "
    "       (excluded.titre, excluded.statut, excluded.priorite, excluded.categorie_id, "
    "        excluded.demandeur_externe_id, excluded.responsable_id, excluded.pris_en_charge_le, "
    "        excluded.resolu_le, excluded.cloture_le, excluded.donnees, "
    "        excluded.sla_prise_en_charge_le, excluded.sla_resolution_le) "
    # cree=True => insertion ; cree=False => mise à jour ; aucune ligne => inchangée.
    "RETURNING (xmax = 0) AS cree"
)

# État connu avant l'import, pour ne journaliser que ce qui bouge (le rapport est réimporté chaque
# jour, l'écrasante majorité des lignes est identique).
_ETATS_CONNUS = text(
    "SELECT module, source_id, statut FROM core.activite "
    "WHERE source = 'IMPORT_SD' AND source_id IS NOT NULL"
)


async def _statuts_avant(session: AsyncSession) -> dict[tuple[str, str], str]:
    lignes = (await session.execute(_ETATS_CONNUS)).all()
    return {(module, source_id): statut for module, source_id, statut in lignes}


def _echeances_sla(
    matrice: dict[int, CiblesSla], priorite: int | None, cree_le: datetime | None
) -> tuple[datetime | None, datetime | None]:
    """Échéances d'un ticket importé. Sans priorité ni date, aucun engagement : on n'invente pas."""
    if priorite is None or cree_le is None:
        return None, None
    try:
        ech = echeances(int(priorite), cree_le, matrice)
    except ValueError:
        return None, None
    return ech.prise_en_charge_le, ech.resolution_le


async def importer_tickets(
    session: AsyncSession, contenu: bytes, acteur: dict[str, Any]
) -> dict[str, Any]:
    tickets = analyser_classeur(contenu)
    cache_gest = await _index_gestionnaires(session)  # comptes existants -> jamais de création
    # Un ticket importé porte une priorité : il porte donc un engagement. Les échéances SLA se
    # calculent ici, sinon la fiche afficherait « Échéance — » et aucun retard ne serait mesurable.
    matrices: dict[str, dict[int, CiblesSla]] = {
        m: await sla_repo.charger_matrice(session, m) for m in ("incident", "demande")
    }
    cache_dem: dict[str, str] = {}
    cache_cat: dict[str, str] = {}
    statuts_avant = await _statuts_avant(session)

    crees = maj = inchanges = 0
    par_module = {"incident": 0, "demande": 0}
    # Libellés de statut que la table ne connaît pas : repliés sur « ouvert », mais SIGNALÉS —
    # c'est la cause silencieuse de tickets clos à la source restés « en cours » chez nous.
    statuts_inconnus: set[str] = set()
    demandeurs_avant = await session.scalar(text("SELECT count(*) FROM core.demandeur")) or 0
    agents_avant = await session.scalar(text("SELECT count(*) FROM core.utilisateur")) or 0

    for t in tickets:
        # « None », « N/A », « - »… ne sont pas des gestionnaires : le ticket reste non renseigné,
        # et n'est donc pas compté chez DBS. Un import ultérieur qui renseigne le nom corrigera.
        gest = nom_significatif(t["gestionnaire"])
        responsable_id = _gestionnaire_id(cache_gest, gest)
        if t["statut_inconnu"]:
            statuts_inconnus.add(t["statut_inconnu"])
        reference = f"{PREFIXE_REFERENCE[t['module']]}-{t['source_id']}"
        statut_avant = statuts_avant.get((t["module"], t["source_id"]))

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
        sla_pec, sla_res = _echeances_sla(matrices[t["module"]], t["priorite"], cree_le)

        cree = await session.scalar(
            _UPSERT,
            {
                "reference": reference,
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
                "sla_prise_en_charge_le": sla_pec,
                "sla_resolution_le": sla_res,
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

        # Le cycle de vie de ces tickets ne vient que du fichier : sans cette trace, l'historique
        # d'une fiche resterait vide et aucune statistique de durée par statut ne serait possible.
        # On ne consigne que ce qui bouge — le rapport est réimporté chaque jour à l'identique.
        if cree:
            await audit.consigner(
                session,
                action="CREATION",
                acteur_id=acteur["id"],
                acteur_email=acteur["email"],
                module=t["module"],
                cible_type=t["module"],
                cible_id=reference,
                nouvelle={"statut": t["statut"], "source": "IMPORT_SD"},
            )
        elif cree is False and statut_avant is not None and statut_avant != t["statut"]:
            await audit.consigner(
                session,
                action="TRANSITION",
                acteur_id=acteur["id"],
                acteur_email=acteur["email"],
                module=t["module"],
                cible_type=t["module"],
                cible_id=reference,
                ancienne={"statut": statut_avant},
                nouvelle={"statut": t["statut"], "source": "IMPORT_SD"},
            )

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
            "statuts_inconnus": len(statuts_inconnus),
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
        "statuts_non_reconnus": sorted(statuts_inconnus),
    }
