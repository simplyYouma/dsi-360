"""Envoi d'e-mails via SMTP (paramètres fournis par l'environnement, cf. infra/env/.env).

Sans hôte SMTP configuré — ou hors production, quel que soit le relais — on journalise le message
au lieu de l'envoyer : une base de démonstration ne doit écrire à personne. Tout échec d'envoi est
journalisé et n'interrompt jamais l'appelant (scanner SLA, flux d'auth…).

L'envoi est **asynchrone** (fil d'arrière-plan) : l'e-mail est best-effort et ne doit jamais
ralentir ni geler l'application — en particulier en **mode hors ligne** (réseau interne sans
Internet), où chaque tentative SMTP peut bloquer ~15 s. Un disjoncteur suspend en plus les envois
pendant quelques minutes après une panne réseau ; le canal interne (cloche) reste garanti.
"""

import logging
import os
import smtplib
import ssl
import threading
import time
from email.message import EmailMessage
from pathlib import Path
from typing import Any, cast

from dsi360.config import get_settings
from dsi360.infrastructure.email_modeles import CID_LOGO

_log = logging.getLogger("dsi360.email")
_TENTATIVES = 2  # reprise sur échec transitoire (ex. résolution DNS intermittente)
_LOGO = Path(__file__).parent / "assets" / "logo-email.png"

# Disjoncteur hors ligne : après une panne SMTP, on n'essaie plus pendant ce délai (les envois
# sont ignorés et journalisés) pour ne pas empiler des fils bloqués quand Internet est absent.
_PANNE_PAUSE_S = 120.0
_panne_jusqua = 0.0
_verrou = threading.Lock()


def _logo_octets() -> bytes | None:
    try:
        return _LOGO.read_bytes()
    except OSError:
        return None


def _envoi_autorise() -> bool:
    """Hors production, rien ne part — même avec un relais SMTP configuré.

    Un jeu de démonstration recrée des centaines d'assignations et de rappels : autant d'e-mails
    vers de vraies boîtes, envoyés par une base de test. La garde se lève avec
    `DSI360_EMAIL_REEL_HORS_PROD=true`, le temps de vérifier le relais de bout en bout.
    """
    reglages = get_settings()
    return reglages.environnement == "prod" or reglages.email_reel_hors_prod


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
    """Envoie un e-mail (texte + HTML optionnel), en arrière-plan — ne bloque jamais l'appelant.

    Sans SMTP configuré : journalise (mode dev). Pendant une panne réseau (disjoncteur ouvert) :
    ignore l'envoi et journalise — l'application reste pleinement utilisable hors ligne.
    """
    if not _envoi_autorise():
        # Le corps est journalisé : c'est ainsi qu'on récupère un lien d'activation en dev,
        # sans qu'aucun message ne quitte la machine.
        _log.info(
            "EMAIL (simulé, hors production) -> %s | %s\n%s", destinataire, sujet, corps[:600]
        )
        return
    cfg = _config()
    if not cfg["hote"]:
        _log.info("EMAIL (simulé, SMTP absent) -> %s | %s", destinataire, sujet)
        return
    if time.time() < _panne_jusqua:
        _log.info("EMAIL ignoré (SMTP en panne / hors ligne) -> %s | %s", destinataire, sujet)
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

    threading.Thread(
        target=_envoyer_sync, args=(cfg, message, destinataire, sujet), daemon=True
    ).start()


def _envoyer_sync(
    cfg: dict[str, Any], message: EmailMessage, destinataire: str, sujet: str
) -> None:
    """Transmission SMTP réelle (dans un fil dédié). Ouvre le disjoncteur en cas d'échec final."""
    global _panne_jusqua
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
            with _verrou:
                _panne_jusqua = time.time() + _PANNE_PAUSE_S
            _log.warning(
                "EMAIL échec -> %s | %s : %s (envois suspendus %.0f s)",
                destinataire, sujet, exc, _PANNE_PAUSE_S,
            )
