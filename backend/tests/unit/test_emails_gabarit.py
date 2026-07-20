"""Tout e-mail qui quitte la plateforme porte le gabarit de marque — jamais du texte nu.

Un message automatique est souvent le seul contact d'un agent avec DSI 360 en dehors de l'écran.
Une alerte SLA envoyée en texte brut donne l'image d'un script bricolé, pas d'un outil de la
banque. Ces tests interdisent la régression.
"""

import inspect

import pytest

from dsi360.infrastructure import email_modeles

# Fonctions publiques du module : chacune doit rendre (sujet, texte, html).
MODELES = [
    nom
    for nom, obj in vars(email_modeles).items()
    if not nom.startswith("_") and inspect.isfunction(obj)
]

# Arguments plausibles par modèle : on ne teste pas le contenu métier, mais la forme du rendu.
EXEMPLES: dict[str, dict[str, object]] = {
    "definir_mot_de_passe": {
        "prenom": "Awa",
        "email": "awa@afgbank.ml",
        "url_definition": "https://dsi360/def",
        "validite_minutes": 120,
    },
    "reinitialisation": {
        "prenom": "Awa",
        "url_reset": "https://dsi360/reset",
        "validite_minutes": 30,
    },
    "mot_de_passe_change": {"prenom": "Awa"},
    "compte_bloque": {"prenom": "Awa"},
    "notification_activite": {
        "titre": "INC-2026-0001 — Ouvert",
        "message": "Une activité vous a été confiée.",
        "url": "https://dsi360",
    },
    "alerte_sla": {
        "reference": "INC-2026-0001",
        "titre_activite": "Panne du serveur de messagerie",
        "depasse": True,
        "echeance": "16/07/2026 à 14h30",
        "url": "https://dsi360",
    },
    "escalade_p1": {
        "reference": "INC-2026-0002",
        "titre_activite": "Coupure du cœur bancaire",
        "url": "https://dsi360",
    },
}


def test_chaque_modele_est_couvert_par_un_exemple() -> None:
    """Un nouveau modèle sans exemple passerait sous le radar des tests suivants."""
    manquants = sorted(set(MODELES) - set(EXEMPLES))
    assert not manquants, f"Modèles d'e-mail sans exemple de test : {manquants}"


@pytest.mark.parametrize("nom", sorted(EXEMPLES))
def test_le_modele_rend_sujet_texte_et_html_de_marque(nom: str) -> None:
    sujet, texte, html = getattr(email_modeles, nom)(**EXEMPLES[nom])

    assert sujet.strip(), "un e-mail sans objet part en spam"
    assert texte.strip(), "le repli texte sert aux clients sans HTML"
    # Le gabarit de marque : structure HTML, logo embarqué, pied de page automatique.
    assert html.lstrip().startswith("<!doctype html>"), f"{nom} : ce n'est pas une page HTML"
    assert f"cid:{email_modeles.CID_LOGO}" in html, f"{nom} : logo de marque absent"
    assert "AFG Bank Mali" in html, f"{nom} : signature de marque absente"
    assert "Merci de ne pas répondre" in html, f"{nom} : pied de page automatique absent"


@pytest.mark.parametrize("nom", sorted(EXEMPLES))
def test_le_html_est_autonome(nom: str) -> None:
    """Les clients de messagerie ignorent les feuilles de style : tout est en ligne."""
    _, _, html = getattr(email_modeles, nom)(**EXEMPLES[nom])
    assert "<style" not in html, f"{nom} : une balise <style> ne survit pas à Outlook"
    assert "<link" not in html, f"{nom} : aucune ressource externe dans un e-mail"


def test_l_alerte_sla_distingue_le_depassement_de_l_approche() -> None:
    """La couleur porte le sens : rouge quand c'est dépassé, ambre quand ça approche."""
    args = {k: v for k, v in EXEMPLES["alerte_sla"].items() if k != "depasse"}
    sujet_d, _, html_d = email_modeles.alerte_sla(depasse=True, **args)  # type: ignore[arg-type]
    sujet_a, _, html_a = email_modeles.alerte_sla(depasse=False, **args)  # type: ignore[arg-type]

    assert "dépassée" in sujet_d and "approche" in sujet_a
    assert "#d64545" in html_d, "un SLA dépassé doit s'afficher en rouge"
    assert "#c77700" in html_a, "une échéance qui approche est une vigilance, pas une urgence"


def test_les_alertes_portent_la_reference_du_dossier() -> None:
    """Sans référence, le destinataire ne sait pas de quel dossier on lui parle."""
    for nom in ("alerte_sla", "escalade_p1"):
        sujet, texte, html = getattr(email_modeles, nom)(**EXEMPLES[nom])
        reference = str(EXEMPLES[nom]["reference"])
        assert reference in sujet and reference in texte and reference in html
