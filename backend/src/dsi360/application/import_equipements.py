"""Import du fichier d'inventaire : chargement initial et mises à jour comptables.

**La règle d'or.** Le fichier vient de la comptabilité, mais la DSI enrichit le parc à l'écran
(n° de série, modèle, emplacement, détenteur). Un réimport qui écraserait tout annulerait ce
travail à chaque fois. On distingue donc deux familles de colonnes :

- **comptables** — code immo, désignation, taux, date et valeur d'acquisition, durée :
  la comptabilité fait foi, l'import les **écrase** ;
- **terrain** — n° de série, modèle, emplacement, département, matricule :
  la DSI fait foi, l'import ne les remplit **que si elles sont vides**.

Ainsi un emplacement corrigé à la main survit au réimport, tandis qu'une réévaluation comptable
remonte bien. Idempotence par code d'immobilisation : réimporter le même fichier ne crée jamais
de doublon.
"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.inventaire import detenteur_pour, index_matricules
from dsi360.domain.texte import nom_significatif, phrase_propre
from dsi360.infrastructure import audit
from dsi360.infrastructure.ingestion_equipements import analyser_classeur
from dsi360.infrastructure.repositories import campagne as repo_campagne
from dsi360.infrastructure.repositories import equipement as repo

#: La comptabilité fait foi : ces colonnes sont toujours reprises du fichier.
_COMPTABLES = ("designation", "taux", "date_acquisition", "duree_annees", "valeur_acquisition")
#: La DSI fait foi : l'import ne comble que les trous, il n'écrase jamais une saisie.
_TERRAIN = ("numero_serie", "modele", "emplacement_id", "departement_id", "matricule_brut")


async def importer_classeur(
    session: AsyncSession, contenu: bytes, acteur: dict[str, Any]
) -> dict[str, Any]:
    """Charge le classeur. Retourne le compte-rendu affiché à l'écran."""
    lignes = analyser_classeur(contenu)
    cache_matricules = await index_matricules(session)
    # Une campagne ouverte : les croix bon/rebut/casse du fichier deviennent des constats.
    # Sans campagne, elles sont seulement comptées — un état hors campagne ne se rattache à rien.
    campagne = await repo_campagne.ouverte(session)

    crees = maj = ignores = 0
    sans_detenteur = 0
    avec_etat = 0
    constats = 0
    for ligne in lignes:
        code = nom_significatif(ligne["code_immo"])
        if code is None:
            # Sans code d'immobilisation, aucune clé pour reconnaître la ligne d'un import à
            # l'autre : on ne peut ni la créer sans risque de doublon, ni la retrouver ensuite.
            ignores += 1
            continue
        if ligne["etat_constate"] is not None:
            avec_etat += 1

        matricule = nom_significatif(ligne["matricule"])
        detenteur = detenteur_pour(cache_matricules, matricule)
        if matricule is not None and detenteur is None:
            sans_detenteur += 1

        emplacement_id = await repo.trouver_ou_creer_referentiel(
            session, "emplacements", nom_significatif(ligne["emplacement"])
        )
        departement_id = await repo.trouver_ou_creer_referentiel(
            session, "departements", nom_significatif(ligne["departement"])
        )

        comptables = {
            "designation": phrase_propre(ligne["designation"]),
            "taux": ligne["taux"],
            "date_acquisition": ligne["date_acquisition"],
            "duree_annees": ligne["duree_annees"],
            "valeur_acquisition": ligne["valeur_acquisition"],
        }
        terrain = {
            "numero_serie": nom_significatif(ligne["numero_serie"]),
            "modele": nom_significatif(ligne["modele"]),
            "emplacement_id": emplacement_id,
            "departement_id": departement_id,
            "matricule_brut": matricule,
        }

        existant = await repo.par_code_immo(session, code)
        if existant is None:
            equipement_id = await repo.creer(
                session,
                {
                    "code_immo": code.upper(),
                    **comptables,
                    **terrain,
                    "detenteur_id": detenteur,
                    "source": "IMPORT_IMMO",
                },
            )
            crees += 1
        else:
            equipement_id = str(existant["id"])
            champs: dict[str, Any] = dict(comptables)
            # Règle d'or : on ne remplit une colonne de terrain que si elle est vide.
            for colonne, valeur in terrain.items():
                if valeur is not None and existant[colonne] is None:
                    champs[colonne] = valeur
            # Le détenteur suit la même règle : un rattachement fait à la main ne se défait pas.
            if detenteur is not None and existant["detenteur_id"] is None:
                champs["detenteur_id"] = detenteur
            await repo.maj(session, existant["id"], champs)
            maj += 1

        # NON_RETROUVE ne vient jamais du fichier : il se déduit à la clôture de la campagne.
        if campagne is not None and ligne["etat_constate"] in repo_campagne.ETATS_SAISIE:
            await repo_campagne.poser_constat(
                session, campagne["id"], equipement_id, ligne["etat_constate"], acteur["id"]
            )
            constats += 1

    await audit.consigner(
        session,
        action="IMPORT",
        acteur_id=acteur["id"],
        acteur_email=acteur["email"],
        module="inventaire",
        cible_type="equipement",
        cible_id="inventaire",
        nouvelle={
            "lus": len(lignes),
            "crees": crees,
            "mis_a_jour": maj,
            "ignores": ignores,
            "constats_enregistres": constats,
        },
    )
    await session.commit()
    return {
        "total": len(lignes),
        "crees": crees,
        "mis_a_jour": maj,
        "ignores": ignores,
        "detenteurs_non_rapproches": sans_detenteur,
        "avec_etat_constate": avec_etat,
        "constats_enregistres": constats,
    }


async def compter_equipements(session: AsyncSession) -> int:
    """Effectif du parc — pour situer l'import dans son contexte."""
    return int(await session.scalar(text("SELECT count(*) FROM core.equipement")) or 0)
