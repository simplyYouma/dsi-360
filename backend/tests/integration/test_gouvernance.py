"""Gouvernance : département, risques/impacts, et avancement déclaré par le gestionnaire.

Ce module se distingue des autres activités pilotées sur trois points, et chacun a une raison :

- il se **range par département** de la DSI — ce qui sert à lire et à analyser, jamais à cloisonner
  les accès (le périmètre reste la direction) ;
- son **avancement se déclare à la main**, contrairement aux projets et changements où il se déduit
  des tâches terminées. Deux sources pour un même chiffre finiraient par diverger ;
- toute déclaration exige une **justification** : un pourcentage seul ne se relit pas trois mois
  plus tard.

Le point le plus important est le dernier test de la première section : le **contributeur** fait
avancer le travail, mais c'est le **gestionnaire** qui rend compte. Confondre les deux reviendrait
à laisser n'importe quel acteur engager le responsable du sujet.
"""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_activite, creer_utilisateur, entetes


async def _departement(session: AsyncSession, code: str) -> str:
    ident = await session.scalar(
        text("SELECT id::text FROM core.departement WHERE code = :c"), {"c": code}
    )
    assert ident is not None, f"département {code} absent : la migration a-t-elle tourné ?"
    return str(ident)


async def _sujet(session: AsyncSession, reference: str, responsable_id: str | None = None) -> str:
    return await creer_activite(
        session, module="gouvernance", reference=reference, responsable_id=responsable_id
    )


async def _detail(client: AsyncClient, ident: str, uid: str) -> dict[str, Any]:
    r = await client.get(f"/gouvernance/{ident}", headers=entetes(uid))
    assert r.status_code == 200, r.text
    return dict(r.json())


# --- L'avancement : qui a le droit de le déclarer ------------------------------------------------


async def test_le_gestionnaire_declare_l_avancement_avec_justification(
    client: AsyncClient, session: AsyncSession
) -> None:
    gestionnaire = await creer_utilisateur(session, email="gest.gouv1@afgbank.ml")
    sujet = await _sujet(session, "GOV-AV-1", responsable_id=gestionnaire)

    r = await client.post(
        f"/gouvernance/{sujet}/avancement",
        headers=entetes(gestionnaire),
        json={"avancement": 40, "justification": "Cadrage validé en COPIL du 12/09"},
    )

    assert r.status_code == 200, r.text
    assert r.json()["avancement"] == 40
    # La justification est conservée comme note du dossier — même mécanisme que les transitions
    # justifiées des projets, plutôt qu'un stockage de plus.
    note = (
        await session.execute(
            text(
                "SELECT texte, contexte FROM core.note WHERE activite_id = cast(:a as uuid)"
            ),
            {"a": sujet},
        )
    ).mappings().one()
    assert note["contexte"] == "avancement"
    assert note["texte"] == "Cadrage validé en COPIL du 12/09"


async def test_un_avancement_sans_justification_est_refuse(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le refus est SERVEUR : l'écran ne fait que le refléter."""
    gestionnaire = await creer_utilisateur(session, email="gest.gouv2@afgbank.ml")
    sujet = await _sujet(session, "GOV-AV-2", responsable_id=gestionnaire)

    for justification in ("", "  ", "ok"):
        r = await client.post(
            f"/gouvernance/{sujet}/avancement",
            headers=entetes(gestionnaire),
            json={"avancement": 40, "justification": justification},
        )
        assert r.status_code == 422, f"« {justification} » aurait dû être refusé : {r.text}"

    assert (await _detail(client, sujet, gestionnaire))["avancement"] == 0


async def test_un_contributeur_ne_declare_pas_l_avancement(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le contributeur fait avancer le travail ; le gestionnaire rend compte. Ce n'est pas pareil.

    Il a pourtant `peut_travailler` : il pose des documents, des liens, des commentaires, il fait
    des transitions. Annoncer un pourcentage engage celui à qui le sujet est affecté — c'est un
    compte rendu, pas une contribution de plus.
    """
    admin = await creer_utilisateur(session, email="admin.gouv3@afgbank.ml", profil="ADMIN")
    gestionnaire = await creer_utilisateur(session, email="gest.gouv3@afgbank.ml")
    contributeur = await creer_utilisateur(session, email="contrib.gouv3@afgbank.ml")
    sujet = await _sujet(session, "GOV-AV-3", responsable_id=gestionnaire)
    r = await client.post(
        f"/gouvernance/{sujet}/contributeurs",
        headers=entetes(admin),
        json={"utilisateur_id": contributeur},
    )
    assert r.status_code == 200, r.text

    refus = await client.post(
        f"/gouvernance/{sujet}/avancement",
        headers=entetes(contributeur),
        json={"avancement": 80, "justification": "je pense que c'est presque fini"},
    )

    assert refus.status_code == 403, refus.text
    # L'écran doit dire la même chose que le serveur : la permission le lui apprend.
    vu_par_le_contributeur = await _detail(client, sujet, contributeur)
    assert vu_par_le_contributeur["permissions"]["peut_avancer"] is False
    assert vu_par_le_contributeur["permissions"]["peut_travailler"] is True
    assert (await _detail(client, sujet, gestionnaire))["permissions"]["peut_avancer"] is True


async def test_l_avancement_est_journalise_en_clair(
    client: AsyncClient, session: AsyncSession
) -> None:
    gestionnaire = await creer_utilisateur(session, email="gest.gouv4@afgbank.ml")
    sujet = await _sujet(session, "GOV-AV-4", responsable_id=gestionnaire)
    for valeur, motif in ((25, "Comité tenu"), (60, "Livrables reçus")):
        r = await client.post(
            f"/gouvernance/{sujet}/avancement",
            headers=entetes(gestionnaire),
            json={"avancement": valeur, "justification": motif},
        )
        assert r.status_code == 200, r.text

    journal = (await _detail(client, sujet, gestionnaire))["journal"]
    details = " ".join(e["detail"] or "" for e in journal)
    assert "avancement" in details
    assert "25 %" in details and "60 %" in details, details
    assert "Livrables reçus" in details


# --- Le département ------------------------------------------------------------------------------


async def test_le_departement_se_pose_et_se_retire(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await creer_utilisateur(session, email="admin.gouv5@afgbank.ml", profil="ADMIN")
    sujet = await _sujet(session, "GOV-DEP-1")
    reseau = await _departement(session, "RESEAU_INFRASTRUCTURE")

    r = await client.post(
        f"/gouvernance/{sujet}/departement",
        headers=entetes(admin),
        json={"departement_id": reseau},
    )
    assert r.status_code == 200, r.text
    assert r.json()["departement"] == "Réseau et Infrastructure"

    r = await client.post(
        f"/gouvernance/{sujet}/departement", headers=entetes(admin), json={"departement_id": None}
    )
    assert r.status_code == 200, r.text
    assert r.json()["departement"] is None


async def test_un_departement_inconnu_est_refuse(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await creer_utilisateur(session, email="admin.gouv6@afgbank.ml", profil="ADMIN")
    sujet = await _sujet(session, "GOV-DEP-2")
    r = await client.post(
        f"/gouvernance/{sujet}/departement",
        headers=entetes(admin),
        json={"departement_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert r.status_code == 400, r.text


async def test_ranger_un_sujet_ne_le_cache_a_personne(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le département ORGANISE, il ne cloisonne pas.

    Un agent d'un autre département continue de voir le sujet : le périmètre d'accès reste la
    direction. Sans ce test, rien n'empêcherait qu'un rangement devienne une restriction.
    """
    admin = await creer_utilisateur(session, email="admin.gouv7@afgbank.ml", profil="ADMIN")
    autre = await creer_utilisateur(session, email="autre.gouv7@afgbank.ml")
    sujet = await _sujet(session, "GOV-DEP-3")
    r = await client.post(
        f"/gouvernance/{sujet}/departement",
        headers=entetes(admin),
        json={"departement_id": await _departement(session, "PRODUCTION_APPLICATIF")},
    )
    assert r.status_code == 200, r.text

    assert (await _detail(client, sujet, autre))["reference"] == "GOV-DEP-3"
    liste = await client.get("/gouvernance", headers=entetes(autre))
    assert liste.status_code == 200, liste.text
    assert any(e["reference"] == "GOV-DEP-3" for e in liste.json()["elements"])


# --- Risques et impacts --------------------------------------------------------------------------


async def test_risques_et_impacts_se_saisissent_et_se_relisent(
    client: AsyncClient, session: AsyncSession
) -> None:
    gestionnaire = await creer_utilisateur(session, email="gest.gouv8@afgbank.ml")
    sujet = await _sujet(session, "GOV-RI-1", responsable_id=gestionnaire)

    r = await client.patch(
        f"/gouvernance/{sujet}",
        headers=entetes(gestionnaire),
        json={
            "risques": "Indisponibilité du prestataire en fin d'année",
            "impacts": "Report du COPIL et du budget associé",
        },
    )

    assert r.status_code == 200, r.text
    detail = r.json()
    assert detail["risques"] == "Indisponibilité du prestataire en fin d'année"
    assert detail["impacts"] == "Report du COPIL et du budget associé"


async def test_un_champ_de_changement_n_entre_pas_dans_un_sujet_de_gouvernance(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le schéma accepte tous les champs de module ; c'est la route qui trie.

    Sans ce filtre, une analyse d'impact de changement finirait dans le JSON d'un sujet de COPIL,
    où rien ne l'afficherait ni ne la relirait — une donnée perdue de vue, pas une donnée en plus.
    """
    gestionnaire = await creer_utilisateur(session, email="gest.gouv9@afgbank.ml")
    sujet = await _sujet(session, "GOV-RI-2", responsable_id=gestionnaire)

    r = await client.patch(
        f"/gouvernance/{sujet}",
        headers=entetes(gestionnaire),
        json={"risques": "Retard fournisseur", "analyse_impact": "n'a rien à faire ici"},
    )

    assert r.status_code == 200, r.text
    assert r.json()["risques"] == "Retard fournisseur"
    donnees = await session.scalar(
        text("SELECT donnees FROM core.activite WHERE id = cast(:a as uuid)"), {"a": sujet}
    )
    assert "analyse_impact" not in (donnees or {})


# --- Export --------------------------------------------------------------------------------------


async def test_l_export_gouvernance_porte_ses_colonnes_propres(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await creer_utilisateur(session, email="admin.gouvx@afgbank.ml", profil="ADMIN")

    r = await client.get("/gouvernance/export?format=csv", headers=entetes(admin))
    assert r.status_code == 200, r.text
    entetes_csv = r.content.decode("utf-8-sig").splitlines()[0]
    for colonne in ("Département", "Avancement (%)", "Risques identifiés", "Impacts attendus"):
        assert colonne in entetes_csv, f"« {colonne} » manque : {entetes_csv}"

    # Et ces colonnes ne polluent pas les modules qui ne peuvent pas les remplir : une colonne
    # toujours vide n'est pas de l'exhaustivité, c'est du bruit.
    r = await client.get("/incidents/export?format=csv", headers=entetes(admin))
    assert r.status_code == 200, r.text
    entetes_incident = r.content.decode("utf-8-sig").splitlines()[0]
    assert "Risques identifiés" not in entetes_incident
    assert "Département" not in entetes_incident
