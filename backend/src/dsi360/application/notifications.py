"""Détection des échéances SLA et création des notifications (interne + e-mail).

Scanne les activités non résolues / non clôturées dont l'échéance de résolution approche ou est
dépassée, et crée une notification (sans doublon, cf. index unique). Cf. docs/02 & 03.
"""

import asyncpg
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.config import get_settings
from dsi360.infrastructure import audit, email_modeles
from dsi360.infrastructure.db import get_sessionmaker
from dsi360.infrastructure.email import envoyer


async def notifier(
    session: AsyncSession,
    *,
    destinataire_id: str | None,
    activite_id: str | None,
    type_: str,
    titre: str,
    message: str,
) -> None:
    """Notifie un destinataire (canal interne) et, selon sa préférence, par e-mail.

    Ne notifie pas si `destinataire_id` est vide. L'échec d'e-mail n'interrompt jamais l'appelant.
    """
    if not destinataire_id:
        return
    await session.execute(
        text(
            "INSERT INTO core.notification (destinataire_id, activite_id, type, titre, message) "
            "VALUES (cast(:d as uuid), cast(:a as uuid), :t, :ti, :m)"
        ),
        {"d": destinataire_id, "a": activite_id, "t": type_, "ti": titre, "m": message},
    )
    ligne = (
        await session.execute(
            text(
                "SELECT u.email, coalesce(p.email, true) AS envoyer_email "
                "FROM core.utilisateur u "
                "LEFT JOIN core.preference_notification p ON p.utilisateur_id = u.id "
                "WHERE u.id = cast(:d as uuid) AND u.actif"
            ),
            {"d": destinataire_id},
        )
    ).mappings().first()
    if ligne and ligne["envoyer_email"] and ligne["email"]:
        sujet, texte, html = email_modeles.notification_activite(
            titre, message, get_settings().url_app
        )
        envoyer(ligne["email"], sujet, texte, html)


async def notifier_acteurs(
    session: AsyncSession,
    *,
    activite_id: str,
    type_: str,
    titre: str,
    message: str,
    exclure_id: str | None = None,
) -> None:
    """Notifie tous les acteurs d'une activité (responsable + contributeurs + valideurs),
    sauf l'auteur de l'action (`exclure_id`) et sans doublon."""
    lignes = await session.execute(
        text(
            "SELECT DISTINCT uid FROM ("
            "  SELECT responsable_id AS uid FROM core.activite WHERE id = cast(:a as uuid)"
            "  UNION SELECT utilisateur_id FROM core.activite_acteur "
            "         WHERE activite_id = cast(:a as uuid)"
            ") s WHERE uid IS NOT NULL"
        ),
        {"a": activite_id},
    )
    for r in lignes.mappings().all():
        dest = str(r["uid"])
        if dest != (exclure_id or ""):
            await notifier(
                session, destinataire_id=dest, activite_id=activite_id,
                type_=type_, titre=titre, message=message,
            )

_SELECTION = """
    SELECT a.id::text AS id, a.reference, a.titre,
           coalesce(a.responsable_id, a.demandeur_id)::text AS destinataire_id,
           u.email AS destinataire_email,
           (a.sla_resolution_le <= now()) AS depasse
    FROM core.activite a
    LEFT JOIN core.utilisateur u ON u.id = coalesce(a.responsable_id, a.demandeur_id)
    WHERE a.resolu_le IS NULL AND a.cloture_le IS NULL
      AND a.sla_resolution_le IS NOT NULL
      AND a.sla_resolution_le <= now() + make_interval(hours => $1)
"""

_INSERT = """
    INSERT INTO core.notification(destinataire_id, activite_id, type, titre, message)
    VALUES (cast($1 as uuid), cast($2 as uuid), $3, $4, $5)
    ON CONFLICT DO NOTHING
"""


def _dsn() -> str:
    return get_settings().database_url.replace("+asyncpg", "")


async def scanner_echeances(fenetre_heures: int = 2) -> dict[str, int]:
    """Crée les notifications SLA dues. Retourne le nombre d'activités vues et de notifs créées."""
    conn = await asyncpg.connect(_dsn())
    crees = 0
    try:
        lignes = await conn.fetch(_SELECTION, fenetre_heures)
        for r in lignes:
            depasse = bool(r["depasse"])
            type_notif = "SLA_DEPASSE" if depasse else "SLA_APPROCHE"
            etat = "dépassé" if depasse else "en approche"
            titre = f"SLA {etat} — {r['reference']}"
            message = f"L'activité {r['reference']} « {r['titre']} » a son SLA {etat}."
            resultat = await conn.execute(
                _INSERT, r["destinataire_id"], r["id"], type_notif, titre, message
            )
            if resultat.endswith(" 1"):
                crees += 1
                if r["destinataire_email"]:
                    envoyer(r["destinataire_email"], titre, message)
    finally:
        await conn.close()
    return {"analysees": len(lignes), "crees": crees}


_P1_EN_RETARD = text(
    "SELECT a.id::text AS id, a.reference, a.titre, a.module, a.responsable_id::text AS resp "
    "FROM core.activite a "
    "WHERE a.priorite = 1 AND a.cloture_le IS NULL AND a.pris_en_charge_le IS NULL "
    "AND a.sla_prise_en_charge_le IS NOT NULL AND a.sla_prise_en_charge_le < now()"
)

_ADMIN_DEFAUT = text(
    "SELECT u.id::text FROM core.utilisateur u JOIN core.profil p ON p.id = u.profil_id "
    "WHERE p.code = 'ADMIN' AND u.actif ORDER BY u.cree_le LIMIT 1"
)

_INSERT_ESCALADE = text(
    "INSERT INTO core.notification (destinataire_id, activite_id, type, titre, message) "
    "VALUES (cast(:dest as uuid), cast(:aid as uuid), 'ESCALADE', :titre, :message) "
    "ON CONFLICT DO NOTHING RETURNING id"
)


async def scanner_tout() -> None:
    """Un passage complet de l'ordonnanceur : échéances SLA + escalades P1."""
    await scanner_echeances()
    await scanner_escalades()


async def scanner_escalades() -> dict[str, int]:
    """Escalade les tickets P1 non pris en charge dans les délais : alerte + journalisation.

    Cible le gestionnaire assigné, sinon un administrateur. Une seule escalade par ticket.
    """
    crees = 0
    async with get_sessionmaker()() as session:
        admin_defaut = await session.scalar(_ADMIN_DEFAUT)
        lignes = (await session.execute(_P1_EN_RETARD)).mappings().all()
        for r in lignes:
            destinataire = r["resp"] or admin_defaut
            if destinataire is None:
                continue
            titre = f"Escalade P1 — {r['reference']}"
            message = (
                f"Le ticket P1 {r['reference']} « {r['titre']} » n'a pas été pris en charge "
                "dans les délais."
            )
            nouvel_id = await session.scalar(
                _INSERT_ESCALADE,
                {"dest": destinataire, "aid": r["id"], "titre": titre, "message": message},
            )
            if nouvel_id is not None:
                crees += 1
                await audit.consigner(
                    session,
                    action="ESCALADE",
                    module=r["module"],
                    cible_type=r["module"],
                    cible_id=r["reference"],
                    nouvelle={"destinataire_id": destinataire, "motif": "P1 non pris en charge"},
                )
        await session.commit()
    return {"vues": len(lignes), "crees": crees}
