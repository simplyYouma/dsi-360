"""Mises en page (gabarits) des e-mails transactionnels DSI 360 — HTML branché + repli texte.

Chaque fonction retourne (sujet, texte, html). Le HTML utilise des styles en ligne (contrainte des
clients de messagerie). Charte sobre : bandeau marque, carte blanche, liseré d'accent, bouton foncé.
"""

_SOUS_MARQUE = "AFG Bank Mali"
_ACCENT = "#16181d"
_SECONDAIRE = "#7fc81f"  # touche de couleur de marque (accents)
_FOND = "#f4f5f7"
_TEXTE = "#16181d"
_MUET = "#6b7280"
_BORDURE = "#e5e7eb"
# Couleurs d'alerte, alignées sur les jetons de l'application (--status-danger / --status-warn).
# Réservées au sens : une échéance dépassée, une escalade. Jamais décoratives.
# Les fonds sont des teintes OPAQUES : un hex à 8 chiffres (alpha) n'est pas rendu par Outlook,
# et le bandeau apparaîtrait sans fond — voire noir.
_DANGER = "#d64545"
_DANGER_FOND = "#fdecec"
_ALERTE = "#c77700"
_ALERTE_FOND = "#fdf3e3"
CID_LOGO = "logodsi360"  # identifiant de l'image logo embarquée (cf. infrastructure.email)


def _preheader(texte: str) -> str:
    """Texte d'aperçu (caché) affiché par les clients de messagerie sous l'objet."""
    return (
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;'
        f'color:{_FOND};font-size:1px;line-height:1px;">{texte}</div>'
    )


def _bouton(url: str, libelle: str) -> str:
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" style="margin:18px 0 4px;">'
        f'<tr><td style="border-radius:10px;background:{_ACCENT};">'
        f'<a href="{url}" style="display:inline-block;background:{_ACCENT};color:#ffffff;'
        "text-decoration:none;font-weight:600;font-size:14px;padding:13px 26px;"
        'border-radius:10px;">'
        f"{libelle}</a></td></tr></table>"
    )


def _encadre(lignes: list[tuple[str, str]]) -> str:
    """Encadré d'informations (libellé → valeur) sur fond léger."""
    cellules = "".join(
        f'<tr><td style="padding:5px 14px 5px 0;color:{_MUET};font-size:13px;">{cle}</td>'
        f'<td style="font-weight:600;font-size:14px;color:{_TEXTE};">{valeur}</td></tr>'
        for cle, valeur in lignes
    )
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;'
        f'margin:4px 0 8px;background:{_FOND};border:1px solid {_BORDURE};border-radius:10px;'
        f'padding:6px 16px;"><tr><td><table role="presentation" cellpadding="0" cellspacing="0">'
        f"{cellules}</table></td></tr></table>"
    )


def _gabarit(titre: str, corps_html: str, apercu: str = "") -> str:
    """Enveloppe HTML commune (aperçu + bandeau marque + carte + pied)."""
    return f"""\
<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;padding:24px 0;background:{_FOND};
  font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:{_TEXTE};">
  {_preheader(apercu or titre)}
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
    <table role="presentation" width="560" cellpadding="0" cellspacing="0"
      style="width:560px;max-width:92%;">
      <tr><td style="padding:20px 8px;">
        <img src="cid:{CID_LOGO}" alt="DSI 360" height="30"
          style="display:inline-block;vertical-align:middle;border:0;">
        <span style="font-size:13px;color:{_MUET};vertical-align:middle;"> — {_SOUS_MARQUE}</span>
      </td></tr>
      <tr><td style="background:#ffffff;border:1px solid {_BORDURE};
        border-top:3px solid {_SECONDAIRE};border-radius:16px;padding:28px;">
        <h1 style="margin:0 0 16px;font-size:19px;font-weight:700;color:{_TEXTE};
          line-height:1.3;">{titre}</h1>
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


def definir_mot_de_passe(
    prenom: str, email: str, url_definition: str, validite_minutes: int
) -> tuple[str, str, str]:
    """Création de compte : l'utilisateur définit son mot de passe via un lien expirable."""
    heures = validite_minutes // 60
    if heures:
        duree = f"{heures} heure" + ("s" if heures > 1 else "")
    else:
        duree = f"{validite_minutes} min"
    sujet = "Activez votre compte DSI 360"
    texte = (
        f"Bonjour {prenom},\n\n"
        "Un compte DSI 360 (AFG Bank Mali) a été créé pour vous.\n"
        f"Identifiant : {email}\n\n"
        f"Définissez votre mot de passe via ce lien (valable {duree}) : {url_definition}\n\n"
        "Passé ce délai, demandez un nouveau lien à votre administrateur.\n"
    )
    html = _gabarit(
        "Activez votre compte",
        _p(f"Bonjour {prenom},")
        + _p("Un compte vous a été créé sur la plateforme DSI 360. Pour l'activer, définissez "
             "votre mot de passe personnel :")
        + _encadre([("Identifiant", email)])
        + _bouton(url_definition, "Définir mon mot de passe")
        + _muet(f"Ce lien est valable <strong>{duree}</strong>. Passé ce délai, il expirera : "
                "demandez alors un nouveau lien à votre administrateur. Si vous n'êtes pas "
                "concerné(e) par cette création, ignorez cet e-mail."),
        apercu="Définissez votre mot de passe pour activer votre accès DSI 360.",
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
        apercu="Lien de réinitialisation de votre mot de passe DSI 360.",
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
        apercu="Confirmation : votre mot de passe DSI 360 a été modifié.",
    )
    return sujet, texte, html


def notification_activite(
    titre: str, message: str, url: str | None = None
) -> tuple[str, str, str]:
    """Gabarit générique des notifications métier (assignation, commentaire, validation, SLA…)."""
    texte = f"{titre}\n\n{message}\n" + (f"\nAccéder : {url}\n" if url else "")
    corps = _p(message) + (_bouton(url, "Ouvrir dans DSI 360") if url else "")
    html = _gabarit(titre, corps, apercu=message[:120])
    return titre, texte, html


def _bandeau_alerte(texte: str, couleur: str, fond: str) -> str:
    """Bandeau d'urgence en tête de carte. La couleur porte le sens, jamais la décoration."""
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;'
        f'margin:0 0 16px;background:{fond};border-left:3px solid {couleur};'
        f'border-radius:8px;"><tr><td style="padding:11px 14px;color:{couleur};'
        f'font-size:13px;font-weight:700;letter-spacing:0.03em;">{texte}</td></tr></table>'
    )


def alerte_sla(
    reference: str,
    titre_activite: str,
    depasse: bool,
    echeance: str | None = None,
    url: str | None = None,
) -> tuple[str, str, str]:
    """Échéance SLA dépassée ou en approche. Une alerte doit se lire d'un coup d'œil."""
    couleur, fond = (_DANGER, _DANGER_FOND) if depasse else (_ALERTE, _ALERTE_FOND)
    etat = "dépassée" if depasse else "en approche"
    sujet = f"SLA {etat} — {reference}"
    intro = (
        "L'échéance de résolution est dépassée : ce dossier demande une action immédiate."
        if depasse
        else "L'échéance de résolution approche : il reste peu de temps pour agir."
    )
    lignes = [("Référence", reference), ("Objet", titre_activite)]
    if echeance:
        lignes.append(("Échéance", echeance))
    corps = (
        _bandeau_alerte(f"SLA {etat.upper()}", couleur, fond)
        + _p(intro)
        + _encadre(lignes)
        + (_bouton(url, "Ouvrir le dossier") if url else "")
    )
    texte = (
        f"{sujet}\n\n{intro}\n\n"
        f"Référence : {reference}\nObjet : {titre_activite}\n"
        + (f"Échéance : {echeance}\n" if echeance else "")
        + (f"\nAccéder : {url}\n" if url else "")
    )
    return sujet, texte, _gabarit(sujet, corps, apercu=intro)


def escalade_p1(
    reference: str, titre_activite: str, url: str | None = None
) -> tuple[str, str, str]:
    """Ticket P1 non pris en charge dans les délais : l'e-mail le plus urgent du produit."""
    sujet = f"Escalade P1 — {reference}"
    intro = (
        "Ce ticket de priorité 1 n'a pas été pris en charge dans le délai prévu. "
        "Il vous est escaladé pour prise en main immédiate."
    )
    corps = (
        _bandeau_alerte("ESCALADE — PRIORITÉ 1", _DANGER, _DANGER_FOND)
        + _p(intro)
        + _encadre([("Référence", reference), ("Objet", titre_activite), ("Priorité", "P1")])
        + (_bouton(url, "Prendre en charge") if url else "")
        + _muet("Cette escalade est journalisée dans le registre d'audit.")
    )
    texte = (
        f"{sujet}\n\n{intro}\n\n"
        f"Référence : {reference}\nObjet : {titre_activite}\nPriorité : P1\n"
        + (f"\nAccéder : {url}\n" if url else "")
    )
    return sujet, texte, _gabarit(sujet, corps, apercu=intro)


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
        apercu="Votre accès à DSI 360 a été suspendu.",
    )
    return sujet, texte, html
