"""Envoi d'e-mails (socle). Tant qu'aucun SMTP n'est configuré, on journalise au lieu d'envoyer.

Le branchement SMTP réel se fera ici quand la DSI fournira les paramètres (serveur, compte).
"""

import logging

_log = logging.getLogger("dsi360.email")


def envoyer(destinataire: str, sujet: str, corps: str) -> None:
    # TODO: brancher le SMTP (aiosmtplib) quand les paramètres seront fournis par la DSI.
    _log.info("EMAIL (simulé) -> %s | %s | %s", destinataire, sujet, corps)
