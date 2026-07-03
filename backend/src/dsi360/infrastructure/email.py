"""Envoi d'e-mails via SMTP (paramètres fournis par l'environnement, cf. infra/env/.env).

Sans hôte SMTP configuré, on journalise au lieu d'envoyer (mode dev). Tout échec d'envoi est
journalisé et n'interrompt jamais l'appelant (scanner SLA, flux d'auth…).
"""

import logging
import os
import smtplib
import ssl
import time
from email.message import EmailMessage
from pathlib import Path
from typing import cast

from dsi360.infrastructure.email_modeles import CID_LOGO

_log = logging.getLogger("dsi360.email")
_TENTATIVES = 2  # reprise sur échec transitoire (ex. résolution DNS intermittente)
_LOGO = Path(__file__).parent / "assets" / "logo-email.png"


def _logo_octets() -> bytes | None:
    try:
        return _LOGO.read_bytes()
    except OSError:
        return None


def _config() -> dict[str, str | int | bool]:
    utilisateur = os.environ.get("SMTP_UTILISATEUR", "")
    return {
        "hote": os.environ.get("SMTP_HOTE", ""),
        "port": int(os.environ.get("SMTP_PORT", "587") or 587),
        "utilisateur": utilisateur,
        "mot_de_passe": os.environ.get("SMTP_MOT_DE_PASSE", ""),
        "expediteur": os.environ.get("SMTP_EXPEDITEUR", "") or utilisateur,
        # SSL implicite (port 465) vs STARTTLS (port 587). Office365 = STARTTLS.
        "ssl": os.environ.get("SMTP_SECURE", "false").strip().lower() == "true",
        "tls": os.environ.get("SMTP_TLS", "true").strip().lower() == "true",
    }


def envoyer(destinataire: str, sujet: str, corps: str, html: str | None = None) -> None:
    """Envoie un e-mail (texte + HTML optionnel). Sans SMTP configuré : journalise (mode dev)."""
    cfg = _config()
    if not cfg["hote"]:
        _log.info("EMAIL (simulé, SMTP absent) -> %s | %s", destinataire, sujet)
        return

    message = EmailMessage()
    message["From"] = str(cfg["expediteur"])
    message["To"] = destinataire
    message["Subject"] = sujet
    message.set_content(corps)
    if html is not None:
        message.add_alternative(html, subtype="html")
        # Logo embarqué (Content-ID) : affiché dans le HTML via src="cid:logodsi360".
        logo = _logo_octets()
        if logo is not None:
            parties = cast(list[EmailMessage], message.get_payload())
            parties[1].add_related(logo, maintype="image", subtype="png", cid=f"<{CID_LOGO}>")

    contexte = ssl.create_default_context()
    for tentative in range(_TENTATIVES):
        try:
            if cfg["ssl"]:
                with smtplib.SMTP_SSL(
                    str(cfg["hote"]), int(cfg["port"]), context=contexte, timeout=15
                ) as serveur:
                    if cfg["utilisateur"]:
                        serveur.login(str(cfg["utilisateur"]), str(cfg["mot_de_passe"]))
                    serveur.send_message(message)
            else:
                with smtplib.SMTP(str(cfg["hote"]), int(cfg["port"]), timeout=15) as serveur:
                    serveur.ehlo()
                    if cfg["tls"]:
                        serveur.starttls(context=contexte)
                    if cfg["utilisateur"]:
                        serveur.login(str(cfg["utilisateur"]), str(cfg["mot_de_passe"]))
                    serveur.send_message(message)
            _log.info("EMAIL envoyé -> %s | %s", destinataire, sujet)
            return
        except Exception as exc:  # noqa: BLE001 - un échec d'e-mail ne casse jamais l'appelant
            if tentative + 1 < _TENTATIVES:
                time.sleep(1)
                continue
            _log.warning("EMAIL échec -> %s | %s : %s", destinataire, sujet, exc)
