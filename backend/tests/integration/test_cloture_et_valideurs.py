"""Clôture = lecture seule, et le comité ne siège pas sans valideur.

Deux règles de sécurité ajoutées :

- Une activité dans un état terminal (clôturée, rejetée…) n'accepte plus aucune modification de son
  contenu — sauf le dossier RFC (le bilan se remplit *après* la mise en production) et les liens.
- On n'entre pas au comité (CAB/ECAB) sans valideur désigné : l'activité y resterait bloquée à vie.
"""

import json

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_activite, creer_utilisateur, designer, entetes

_RFC_COMPLET = {
    "analyse_impact": "Impact maîtrisé, service X.",
    "analyse_risque": "Risque faible, mesures en place.",
    "plan_retour_arriere": "Restauration du snapshot en 10 min.",
}


async def _remplir_donnees(session: AsyncSession, activite_id: str, donnees: dict[str, str]) -> None:
    await session.execute(
        text("UPDATE core.activite SET donnees = cast(:d as jsonb) WHERE id = cast(:id as uuid)"),
        {"d": json.dumps(donnees), "id": activite_id},
    )
    await session.commit()


async def test_pas_de_comite_sans_valideur(client: AsyncClient, session: AsyncSession) -> None:
    admin = await creer_utilisateur(session, email="admin.novalid@afgbank.ml", profil="ADMIN")
    changement = await creer_activite(
        session, module="changement", reference="CHG-NOVAL-1", statut="Évaluation"
    )
    await _remplir_donnees(session, changement, _RFC_COMPLET)

    # Sans valideur : soumettre au comité est refusé (422), pas de cul-de-sac.
    r = await client.post(
        f"/changements/{changement}/transition",
        headers=entetes(admin),
        json={"vers": "CAB"},
    )
    assert r.status_code == 422, r.text

    # Avec un valideur désigné : la transition passe.
    valideur = await creer_utilisateur(session, email="valid.novalid@afgbank.ml")
    await designer(session, activite_id=changement, utilisateur_id=valideur, role="VALIDEUR")
    r = await client.post(
        f"/changements/{changement}/transition",
        headers=entetes(admin),
        json={"vers": "CAB"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["statut"] == "CAB"


async def test_activite_close_en_lecture_seule_sauf_dossier(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await creer_utilisateur(session, email="admin.clos@afgbank.ml", profil="ADMIN")
    changement = await creer_activite(
        session, module="changement", reference="CHG-CLOS-1", statut="Clôturé"
    )

    # Les capacités reflètent la clôture : plus de travail, mais le dossier reste ouvert.
    r = await client.get(f"/changements/{changement}", headers=entetes(admin))
    perms = r.json()["permissions"]
    assert perms["peut_travailler"] is False
    assert perms["peut_assigner"] is False
    assert perms["peut_completer_dossier"] is True

    # Titre : refusé (impacterait l'état fini).
    r = await client.patch(
        f"/changements/{changement}",
        headers=entetes(admin),
        json={"titre": "Nouveau titre interdit"},
    )
    assert r.status_code == 409, r.text

    # Dossier RFC (bilan post-implémentation) : autorisé même clôturé.
    r = await client.patch(
        f"/changements/{changement}",
        headers=entetes(admin),
        json={"bilan_post_implementation": "Déploiement sans incident."},
    )
    assert r.status_code == 200, r.text

    # Réassigner le gestionnaire : refusé.
    autre = await creer_utilisateur(session, email="autre.clos@afgbank.ml")
    r = await client.post(
        f"/changements/{changement}/assignation",
        headers=entetes(admin),
        json={"responsable_id": autre},
    )
    assert r.status_code == 409, r.text


async def test_ma_decision_est_exposee_au_valideur(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await creer_utilisateur(session, email="admin.madec@afgbank.ml", profil="ADMIN")
    valideur = await creer_utilisateur(session, email="valid.madec@afgbank.ml")
    changement = await creer_activite(session, module="changement", reference="CHG-MADEC-1")
    await client.post(
        f"/changements/{changement}/valideurs",
        headers=entetes(admin),
        json={"utilisateur_id": valideur},
    )
    await client.post(
        f"/changements/{changement}/decision",
        headers=entetes(valideur),
        json={"decision": "REJETE"},
    )

    # Le valideur voit sa propre décision ; l'admin (non-valideur) ne l'a pas.
    r = await client.get(f"/changements/{changement}", headers=entetes(valideur))
    assert r.json()["ma_decision"] == "REJETE"
    r = await client.get(f"/changements/{changement}", headers=entetes(admin))
    assert r.json()["ma_decision"] is None
