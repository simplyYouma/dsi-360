"""Inventaire applicatif : le patrimoine logiciel, ses éditeurs et ses administrateurs.

Une application n'est pas une activité : pas de workflow, pas de SLA. Ce qui compte ici, c'est que
le nom reste unique (deux fiches scinderaient le suivi), que le chargement initial soit bien en
base, que les changements d'administrateur se relisent dans l'historique, et que seule
l'administration puisse toucher au parc.
"""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import PROFIL_METIER, creer_utilisateur, entetes


async def _admin(session: AsyncSession, email: str) -> str:
    return await creer_utilisateur(session, email=email, profil="ADMIN")


async def _creer(client: AsyncClient, uid: str, **champs: Any) -> dict[str, Any]:
    corps: dict[str, Any] = {"nom": "Application de test"} | champs
    r = await client.post("/applications", json=corps, headers=entetes(uid))
    assert r.status_code == 201, r.text
    return dict(r.json())


async def test_creer_puis_relire_une_application(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await _admin(session, "admin.app1@afgbank.ml")

    # Nom volontairement absent du chargement initial : la base de test le porte aussi.
    cree = await _creer(
        client,
        admin,
        nom="E-bank de test (OBDX)",
        processus_metier="Banque mobile",
        fonctionnalites="Permet aux clients d'accéder aux services bancaires à distance",
        hebergement="INTERNE",
        interfacage="OUI",
        administrateur="Youssouf DIARRA",
        administrateur_secours="Mariam DIALLO",
    )

    r = await client.get(f"/applications/{cree['id']}", headers=entetes(admin))
    assert r.status_code == 200, r.text
    d = r.json()
    # Le nom d'un logiciel n'est pas un nom propre : la casse d'origine est conservée telle quelle.
    assert d["nom"] == "E-bank de test (OBDX)"
    assert d["processus_metier"] == "Banque mobile"
    assert d["hebergement"] == "INTERNE"
    assert d["interfacage"] == "OUI"
    assert d["administrateur"] == "Youssouf DIARRA"
    assert d["statut"] == "EN_SERVICE"
    assert d["actif"] is True
    assert d["source"] == "SAISIE"
    # Référence système attribuée d'office, jamais saisie : format APP-xxxxx.
    assert d["reference"].startswith("APP-")
    assert len(d["reference"]) >= 8


async def test_le_nom_identifie_l_application(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Deux fiches pour le même logiciel scinderaient son suivi : le second essai est refusé."""
    admin = await _admin(session, "admin.app2@afgbank.ml")
    await _creer(client, admin, nom="GENERATEUR DE TEST")

    # Même nom, casse et espaces différents : c'est la même application.
    r = await client.post(
        "/applications", json={"nom": "  generateur   de test "}, headers=entetes(admin)
    )
    assert r.status_code == 409, r.text
    assert "déjà" in r.json()["detail"]


async def test_absences_ecrites_a_la_main_ne_sont_pas_des_valeurs(
    client: AsyncClient, session: AsyncSession
) -> None:
    """« N/A » n'est pas un administrateur : le champ doit rester vide, pas porter le mot."""
    admin = await _admin(session, "admin.app3@afgbank.ml")

    cree = await _creer(
        client,
        admin,
        nom="Application sans responsable",
        administrateur="N/A",
        administrateur_secours="None",
        version="  ",
    )
    assert cree["administrateur"] is None
    assert cree["administrateur_secours"] is None
    assert cree["version"] is None


async def test_editeur_inconnu_refuse_en_clair(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Un identifiant forgé répond 422 lisible, jamais une erreur d'intégrité en 500."""
    admin = await _admin(session, "admin.app4@afgbank.ml")

    r = await client.post(
        "/applications",
        json={"nom": "Application éditeur fantôme", "editeur_id": "pas-un-uuid"},
        headers=entetes(admin),
    )
    assert r.status_code == 422, r.text

    r = await client.post(
        "/applications",
        json={
            "nom": "Application éditeur absent",
            "editeur_id": "00000000-0000-0000-0000-000000000000",
        },
        headers=entetes(admin),
    )
    assert r.status_code == 422, r.text
    assert "existe pas" in r.json()["detail"]


async def test_changement_d_administrateur_se_relit_dans_l_historique(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Qui administrait quoi, et depuis quand : c'est la question qu'on pose en audit."""
    admin = await _admin(session, "admin.app5@afgbank.ml")
    cree = await _creer(
        client, admin, nom="Application transmise", administrateur="Awa Touré"
    )

    r = await client.patch(
        f"/applications/{cree['id']}",
        json={"administrateur": "Mady Wague"},
        headers=entetes(admin),
    )
    assert r.status_code == 200, r.text
    assert r.json()["administrateur"] == "Mady Wague"

    detail = (await client.get(f"/applications/{cree['id']}", headers=entetes(admin))).json()
    lignes = [e["detail"] for e in detail["historique"] if e["detail"]]
    assert any("administrateur : Awa Touré → Mady Wague" in ligne for ligne in lignes), lignes


async def test_editeur_se_cree_et_ne_se_supprime_pas_sous_les_applications(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await _admin(session, "admin.app6@afgbank.ml")

    r = await client.post(
        "/applications/referentiels/editeurs",
        json={"libelle": "ÉDITEUR TEST"},
        headers=entetes(admin),
    )
    assert r.status_code == 201, r.text
    editeur = r.json()

    await _creer(client, admin, nom="Application de l'éditeur test", editeur_id=editeur["id"])

    # Retirer l'éditeur détacherait l'application sans le dire : refusé.
    r = await client.delete(
        f"/applications/referentiels/editeurs/{editeur['id']}", headers=entetes(admin)
    )
    assert r.status_code == 409, r.text

    liste = await client.get("/applications/referentiels/editeurs", headers=entetes(admin))
    assert any(e["libelle"] == "ÉDITEUR TEST" for e in liste.json())


async def test_le_parc_applicatif_est_en_lecture_pour_tous_en_ecriture_pour_l_admin(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Même partage des rôles que le parc matériel : l'agent consulte, l'admin tient le parc."""
    admin = await _admin(session, "admin.app7@afgbank.ml")
    agent = await creer_utilisateur(session, email="agent.app7@afgbank.ml", profil=PROFIL_METIER)
    cree = await _creer(client, admin, nom="Application gardée")

    # Lecture : ouverte à qui a l'accès module.
    assert (await client.get("/applications", headers=entetes(agent))).status_code == 200
    assert (
        await client.get(f"/applications/{cree['id']}", headers=entetes(agent))
    ).status_code == 200

    # Écriture : réservée à l'administrateur, et le serveur fait foi.
    r = await client.post("/applications", json={"nom": "Interdite"}, headers=entetes(agent))
    assert r.status_code == 403, r.text
    r = await client.patch(
        f"/applications/{cree['id']}", json={"version": "2.0"}, headers=entetes(agent)
    )
    assert r.status_code == 403, r.text
    r = await client.delete(f"/applications/{cree['id']}", headers=entetes(agent))
    assert r.status_code == 403, r.text


async def test_stats_comptent_les_trous_de_suivi(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Sans administrateur, sans relais : les vrais indicateurs d'un inventaire applicatif."""
    admin = await _admin(session, "admin.app8@afgbank.ml")
    avant = (await client.get("/applications/stats", headers=entetes(admin))).json()

    await _creer(client, admin, nom="Application orpheline")  # ni admin, ni secours
    await _creer(
        client, admin, nom="Application sans relais", administrateur="Seule Personne"
    )

    apres = (await client.get("/applications/stats", headers=entetes(admin))).json()
    assert apres["total"] == avant["total"] + 2
    assert apres["sans_administrateur"] == avant["sans_administrateur"] + 1
    assert apres["sans_secours"] == avant["sans_secours"] + 2


async def test_chargement_initial_present_et_idempotent(session: AsyncSession) -> None:
    """Les applications réelles du fichier source sont en base, et une seule fois chacune."""
    total = await session.scalar(
        text("SELECT count(*) FROM core.application WHERE source = 'CHARGEMENT_INITIAL'")
    )
    assert total is not None and total >= 84

    # Le nom est unique : aucun doublon n'a pu s'installer.
    doublons = await session.scalar(
        text(
            "SELECT count(*) FROM ("
            "  SELECT upper(btrim(nom)) FROM core.application"
            "  GROUP BY 1 HAVING count(*) > 1"
            ") d"
        )
    )
    assert doublons == 0

    # Une fiche témoin, avec son éditeur rattaché et son hébergement traduit.
    ligne = (
        await session.execute(
            text(
                "SELECT a.nom, e.libelle AS editeur, a.hebergement, a.administrateur "
                "FROM core.application a "
                "LEFT JOIN core.editeur_application e ON e.id = a.editeur_id "
                "WHERE upper(btrim(a.nom)) = 'ACCES CONNEXION VPN'"
            )
        )
    ).mappings().first()
    assert ligne is not None
    assert ligne["editeur"] == "CISCO/FORTINET"
    # « Banque » dans le fichier = hébergé chez nous.
    assert ligne["hebergement"] == "INTERNE"
    assert ligne["administrateur"] is not None


async def test_export_porte_toutes_les_colonnes_tenues(
    client: AsyncClient, session: AsyncSession
) -> None:
    """L'export dit tout ce que la fiche sait, pas seulement ce que la liste montre."""
    admin = await _admin(session, "admin.app9@afgbank.ml")
    await _creer(
        client,
        admin,
        nom="Application exportée",
        processus_metier="Compensation",
        version="12.4",
        administrateur="Awa Touré",
        administrateur_secours="Mady Wague",
        port="8443",
        serveur_application="SRV-APP-01",
    )

    r = await client.get("/applications/export?format=csv", headers=entetes(admin))
    assert r.status_code == 200, r.text
    contenu = r.content.decode("utf-8-sig")
    entete = contenu.splitlines()[0]
    for colonne in (
        "Réf",
        "Application",
        "Processus métier",
        "Version",
        "Éditeur",
        "Hébergement",
        "Administrateur",
        "Administrateur de secours",
        "Serveur d'application",
        "Port",
    ):
        assert colonne in entete, entete
    assert "Application exportée" in contenu
    assert "SRV-APP-01" in contenu
    assert "8443" in contenu


async def test_analyses_nomment_ce_qui_tient_a_une_personne(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await _admin(session, "admin.app10@afgbank.ml")
    await _creer(client, admin, nom="Application fragile", administrateur="Seule Personne")

    r = await client.get("/applications/analyses", headers=entetes(admin))
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["total"] >= 1
    # Le patrimoine se lit par éditeur (de qui dépend-on) et par hébergement (qu'est-ce qui sort).
    assert any(t["libelle"] for t in a["par_editeur"])
    assert any(t["libelle"] == "Interne (nos serveurs)" for t in a["par_hebergement"])
    assert any(t["libelle"] == "Application fragile" for t in a["sans_secours"])
