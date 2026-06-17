"""Détection des échéances SLA et création des notifications (interne + e-mail).

Scanne les activités non résolues / non clôturées dont l'échéance de résolution approche ou est
dépassée, et crée une notification (sans doublon, cf. index unique). Cf. docs/02 & 03.
"""

import asyncpg

from dsi360.config import get_settings
from dsi360.infrastructure.email import envoyer

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
