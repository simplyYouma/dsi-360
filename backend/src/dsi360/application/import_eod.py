"""Charger une soirée EOD depuis le classeur du soir.

La nuit se pointe à l'écran quand la plateforme est sous la main, et dans le tableur de la banque
quand elle ne l'est pas. Retaper vingt-huit lignes au matin n'apporte rien et introduit des fautes :
on dépose le fichier, le pointage s'en déduit.

Trois règles, et la première est la plus importante :

* **l'import ne récrit jamais ce qui a été pointé.** Une étape déjà démarrée, terminée ou déclarée
  sans objet est laissée telle quelle, et comptée à part. C'est la leçon de l'import d'inventaire :
  un fichier qui reprend tout annule à chaque dépôt le travail fait à l'écran. Déposer deux fois le
  même classeur ne change donc rien la seconde fois ;
* **ce que le classeur ne sait pas dire, il ne le dit pas.** Une note du rapport devient une
  observation ordinaire, jamais une anomalie : le tableur ne distingue pas les deux, et deviner
  ferait apparaître des anomalies que personne n'a déclarées. L'opérateur requalifie d'un clic ;
* **une ligne non reconnue se montre.** Le déroulé de référence évolue ; un intitulé que le modèle
  ignore est rendu à l'écran plutôt que perdu en silence.
"""

from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.eod import ouvrir_journee, rafraichir_avancement
from dsi360.domain.eod import (
    A_FAIRE,
    COMPLETE,
    EN_COURS,
    MODULE,
    NON_APPLICABLE,
    NOTE,
    heure_de_la_nuit,
)
from dsi360.infrastructure import audit
from dsi360.infrastructure.ingestion_eod import (
    ClasseurEod,
    LigneClasseur,
    analyser_classeur,
    cle_intitule,
)
from dsi360.infrastructure.repositories import eod as eod_repo


class ClasseurSansJournee(ValueError):
    """Le classeur ne porte aucune date système : impossible de savoir quelle nuit il raconte."""


def _cle(section: Any, libelle: Any) -> tuple[str, str]:
    """Une étape se reconnaît au couple section + intitulé.

    L'intitulé seul ne suffit pas : « System Date » figure deux fois dans le déroulé — avant et
    après la bascule — et les confondre écraserait la date relevée en début de soirée par celle de
    la fin.
    """
    return cle_intitule(section), cle_intitule(libelle)


def _statut(ligne: LigneClasseur) -> str | None:
    """Le verdict que la ligne justifie, ou ``None`` si elle n'en porte pas.

    Jamais « Anomalie » : le classeur écrit ses remarques dans la même colonne que ses « Complete »,
    et rien n'y distingue un incident d'un commentaire. La note est importée, l'opérateur tranche.
    """
    if ligne.sans_objet:
        return NON_APPLICABLE
    if ligne.valeur is not None:
        return COMPLETE
    if ligne.fin is not None:
        return COMPLETE
    if ligne.debut is not None:
        return EN_COURS
    return None


def _intacte(etape: Any) -> bool:
    """Rien n'a encore été pointé sur cette étape : l'import peut la renseigner sans rien perdre."""
    return (
        etape["statut"] == A_FAIRE
        and etape["debut"] is None
        and etape["fin"] is None
        and not (etape["valeur"] or "").strip()
    )


async def _soiree_de(
    session: AsyncSession, journee: date, acteur: dict[str, Any]
) -> tuple[str, str, bool]:
    """L'identifiant et la référence de la soirée de cette journée — ouverte au besoin."""
    reference = await eod_repo.journee_existante(session, journee.isoformat())
    if reference is not None:
        identifiant = await session.scalar(
            text("SELECT id::text FROM core.activite WHERE reference = :r"), {"r": reference}
        )
        return str(identifiant), reference, False
    identifiant, reference, _ = await ouvrir_journee(
        session,
        journee=journee,
        categorie_id=None,
        direction_id=None,
        responsable_id=acteur["id"],
        impact=None,
        urgence=None,
        acteur=acteur,
    )
    return identifiant, reference, True


async def importer_classeur(
    session: AsyncSession, contenu: bytes, acteur: dict[str, Any]
) -> dict[str, Any]:
    """Charge le classeur d'une soirée. Retourne le compte-rendu affiché à l'écran."""
    classeur: ClasseurEod = analyser_classeur(contenu)
    if classeur.journee is None:
        raise ClasseurSansJournee(
            "Le classeur ne porte aucune date système : impossible de savoir quelle nuit il "
            "raconte. Renseignez la ligne « System Date » du rapport."
        )
    journee = classeur.journee
    identifiant, reference, creee = await _soiree_de(session, journee, acteur)

    etapes = {
        _cle(e["section"], e["libelle"]): e for e in await eod_repo.lister(session, identifiant)
    }
    deja = {
        (str(o["etape_id"]), cle_intitule(o["texte"]))
        for o in await eod_repo.observations(session, identifiant)
    }

    renseignees = conservees = observations = 0
    non_reconnues: list[str] = []

    for ligne in classeur.lignes:
        etape = etapes.get(_cle(ligne.section, ligne.libelle))
        if etape is None:
            non_reconnues.append(f"{ligne.section} · {ligne.libelle}")
            continue

        if _intacte(etape):
            champs: dict[str, Any] = {}
            statut = _statut(ligne)
            if statut is not None:
                champs["statut"] = statut
            if ligne.valeur is not None:
                champs["valeur"] = ligne.valeur.strftime("%d/%m/%Y")
            if ligne.debut is not None:
                champs["debut"] = heure_de_la_nuit(ligne.debut, journee)
            if ligne.fin is not None:
                champs["fin"] = heure_de_la_nuit(ligne.fin, journee)
            if champs:
                await eod_repo.maj(session, str(etape["id"]), champs)
                renseignees += 1
        else:
            conservees += 1

        # Une observation s'ajoute même sur une étape déjà pointée : le journal est append-only, il
        # ne perd rien. Mais pas deux fois la même, sinon redéposer le fichier doublerait le récit.
        if ligne.note is not None and (str(etape["id"]), cle_intitule(ligne.note)) not in deja:
            await eod_repo.creer_observation(
                session,
                etape_id=str(etape["id"]),
                activite_id=identifiant,
                champs={
                    "nature": NOTE,
                    "agence": None,
                    "relance_le": None,
                    "texte": ligne.note,
                    "auteur_id": acteur["id"],
                    "auteur_email": acteur["email"],
                },
            )
            observations += 1

    await rafraichir_avancement(session, identifiant)
    compte_rendu = {
        "journee": journee.isoformat(),
        "reference": reference,
        "soiree_id": identifiant,
        "creee": creee,
        "etapes_renseignees": renseignees,
        "etapes_conservees": conservees,
        "observations_ajoutees": observations,
        "lignes_non_reconnues": non_reconnues,
    }
    await audit.consigner(
        session,
        action="IMPORT",
        acteur_id=acteur["id"],
        acteur_email=acteur["email"],
        module=MODULE,
        cible_type=MODULE,
        cible_id=reference,
        nouvelle=compte_rendu,
    )
    return compte_rendu
