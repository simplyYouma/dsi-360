"""Création des notifications (canal interne + e-mail) et escalade des P1 non pris en charge.

`notifier` est le point de passage unique : il écrit la notification interne ET décide de
l'e-mail (compte actif, préférence de l'agent, canal activé). Les rappels d'échéance, eux, vivent
dans `application/echeances`. Cf. docs/02 & 03.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.config import get_settings
from dsi360.domain.activite import lien_activite
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
    courriel: tuple[str, str, str] | None = None,
) -> None:
    """Notifie un destinataire (canal interne) et, selon sa préférence, par e-mail.

    ``courriel`` — (sujet, texte, html) déjà composé : permet à un appelant d'utiliser un gabarit
    dédié (alerte SLA, rappel d'échéance) plutôt que le gabarit générique. La règle d'envoi, elle,
    reste ici : compte actif, préférence e-mail, canal activé. Un seul endroit en décide.

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
    if get_settings().notif_email_active and ligne and ligne["envoyer_email"] and ligne["email"]:
        # Le bouton mène AU dossier concerné, pas à l'accueil : une notification qui oblige à
        # chercher le ticket a manqué son but. Le module est lu sur l'activité, donc aucun
        # appelant n'a à le fournir — et aucun ne peut l'oublier.
        sujet, texte, html = courriel or email_modeles.notification_activite(
            titre, message, await _lien_du_dossier(session, activite_id), type_
        )
        envoyer(ligne["email"], sujet, texte, html)


async def _lien_du_dossier(session: AsyncSession, activite_id: str | None) -> str:
    """Lien profond vers le dossier ; repli sur l'accueil si l'activité n'est pas identifiable."""
    accueil = get_settings().url_app
    if not activite_id:
        return accueil
    module = await session.scalar(
        text("SELECT module FROM core.activite WHERE id = cast(:a as uuid)"),
        {"a": activite_id},
    )
    if module is None:
        return accueil
    return lien_activite(accueil, str(module), activite_id) or accueil


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


async def scanner_tout() -> None:
    """Un passage complet de l'ordonnanceur : rappels d'échéance + escalades P1.

    Les rappels (SLA, tâches, jalons, fins de projet, revues) passent tous par le même scanner,
    avec trois paliers chacun — cf. `application/echeances`. Il remplace les anciens
    `scanner_echeances`, `scanner_revues` et `scanner_jalons`, qui n'alertaient qu'une fois et
    ignoraient les tâches comme les fins de projet.
    """
    # Import local : `echeances` importe `notifier` d'ici, un import en tête serait circulaire.
    from dsi360.application.echeances import scanner_rappels

    await scanner_rappels()
    await scanner_escalades()


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

_EMAIL_DEST = text(
    "SELECT u.email, coalesce(p.email, true) AS envoyer_email "
    "FROM core.utilisateur u "
    "LEFT JOIN core.preference_notification p ON p.utilisateur_id = u.id "
    "WHERE u.id = cast(:d as uuid) AND u.actif"
)


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
                # L'escalade P1 est critique : elle part aussi par e-mail (comme les autres notifs).
                dest_email = (
                    await session.execute(_EMAIL_DEST, {"d": destinataire})
                ).mappings().first()
                if (
                    get_settings().notif_email_active
                    and dest_email
                    and dest_email["envoyer_email"]
                    and dest_email["email"]
                ):
                    sujet, texte_mail, html = email_modeles.escalade_p1(
                        reference=r["reference"],
                        titre_activite=r["titre"],
                        url=lien_activite(get_settings().url_app, r["module"], r["id"]),
                    )
                    envoyer(dest_email["email"], sujet, texte_mail, html)
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
