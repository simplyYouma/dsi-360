"""Aperçu de lien (unfurl) pour la discussion — façon messagerie.

Le serveur récupère la page cible et en extrait titre/description/image (OpenGraph), afin que le
front affiche une vignette. Récupération **strictement encadrée** (anti-SSRF) : schéma http(s)
uniquement, hôtes privés/loopback/réservés refusés (y compris après redirection), délai et taille
bornés. Réservé aux comptes authentifiés — jamais un proxy ouvert.
"""

import html
import ipaddress
import re
import socket
from typing import Annotated, Any
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import APIRouter, Depends, Query

from dsi360.interface.schemas import ApercuLien
from dsi360.interface.securite import utilisateur_courant

routeur = APIRouter(prefix="/apercu-lien", tags=["apercu"])
Courant = Annotated[dict[str, Any], Depends(utilisateur_courant)]

_DELAI = httpx.Timeout(4.0, connect=3.0)
_TAILLE_MAX = 256 * 1024  # on ne lit que le début de la page : les balises <head> suffisent.
_MAX_REDIR = 4
# Cache borné en mémoire (sans TTL) : une même URL n'est récupérée qu'une fois par cycle de vie.
_CACHE: dict[str, dict[str, str | None]] = {}
_CACHE_MAX = 512


def _hote_autorise(hote: str) -> bool:
    """Vrai si l'hôte ne résout que vers des adresses publiques (bloque le SSRF)."""
    try:
        infos = socket.getaddrinfo(hote, None)
    except OSError:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False
    return True


def _meta(corps: str, cles: tuple[str, ...]) -> str | None:
    """Extrait le premier <meta property|name="cle" content="..."> trouvé pour l'une des clés."""
    for cle in cles:
        motif = (
            r'<meta[^>]+(?:property|name)=["\']'
            + re.escape(cle)
            + r'["\'][^>]+content=["\']([^"\']*)["\']'
        )
        m = re.search(motif, corps, re.IGNORECASE)
        if m is None:
            # L'ordre des attributs peut être inversé (content avant property).
            motif2 = (
                r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']'
                + re.escape(cle)
                + r'["\']'
            )
            m = re.search(motif2, corps, re.IGNORECASE)
        if m is not None and m.group(1).strip() != "":
            return html.unescape(m.group(1).strip())
    return None


async def _recuperer(url: str) -> str | None:
    """Suit jusqu'à `_MAX_REDIR` redirections en validant chaque hôte ; renvoie le HTML ou None."""
    async with httpx.AsyncClient(
        timeout=_DELAI, follow_redirects=False, headers={"User-Agent": "DSI360-Apercu/1.0"}
    ) as client:
        courant = url
        for _ in range(_MAX_REDIR):
            hote = urlparse(courant).hostname
            if hote is None or not _hote_autorise(hote):
                return None
            reponse = await client.get(courant)
            if reponse.is_redirect:
                cible = reponse.headers.get("location")
                if cible is None:
                    return None
                courant = urljoin(courant, cible)
                continue
            type_contenu = reponse.headers.get("content-type", "")
            if "html" not in type_contenu.lower():
                return None
            return reponse.text[:_TAILLE_MAX]
    return None


@routeur.get("", response_model=ApercuLien)
async def apercu(
    _courant: Courant, url: Annotated[str, Query(min_length=8, max_length=2048)]
) -> dict[str, str | None]:
    """Métadonnées d'aperçu d'une URL (titre, description, image, site) ; champs None si absents."""
    parse = urlparse(url)
    if parse.scheme not in ("http", "https") or parse.hostname is None:
        return {"url": url, "titre": None, "description": None, "image": None, "site": None}
    if url in _CACHE:
        return {"url": url, **_CACHE[url]}

    corps = await _recuperer(url)
    if corps is None:
        donnees: dict[str, str | None] = {
            "titre": None,
            "description": None,
            "image": None,
            "site": parse.hostname,
        }
    else:
        titre = _meta(corps, ("og:title", "twitter:title"))
        if titre is None:
            m = re.search(r"<title[^>]*>([^<]+)</title>", corps, re.IGNORECASE)
            titre = html.unescape(m.group(1).strip()) if m else None
        image = _meta(corps, ("og:image", "twitter:image", "twitter:image:src"))
        if image is not None:
            image = urljoin(url, image)  # une image relative devient absolue.
        donnees = {
            "titre": titre,
            "description": _meta(corps, ("og:description", "twitter:description", "description")),
            "image": image,
            "site": _meta(corps, ("og:site_name",)) or parse.hostname,
        }

    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[url] = donnees
    return {"url": url, **donnees}
