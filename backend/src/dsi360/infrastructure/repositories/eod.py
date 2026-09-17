"""Repositories de l'EOD : le déroulé de référence (core.eod_modele_etape), les étapes réellement
pointées d'une soirée (core.eod_etape) et leur journal d'observations (core.eod_observation).

Même partage qu'entre un modèle de jalons et les jalons d'un projet : le modèle décrit ce qui se
fait tous les soirs, les étapes appartiennent à la soirée dès qu'elles sont posées. Corriger le
modèle ne réécrit donc jamais une nuit passée — c'est la propriété qui rend le rapport opposable.

Le journal, lui, ne s'écrit qu'en ajout : aucune fonction de mise à jour ni de suppression n'est
offerte ici. Ce n'est pas un oubli — une observation qui se corrige après coup ne prouve plus rien
(principe n° 4). L'erreur se rattrape par une observation suivante, qui la date et la signe.
"""

from typing import Any, cast

from sqlalchemy import CursorResult, RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

_CHAMPS = (
    "id::text AS id, section, libelle, nature, aide, ordre, statut, debut, fin, valeur, "
    "relance_de::text AS relance_de, agence"
)
_CHAMPS_MODELE = "id::text AS id, section, libelle, nature, aide, ordre, actif"

#: Champs qu'une mise à jour d'étape peut toucher. Tout le reste (section, libellé, nature) décrit
#: le déroulé et ne se retouche qu'en ajoutant ou en retirant une étape. Les observations n'y
#: figurent pas : elles s'ajoutent, elles ne se réécrivent jamais.
_MODIFIABLES = frozenset({"statut", "debut", "fin", "valeur", "ordre"})

#: L'auteur est rendu tel qu'il se lit — « Awa Touré » — et retombe sur l'e-mail figé à l'écriture
#: quand le compte a disparu : un journal dont les lignes perdent leur signataire ne prouve rien.
_CHAMPS_OBSERVATION = (
    "o.id::text AS id, o.etape_id::text AS etape_id, o.nature, o.agence, o.relance_le, o.texte, "
    "coalesce(u.prenom || ' ' || u.nom, o.auteur_email) AS auteur, o.cree_le"
)


# --- Déroulé de référence ------------------------------------------------------------------------


async def lister_modele(session: AsyncSession, *, actifs_seuls: bool = True) -> list[RowMapping]:
    clause = "WHERE actif" if actifs_seuls else ""
    lignes = await session.execute(
        text(f"SELECT {_CHAMPS_MODELE} FROM core.eod_modele_etape {clause} ORDER BY ordre, libelle")
    )
    return list(lignes.mappings().all())


async def poser_le_deroule(session: AsyncSession, activite_id: str) -> int:
    """Recopie le déroulé de référence sur une soirée **qui n'a aucune étape**. Renvoie le nombre.

    La garde « aucune étape » est la sécurité : relancer la pose sur une soirée déjà pointée
    doublerait les lignes et effacerait le travail de l'opérateur au milieu de sa nuit.
    """
    resultat = await session.execute(
        text(
            "INSERT INTO core.eod_etape (activite_id, section, libelle, nature, aide, ordre) "
            "SELECT cast(:a as uuid), m.section, m.libelle, m.nature, m.aide, m.ordre "
            "FROM core.eod_modele_etape m WHERE m.actif "
            "  AND NOT EXISTS (SELECT 1 FROM core.eod_etape e "
            "                  WHERE e.activite_id = cast(:a as uuid))"
        ),
        {"a": activite_id},
    )
    return int(cast(CursorResult[object], resultat).rowcount or 0)


# --- Étapes d'une soirée -------------------------------------------------------------------------


async def lister(session: AsyncSession, activite_id: str) -> list[RowMapping]:
    lignes = await session.execute(
        text(
            f"SELECT {_CHAMPS} FROM core.eod_etape WHERE activite_id = cast(:a as uuid) "
            # Une relance porte le rang de l'étape qu'elle rejoue : elle se range juste après
            # elle, sans renuméroter le déroulé, et deux relances se suivent dans l'ordre où
            # elles ont eu lieu.
            "ORDER BY ordre, (relance_de IS NOT NULL), cree_le"
        ),
        {"a": activite_id},
    )
    return list(lignes.mappings().all())


async def par_id(session: AsyncSession, etape_id: str, activite_id: str) -> RowMapping | None:
    resultat = await session.execute(
        text(
            f"SELECT {_CHAMPS} FROM core.eod_etape "
            "WHERE id = cast(:id as uuid) AND activite_id = cast(:a as uuid)"
        ),
        {"id": etape_id, "a": activite_id},
    )
    return resultat.mappings().first()


async def statuts(session: AsyncSession, activite_id: str) -> list[str]:
    """Les seuls statuts, pour calculer l'avancement sans rapatrier tout le déroulé."""
    lignes = await session.execute(
        text("SELECT statut FROM core.eod_etape WHERE activite_id = cast(:a as uuid)"),
        {"a": activite_id},
    )
    return [str(ligne[0]) for ligne in lignes.all()]


async def creer(session: AsyncSession, activite_id: str, champs: dict[str, Any]) -> RowMapping:
    """Ajoute une étape à une soirée. Sans rang donné, elle se range en fin de section."""
    ordre = champs.get("ordre")
    if ordre is None:
        ordre = await session.scalar(
            text(
                "SELECT coalesce(max(ordre), 0) + 1 FROM core.eod_etape "
                "WHERE activite_id = cast(:a as uuid)"
            ),
            {"a": activite_id},
        )
    ligne = (
        (
            await session.execute(
                text(
                    "INSERT INTO core.eod_etape "
                    "(activite_id, section, libelle, nature, aide, ordre, statut, debut, "
                    " relance_de, agence) "
                    "VALUES (cast(:a as uuid), :section, :libelle, :nature, :aide, :ordre, "
                    "        :statut, :debut, cast(:relance_de as uuid), :agence) "
                    f"RETURNING {_CHAMPS}"
                ),
                {
                    "a": activite_id,
                    "section": champs["section"],
                    "libelle": champs["libelle"],
                    "nature": champs.get("nature", "horaire"),
                    "aide": champs.get("aide"),
                    "ordre": ordre,
                    "statut": champs.get("statut", "À faire"),
                    "debut": champs.get("debut"),
                    "relance_de": champs.get("relance_de"),
                    "agence": champs.get("agence"),
                },
            )
        )
        .mappings()
        .one()
    )
    return ligne


async def maj(session: AsyncSession, etape_id: str, champs: dict[str, Any]) -> None:
    fixes = {c: v for c, v in champs.items() if c in _MODIFIABLES}
    if not fixes:
        return
    fragments = ", ".join(f"{c} = :{c}" for c in fixes)
    await session.execute(
        text(f"UPDATE core.eod_etape SET {fragments}, maj_le = now() WHERE id = cast(:id as uuid)"),
        {"id": etape_id, **fixes},
    )


async def supprimer(session: AsyncSession, etape_id: str) -> None:
    await session.execute(
        text("DELETE FROM core.eod_etape WHERE id = cast(:id as uuid)"), {"id": etape_id}
    )


async def agregats(session: AsyncSession, activite_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Ce que les étapes disent de chaque soirée, en **une** requête pour toute la page.

    Aller compter les étapes soirée par soirée ferait quinze requêtes pour afficher quinze lignes ;
    la liste s'alourdirait à mesure que la DSI garde ses nuits — exactement l'inverse du but.
    """
    if not activite_ids:
        return {}
    lignes = await session.execute(
        text(
            "SELECT activite_id::text AS id, count(*) AS total, "
            "  count(*) FILTER (WHERE statut IN ('Complété', 'Anomalie', 'Non applicable')) "
            "    AS regles, "
            "  min(debut) AS debut, max(fin) AS fin "
            "FROM core.eod_etape WHERE activite_id::text = ANY(:ids) "
            "GROUP BY activite_id"
        ),
        {"ids": activite_ids},
    )
    mesures = {
        str(ligne["id"]): {
            "nb_etapes": int(ligne["total"]),
            "reste": int(ligne["total"]) - int(ligne["regles"]),
            "anomalies": 0,
            "incidents": 0,
            "debut_effectif": ligne["debut"],
            "fin_effective": ligne["fin"],
        }
        for ligne in lignes.mappings().all()
    }
    # Les relances d'agence, dans la même passe : « combien d'agences ont bloqué cette nuit » est
    # la question qui suit immédiatement « combien d'anomalies ». Une anomalie peut tenir à un
    # batch et ne toucher aucune agence ; l'inverse existe aussi — une agence relancée sans que
    # l'étape finisse en anomalie. Les deux chiffres ne se déduisent pas l'un de l'autre.
    #
    # Les anomalies se comptent AU JOURNAL, pas sur le verdict des étapes : une étape finit, et
    # porte ses anomalies — parfois plusieurs. L'incident d'agence en est une, avec une agence et
    # une relance en plus ; il compte donc des deux côtés, à dessein.
    journal = await session.execute(
        text(
            "SELECT activite_id::text AS id, "
            "  count(*) FILTER (WHERE nature IN ('anomalie', 'incident')) AS anomalies, "
            "  count(*) FILTER (WHERE nature = 'incident') AS incidents "
            "FROM core.eod_observation WHERE activite_id::text = ANY(:ids) "
            "GROUP BY activite_id"
        ),
        {"ids": activite_ids},
    )
    for ligne in journal.mappings().all():
        mesure = mesures.get(str(ligne["id"]))
        if mesure is not None:
            mesure["anomalies"] = int(ligne["anomalies"])
            mesure["incidents"] = int(ligne["incidents"])
    return mesures


async def journee_existante(session: AsyncSession, journee: str) -> str | None:
    """Référence de la soirée déjà ouverte pour cette date, le cas échéant.

    Permet de refuser un doublon en le **nommant** — « EOD-2026-00042 couvre déjà cette nuit » —
    plutôt que de laisser remonter une violation d'index que personne ne sait interpréter.
    """
    reference = await session.scalar(
        text(
            "SELECT reference FROM core.activite "
            "WHERE module = 'eod' AND donnees ->> 'journee' = :j"
        ),
        {"j": journee},
    )
    return None if reference is None else str(reference)


# --- Le journal d'une étape ----------------------------------------------------------------------
#
# Append-only : ni `maj_observation`, ni `supprimer_observation`. Une observation qui se corrige
# après coup ne prouve plus rien — et c'est bien la preuve qu'on vient chercher au matin. Une
# erreur se rattrape par l'observation suivante, qui la date et la signe.


async def observations(session: AsyncSession, activite_id: str) -> list[RowMapping]:
    """Le journal de **toute** la soirée, en une requête.

    Le détail affiche les vingt-huit étapes d'un coup : interroger le journal étape par étape
    ferait vingt-huit requêtes pour ouvrir un écran. L'appelant regroupe par `etape_id`.
    """
    lignes = await session.execute(
        text(
            f"SELECT {_CHAMPS_OBSERVATION} FROM core.eod_observation o "
            "LEFT JOIN core.utilisateur u ON u.id = o.auteur_id "
            "WHERE o.activite_id = cast(:a as uuid) "
            # Par heure d'écriture : le journal raconte la nuit dans l'ordre où elle s'est vécue.
            # Trier sur `relance_le` remonterait une relance consignée en retard au milieu du fil.
            "ORDER BY o.cree_le, o.id"
        ),
        {"a": activite_id},
    )
    return list(lignes.mappings().all())


async def compter_observations(session: AsyncSession, etape_id: str) -> int:
    """Lignes au journal d'une étape : ce qui fait, ou non, la justification de son verdict."""
    total = await session.scalar(
        text("SELECT count(*) FROM core.eod_observation WHERE etape_id = cast(:e as uuid)"),
        {"e": etape_id},
    )
    return int(total or 0)


async def creer_observation(
    session: AsyncSession, *, etape_id: str, activite_id: str, champs: dict[str, Any]
) -> RowMapping:
    """Ajoute une ligne au journal d'une étape et la rend telle qu'elle se lira."""
    ligne = (
        (
            await session.execute(
                text(
                    "WITH nouvelle AS ("
                    "  INSERT INTO core.eod_observation "
                    "  (etape_id, activite_id, nature, agence, relance_le, texte, "
                    "   auteur_id, auteur_email) "
                    "  VALUES (cast(:e as uuid), cast(:a as uuid), :nature, :agence, :relance_le, "
                    "          :texte, cast(:auteur_id as uuid), :auteur_email) "
                    "  RETURNING *"
                    ") "
                    f"SELECT {_CHAMPS_OBSERVATION} FROM nouvelle o "
                    "LEFT JOIN core.utilisateur u ON u.id = o.auteur_id"
                ),
                {"e": etape_id, "a": activite_id, **champs},
            )
        )
        .mappings()
        .one()
    )
    return ligne


async def agences(session: AsyncSession) -> list[str]:
    """Le réseau d'agences de la banque, pour que la saisie d'un incident converge.

    On lit `core.emplacement` — la liste officielle des sites, déjà posée pour l'inventaire —
    plutôt que de tenir un second référentiel d'agences : deux listes du même réseau finiraient
    par diverger, et c'est exactement le désordre que la liste officielle a été posée pour éteindre.
    L'écran la **propose** sans l'imposer : le core banking nomme aussi des agences qui lui sont
    propres (« 000 BAM », « 000 BHO »), et une soirée ne doit pas s'arrêter faute de vocabulaire.
    """
    lignes = await session.execute(
        text("SELECT libelle FROM core.emplacement WHERE actif ORDER BY libelle")
    )
    return [str(ligne[0]) for ligne in lignes.all()]
