"""Mises en page (gabarits) des e-mails transactionnels DSI 360 — HTML branché + repli texte.

Chaque fonction retourne (sujet, texte, html). Le HTML utilise des styles en ligne (contrainte des
clients de messagerie). Charte sobre : bandeau foncé, carte blanche, accent noir.
"""

_SOUS_MARQUE = "AFG Bank Mali"
_ACCENT = "#16181d"
_SECONDAIRE = "#7fc81f"  # touche de couleur de marque (accents)
_FOND = "#f4f5f7"
_TEXTE = "#16181d"
_MUET = "#6b7280"
CID_LOGO = "logodsi360"  # identifiant de l'image logo embarquée (cf. infrastructure.email)


def _bouton(url: str, libelle: str) -> str:
    return (
        f'<a href="{url}" style="display:inline-block;background:{_ACCENT};color:#ffffff;'
        "text-decoration:none;font-weight:600;font-size:14px;padding:12px 22px;"
        'border-radius:10px;">'
        f"{libelle}</a>"
    )


def _gabarit(titre: str, corps_html: str) -> str:
    """Enveloppe HTML commune (bandeau marque + carte + pied)."""
    return f"""\
<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;padding:24px 0;background:{_FOND};
  font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:{_TEXTE};">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
    <table role="presentation" width="560" cellpadding="0" cellspacing="0"
      style="width:560px;max-width:92%;">
      <tr><td style="padding:20px 8px;">
        <img src="cid:{CID_LOGO}" alt="DSI 360" height="30"
          style="display:inline-block;vertical-align:middle;border:0;">
        <span style="font-size:13px;color:{_MUET};vertical-align:middle;"> — {_SOUS_MARQUE}</span>
      </td></tr>
      <tr><td style="background:#ffffff;border:1px solid #e5e7eb;
        border-top:3px solid {_SECONDAIRE};border-radius:16px;padding:28px;">
        <h1 style="margin:0 0 14px;font-size:18px;font-weight:700;color:{_TEXTE};">{titre}</h1>
        {corps_html}
      </td></tr>
      <tr><td style="padding:16px 8px;color:{_MUET};font-size:12px;line-height:1.5;">
        Message automatique de la plateforme DSI 360 — {_SOUS_MARQUE}. Merci de ne pas répondre à
        cet e-mail.
      </td></tr>
    </table>
  </td></tr></table>
</body></html>"""


def _p(texte: str) -> str:
    return f'<p style="margin:0 0 12px;font-size:14px;line-height:1.6;color:{_TEXTE};">{texte}</p>'


def _muet(texte: str) -> str:
    return f'<p style="margin:14px 0 0;font-size:12px;color:{_MUET};line-height:1.5;">{texte}</p>'


def bienvenue(
    prenom: str, email: str, mot_de_passe: str, url_connexion: str
) -> tuple[str, str, str]:
    sujet = "Votre compte DSI 360 a été créé"
    texte = (
        f"Bonjour {prenom},\n\n"
        "Un compte DSI 360 (AFG Bank Mali) a été créé pour vous.\n"
        f"Identifiant : {email}\n"
        f"Mot de passe provisoire : {mot_de_passe}\n\n"
        "Vous devrez le changer à la première connexion.\n"
        f"Connexion : {url_connexion}\n"
    )
    ids = (
        f'<table role="presentation" cellpadding="0" cellspacing="0" '
        'style="margin:4px 0 16px;font-size:14px;">'
        f'<tr><td style="padding:4px 12px 4px 0;color:{_MUET};">Identifiant</td>'
        f'<td style="font-weight:600;">{email}</td></tr>'
        f'<tr><td style="padding:4px 12px 4px 0;color:{_MUET};">Mot de passe provisoire</td>'
        f'<td style="font-weight:600;font-family:monospace;">{mot_de_passe}</td></tr></table>'
    )
    html = _gabarit(
        "Bienvenue sur DSI 360",
        _p(f"Bonjour {prenom},")
        + _p("Un compte vous a été créé sur la plateforme DSI 360.")
        + ids
        + _p("Pour votre sécurité, vous devrez <strong>changer ce mot de passe</strong> à la "
             "première connexion.")
        + _bouton(url_connexion, "Se connecter")
        + _muet("Si vous n'êtes pas concerné(e) par cette création, ignorez cet e-mail ou "
                "prévenez l'administrateur."),
    )
    return sujet, texte, html


def reinitialisation(prenom: str, url_reset: str, validite_minutes: int) -> tuple[str, str, str]:
    sujet = "Réinitialisation de votre mot de passe DSI 360"
    texte = (
        f"Bonjour {prenom},\n\n"
        "Vous avez demandé la réinitialisation de votre mot de passe DSI 360.\n"
        f"Lien (valable {validite_minutes} minutes) : {url_reset}\n\n"
        "Si vous n'êtes pas à l'origine de cette demande, ignorez cet e-mail.\n"
    )
    html = _gabarit(
        "Réinitialiser votre mot de passe",
        _p(f"Bonjour {prenom},")
        + _p("Vous avez demandé à réinitialiser votre mot de passe. Cliquez sur le bouton "
             "ci-dessous pour en définir un nouveau.")
        + _bouton(url_reset, "Choisir un nouveau mot de passe")
        + _muet(f"Ce lien est valable {validite_minutes} minutes. Si vous n'êtes pas à l'origine "
                "de cette demande, ignorez cet e-mail : votre mot de passe reste inchangé."),
    )
    return sujet, texte, html


def mot_de_passe_change(prenom: str) -> tuple[str, str, str]:
    sujet = "Votre mot de passe DSI 360 a été modifié"
    texte = (
        f"Bonjour {prenom},\n\n"
        "Votre mot de passe DSI 360 vient d'être modifié.\n"
        "Si vous n'êtes pas à l'origine de ce changement, contactez immédiatement "
        "l'administrateur.\n"
    )
    html = _gabarit(
        "Mot de passe modifié",
        _p(f"Bonjour {prenom},")
        + _p("Votre mot de passe vient d'être <strong>modifié avec succès</strong>.")
        + _muet("Si vous n'êtes pas à l'origine de ce changement, contactez immédiatement "
                "l'administrateur : votre compte pourrait être compromis."),
    )
    return sujet, texte, html


def notification_activite(
    titre: str, message: str, url: str | None = None
) -> tuple[str, str, str]:
    """Gabarit générique des notifications métier (assignation, commentaire, validation, SLA…)."""
    texte = f"{titre}\n\n{message}\n" + (f"\nAccéder : {url}\n" if url else "")
    corps = _p(message) + (_bouton(url, "Ouvrir dans DSI 360") if url else "")
    html = _gabarit(titre, corps)
    return titre, texte, html


def compte_bloque(prenom: str) -> tuple[str, str, str]:
    sujet = "Votre accès DSI 360 a été suspendu"
    texte = (
        f"Bonjour {prenom},\n\n"
        "Votre accès à la plateforme DSI 360 a été suspendu par un administrateur.\n"
        "Pour toute question, rapprochez-vous de la DSI.\n"
    )
    html = _gabarit(
        "Accès suspendu",
        _p(f"Bonjour {prenom},")
        + _p("Votre accès à la plateforme DSI 360 a été <strong>suspendu</strong> par un "
             "administrateur.")
        + _muet("Pour toute question ou pour rétablir votre accès, rapprochez-vous de la DSI."),
    )
    return sujet, texte, html
