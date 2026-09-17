"""EOD : ouvrir une soirée, la pointer, la clore — et ce que le serveur refuse.

La soirée EOD se distingue des autres activités sur trois points, chacun éprouvé ici :

- elle s'ouvre **d'une date** : titre, référence, priorité et déroulé de référence sont déduits.
  À 20 h, pendant que le core banking attend, un formulaire de plus ne serait pas rempli ;
- son avancement se **déduit** des étapes pointées, jamais déclaré ;
- **une seule soirée par journée comptable** : deux rapports pour la même nuit seraient une faute
  de saisie, jamais une intention.

Le test qui compte le plus est celui de la justification : un « Anomalie » ou un « Non applicable »
sans un mot ne se relit pas six semaines plus tard, et c'est précisément ce qu'on vient chercher
dans l'historique d'une nuit.
"""

from datetime import UTC, datetime
from typing import Any

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_utilisateur, entetes


async def _ouvrir(client: AsyncClient, uid: str, journee: str) -> str:
    r = await client.post("/eod", headers=entetes(uid), json={"journee": journee})
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def _detail(client: AsyncClient, uid: str, ident: str) -> dict[str, Any]:
    r = await client.get(f"/eod/{ident}", headers=entetes(uid))
    assert r.status_code == 200, r.text
    return dict(r.json())


def _etape(detail: dict[str, Any], libelle: str) -> dict[str, Any]:
    for e in detail["etapes"]:
        if e["libelle"] == libelle:
            return dict(e)
    raise AssertionError(f"Étape « {libelle} » absente du déroulé.")


# --- Ouvrir la soirée ---------------------------------------------------------------------------


async def test_ouvrir_une_soiree_pose_le_deroule_de_reference(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Une date suffit : l'opérateur pointe sa première étape sans avoir rien rédigé."""
    operateur = await creer_utilisateur(session, email="eod.ouvre@afgbank.ml")
    ident = await _ouvrir(client, operateur, "2026-09-15")

    detail = await _detail(client, operateur, ident)
    assert detail["reference"].startswith("EOD-2026-")
    assert detail["titre"] == "EOD du 15/09/2026"
    assert detail["statut"] == "Préparé"
    assert detail["journee"] == "2026-09-15"
    assert detail["nb_etapes"] == 28, "le déroulé de référence doit être recopié en entier"
    assert detail["avancement"] == 0
    # Qui ouvre la soirée la conduit : sans cela, personne ne pourrait pointer avant qu'un
    # administrateur ne passe — au milieu de la nuit.
    assert detail["responsable_id"] == operateur
    assert detail["permissions"]["peut_travailler"] is True


async def test_le_deroule_garde_l_ordre_d_execution(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Chaque étape suppose la précédente faite : l'ordre n'est pas décoratif."""
    operateur = await creer_utilisateur(session, email="eod.ordre@afgbank.ml")
    detail = await _detail(client, operateur, await _ouvrir(client, operateur, "2026-09-14"))

    libelles = [e["libelle"] for e in detail["etapes"]]
    assert libelles[0] == "Intégration fichier CARTHAGO"
    assert libelles[-1] == "Backup After EOD"
    sections = [e["section"] for e in detail["etapes"]]
    assert sections.index("PART 1") < sections.index("PART 4")


async def test_la_date_systeme_se_releve_au_lieu_de_se_chronometrer(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Sur « System Date », ce qui compte n'est pas quand on a regardé mais ce qu'on a lu."""
    operateur = await creer_utilisateur(session, email="eod.datesys@afgbank.ml")
    detail = await _detail(client, operateur, await _ouvrir(client, operateur, "2026-09-13"))

    dates = [e for e in detail["etapes"] if e["libelle"] == "System Date"]
    assert len(dates) == 2, "relevée avant ET après la bascule"
    assert {e["nature"] for e in dates} == {"valeur"}


async def test_deux_soirees_pour_la_meme_nuit_sont_refusees(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Et le refus **nomme** la soirée déjà ouverte : « laquelle ? » est la première question."""
    operateur = await creer_utilisateur(session, email="eod.doublon@afgbank.ml")
    await _ouvrir(client, operateur, "2026-09-12")

    r = await client.post("/eod", headers=entetes(operateur), json={"journee": "2026-09-12"})
    assert r.status_code == 409, r.text
    assert "EOD-2026-" in r.json()["detail"]


# --- Pointer la soirée --------------------------------------------------------------------------


async def test_pointer_horodate_et_fait_avancer_l_etape(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Un seul geste : sinon on obtient des étapes horodatées restées « À faire »."""
    operateur = await creer_utilisateur(session, email="eod.pointe@afgbank.ml")
    ident = await _ouvrir(client, operateur, "2026-09-11")
    etape = _etape(await _detail(client, operateur, ident), "EODM")

    r = await client.post(
        f"/eod/{ident}/etapes/{etape['id']}/pointer",
        headers=entetes(operateur),
        json={"quoi": "debut"},
    )
    assert r.status_code == 200, r.text
    apres = _etape(r.json(), "EODM")
    assert apres["statut"] == "En cours"
    assert apres["debut"] is not None

    r = await client.post(
        f"/eod/{ident}/etapes/{etape['id']}/pointer",
        headers=entetes(operateur),
        json={"quoi": "fin"},
    )
    assert r.status_code == 200, r.text
    fini = _etape(r.json(), "EODM")
    assert fini["statut"] == "Complété"
    assert fini["fin"] is not None


async def test_demarrer_sur_une_heure_choisie_rattrape_une_ligne_oubliee(
    client: AsyncClient, session: AsyncSession
) -> None:
    """« Démarrer » pose l'instant présent ; rattraper une ligne oubliée pose l'heure qu'on donne.

    L'écran s'appuie sur le PATCH générique (celui de « Reprendre ») plutôt que sur une route
    dédiée : il n'existe qu'un seul chemin pour écrire une heure de début, jamais deux qui
    pourraient diverger.
    """
    operateur = await creer_utilisateur(session, email="eod.demarrer.heure@afgbank.ml")
    ident = await _ouvrir(client, operateur, "2026-09-09")
    etape = _etape(await _detail(client, operateur, ident), "EODM")

    heure_choisie = datetime(2026, 9, 9, 21, 5, tzinfo=UTC)
    r = await client.patch(
        f"/eod/{ident}/etapes/{etape['id']}",
        headers=entetes(operateur),
        json={"statut": "En cours", "debut": heure_choisie.isoformat()},
    )
    assert r.status_code == 200, r.text
    apres = _etape(r.json(), "EODM")
    assert apres["statut"] == "En cours"
    # Comparé en instant, pas en chaîne : le serveur peut rendre « Z » là où on a envoyé
    # « +00:00 », deux écritures du même instant.
    assert datetime.fromisoformat(apres["debut"]) == heure_choisie
    # Aucune explication à fournir : ce n'est pas un verdict d'échec, seulement un rattrapage.


async def test_l_avancement_se_deduit_des_etapes_reglees(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Il n'est jamais déclaré : deux sources pour un même chiffre finiraient par diverger."""
    operateur = await creer_utilisateur(session, email="eod.avance@afgbank.ml")
    ident = await _ouvrir(client, operateur, "2026-09-10")
    detail = await _detail(client, operateur, ident)
    assert detail["avancement"] == 0

    for libelle in ("Intégration fichier CARTHAGO", "Check Pending Transactions"):
        etape = _etape(detail, libelle)
        r = await client.post(
            f"/eod/{ident}/etapes/{etape['id']}/pointer",
            headers=entetes(operateur),
            json={"quoi": "fin"},
        )
        assert r.status_code == 200, r.text
        detail = dict(r.json())

    # 2 étapes sur 28 : arrondi à 7 %.
    assert detail["avancement"] == 7
    assert detail["reste"] == 26


async def test_le_non_applicable_compte_comme_regle(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Un soir sans fin de mois n'est pas un soir inachevé : l'étape EOM ne s'appliquait pas."""
    operateur = await creer_utilisateur(session, email="eod.eom@afgbank.ml")
    ident = await _ouvrir(client, operateur, "2026-09-09")
    etape = _etape(await _detail(client, operateur, ident), "Backup before EOM")

    r = await client.patch(
        f"/eod/{ident}/etapes/{etape['id']}",
        headers=entetes(operateur),
        json={
            "statut": "Non applicable",
            "observation": {"texte": "Pas une fin de mois."},
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["reste"] == 27
    assert r.json()["anomalies"] == 0


# --- Ce que le serveur refuse -------------------------------------------------------------------


async def test_une_anomalie_sans_explication_est_refusee(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Six semaines plus tard, « Anomalie » sans un mot ne se relit pas."""
    operateur = await creer_utilisateur(session, email="eod.anomalie@afgbank.ml")
    ident = await _ouvrir(client, operateur, "2026-09-08")
    detail = await _detail(client, operateur, ident)
    etape = _etape(detail, "Batch Check : EMS_IN, EMS_OUT, EMS_OUT_PM")

    r = await client.patch(
        f"/eod/{ident}/etapes/{etape['id']}",
        headers=entetes(operateur),
        json={"statut": "Anomalie"},
    )
    assert r.status_code == 400, r.text

    # Verdict et explication dans le MÊME appel : demander l'observation dans un second temps
    # ferait échouer le premier geste pour une raison découverte après coup.
    r = await client.patch(
        f"/eod/{ident}/etapes/{etape['id']}",
        headers=entetes(operateur),
        json={
            "statut": "Anomalie",
            "observation": {
                "texte": "Jobs démarrés mais la date reste au 15/09 au lieu du 16/09.",
            },
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["anomalies"] == 1
    assert len(_etape(r.json(), "Batch Check : EMS_IN, EMS_OUT, EMS_OUT_PM")["observations"]) == 1

    # Une observation déjà au journal suffit : le verdict se corrige ensuite sans réécrire un mot.
    r = await client.patch(
        f"/eod/{ident}/etapes/{etape['id']}",
        headers=entetes(operateur),
        json={"statut": "Non applicable"},
    )
    assert r.status_code == 200, r.text


async def test_un_agent_sans_role_sur_la_soiree_ne_la_pointe_pas(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Voir la soirée ne donne pas prise dessus : le pointage engage la nuit de quelqu'un."""
    operateur = await creer_utilisateur(session, email="eod.titulaire@afgbank.ml")
    passant = await creer_utilisateur(session, email="eod.passant@afgbank.ml")
    ident = await _ouvrir(client, operateur, "2026-09-07")
    etape = _etape(await _detail(client, operateur, ident), "Date Check")

    # Il la lit sans difficulté…
    assert (await client.get(f"/eod/{ident}", headers=entetes(passant))).status_code == 200
    # …mais il ne la pointe pas.
    r = await client.post(
        f"/eod/{ident}/etapes/{etape['id']}/pointer",
        headers=entetes(passant),
        json={"quoi": "debut"},
    )
    assert r.status_code == 403, r.text


# --- Clore la soirée ----------------------------------------------------------------------------


async def test_la_cloture_conseillee_suit_l_etat_reel_du_deroule(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le serveur conseille, l'opérateur tranche — mais jamais d'effacer une anomalie constatée."""
    operateur = await creer_utilisateur(session, email="eod.conseil@afgbank.ml")
    ident = await _ouvrir(client, operateur, "2026-09-06")
    detail = await _detail(client, operateur, ident)
    assert detail["cloture_conseillee"] is None, "28 étapes à faire : rien à conseiller"

    etapes = list(detail["etapes"])
    for e in etapes[:-1]:
        r = await client.patch(
            f"/eod/{ident}/etapes/{e['id']}",
            headers=entetes(operateur),
            json={"statut": "Complété"},
        )
        assert r.status_code == 200, r.text
    r = await client.patch(
        f"/eod/{ident}/etapes/{etapes[-1]['id']}",
        headers=entetes(operateur),
        json={
            "statut": "Anomalie",
            "observation": {"texte": "Sauvegarde post-EOD relancée à la main."},
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["cloture_conseillee"] == "Clôturé avec réserves"


async def test_clore_une_nuit_inachevee_exige_de_dire_pourquoi(
    client: AsyncClient, session: AsyncSession
) -> None:
    """On ne l'interdit pas — une soirée s'arrête parfois — mais les étapes restées à faire
    doivent pouvoir se relire."""
    operateur = await creer_utilisateur(session, email="eod.inachevee@afgbank.ml")
    ident = await _ouvrir(client, operateur, "2026-09-05")
    r = await client.post(
        f"/eod/{ident}/transition", headers=entetes(operateur), json={"vers": "En cours"}
    )
    assert r.status_code == 200, r.text

    r = await client.post(
        f"/eod/{ident}/transition", headers=entetes(operateur), json={"vers": "Clôturé"}
    )
    assert r.status_code == 400, r.text

    r = await client.post(
        f"/eod/{ident}/transition",
        headers=entetes(operateur),
        json={"vers": "Clôturé", "note": "Arrêt décidé : bascule reprise au matin avec l'éditeur."},
    )
    assert r.status_code == 200, r.text
    assert r.json()["statut"] == "Clôturé"


async def test_la_note_de_cloture_rejoint_le_journal_de_bord(
    client: AsyncClient, session: AsyncSession
) -> None:
    operateur = await creer_utilisateur(session, email="eod.note@afgbank.ml")
    ident = await _ouvrir(client, operateur, "2026-09-04")
    await client.post(
        f"/eod/{ident}/transition", headers=entetes(operateur), json={"vers": "En cours"}
    )
    await client.post(
        f"/eod/{ident}/transition",
        headers=entetes(operateur),
        json={"vers": "Annulé", "note": "Maintenance éditeur : pas d'EOD ce soir."},
    )
    texte = await session.scalar(
        text("SELECT texte FROM core.note WHERE activite_id = cast(:id as uuid)"), {"id": ident}
    )
    assert texte == "Maintenance éditeur : pas d'EOD ce soir."


# --- Le journal d'une étape ---------------------------------------------------------------------
#
# C'est la raison d'être des observations : sur « PART 3 », une agence bloque, on relance ; une
# autre bloque vingt minutes plus tard, on relance encore. Le champ unique d'avant gardait la
# dernière phrase tapée et effaçait les précédentes — au matin, il ne restait rien à relire.


async def test_les_relances_d_agence_s_empilent_au_lieu_de_s_ecraser(
    client: AsyncClient, session: AsyncSession
) -> None:
    operateur = await creer_utilisateur(session, email="eod.relances@afgbank.ml")
    ident = await _ouvrir(client, operateur, "2026-09-01")
    etape = _etape(
        await _detail(client, operateur, ident), "EOD till Post MARKBOD for all branches"
    )

    for agence, quand, quoi in (
        ("Agence 11 Kayes", "01H12", "POSTEOPD3 relancé, reprise OK."),
        ("Agence 15 Segou", "01H40", "Session bloquée, relancée après purge."),
    ):
        r = await client.post(
            f"/eod/{ident}/etapes/{etape['id']}/observations",
            headers=entetes(operateur),
            json={"nature": "incident", "agence": agence, "relance": quand, "texte": quoi},
        )
        assert r.status_code == 201, r.text

    detail = r.json()
    journal = _etape(detail, "EOD till Post MARKBOD for all branches")["observations"]
    assert [o["agence"] for o in journal] == ["Agence 11 Kayes", "Agence 15 Segou"]
    assert all(o["relance_le"] is not None for o in journal)
    # L'auteur est figé à l'écriture : un journal dont les lignes perdent leur signataire ne
    # prouve rien.
    assert all(o["auteur"] is not None for o in journal)
    # Deux agences relancées, et l'étape n'est pas pour autant en anomalie : les deux comptes ne
    # se déduisent pas l'un de l'autre.
    assert detail["incidents"] == 2
    assert detail["anomalies"] == 0


async def test_un_incident_d_agence_doit_dire_quelle_agence(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Sans l'agence, l'incident ne répond pas à la première question qu'on lui pose."""
    operateur = await creer_utilisateur(session, email="eod.sansagence@afgbank.ml")
    ident = await _ouvrir(client, operateur, "2026-08-31")
    detail = await _detail(client, operateur, ident)
    etape = _etape(detail, "Post EOFI_1 for all branch including 000 BAM")

    r = await client.post(
        f"/eod/{ident}/etapes/{etape['id']}/observations",
        headers=entetes(operateur),
        json={"nature": "incident", "texte": "Bloqué, relancé."},
    )
    assert r.status_code == 400, r.text
    assert "agence" in r.json()["detail"]


async def test_un_incident_sans_heure_saisie_est_consigne_a_l_instant(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Consigner un incident, c'est le consigner sur le moment : pas une frappe de plus à 2 h."""
    operateur = await creer_utilisateur(session, email="eod.heureauto@afgbank.ml")
    ident = await _ouvrir(client, operateur, "2026-08-30")
    detail = await _detail(client, operateur, ident)
    etape = _etape(detail, "EOD till Post EOFI_3 for branch 000 BHO")

    r = await client.post(
        f"/eod/{ident}/etapes/{etape['id']}/observations",
        headers=entetes(operateur),
        json={"nature": "incident", "agence": "000 BHO", "texte": "Relancé."},
    )
    assert r.status_code == 201, r.text
    journal = _etape(r.json(), "EOD till Post EOFI_3 for branch 000 BHO")["observations"]
    assert journal[0]["relance_le"] is not None


async def test_une_heure_de_relance_illisible_est_refusee_en_le_disant(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le serveur ne devine pas : une heure fausse au rapport vaut moins qu'un refus expliqué."""
    operateur = await creer_utilisateur(session, email="eod.heurefausse@afgbank.ml")
    ident = await _ouvrir(client, operateur, "2026-08-29")
    etape = _etape(await _detail(client, operateur, ident), "EODM")

    r = await client.post(
        f"/eod/{ident}/etapes/{etape['id']}/observations",
        headers=entetes(operateur),
        json={
            "nature": "incident",
            "agence": "Agence 17 Sikasso",
            "relance": "vers minuit",
            "texte": "Relancé.",
        },
    )
    assert r.status_code == 400, r.text
    assert "01H12" in r.json()["detail"], "le refus doit montrer ce qui est attendu"


async def test_une_observation_ne_se_reecrit_ni_ne_s_efface(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Append-only : une observation corrigée après coup ne prouverait plus rien (principe n° 4)."""
    operateur = await creer_utilisateur(session, email="eod.appendonly@afgbank.ml")
    ident = await _ouvrir(client, operateur, "2026-08-28")
    etape = _etape(await _detail(client, operateur, ident), "Date Check")

    r = await client.post(
        f"/eod/{ident}/etapes/{etape['id']}/observations",
        headers=entetes(operateur),
        json={"texte": "Date du jour conforme."},
    )
    assert r.status_code == 201, r.text
    observation = _etape(r.json(), "Date Check")["observations"][0]

    # Aucune route ne sert la correction ni la suppression d'une observation : l'API n'offre pas
    # le geste, et ce n'est pas un oubli. L'erreur se rattrape par l'observation suivante.
    chemin = f"/eod/{ident}/etapes/{etape['id']}/observations/{observation['id']}"
    assert (await client.patch(chemin, headers=entetes(operateur), json={})).status_code in (
        404,
        405,
    )
    assert (await client.delete(chemin, headers=entetes(operateur))).status_code in (404, 405)


async def test_un_passant_ne_consigne_rien_sur_la_nuit_d_un_autre(
    client: AsyncClient, session: AsyncSession
) -> None:
    operateur = await creer_utilisateur(session, email="eod.journal.titulaire@afgbank.ml")
    passant = await creer_utilisateur(session, email="eod.journal.passant@afgbank.ml")
    ident = await _ouvrir(client, operateur, "2026-08-27")
    etape = _etape(await _detail(client, operateur, ident), "Date Check")

    r = await client.post(
        f"/eod/{ident}/etapes/{etape['id']}/observations",
        headers=entetes(passant),
        json={"texte": "Vu de loin."},
    )
    assert r.status_code == 403, r.text


async def test_le_reseau_d_agences_est_propose_a_la_saisie(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Proposer la liste officielle évite « Kayes », « AGENCE KAYES » et « Agence 11 Kayes »."""
    operateur = await creer_utilisateur(session, email="eod.agences@afgbank.ml")
    r = await client.get("/eod/agences", headers=entetes(operateur))
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


# --- Supprimer une soirée -----------------------------------------------------------------------


async def test_seul_l_admin_supprime_une_soiree(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Une nuit ouverte sur la mauvaise date bloque la bonne : l'unicité porte sur la journée.

    La corriger est impossible — c'est elle qui fait l'identité de la soirée — donc il faut
    pouvoir l'effacer. Mais l'effacer reste le geste de l'administrateur, et la journée libérée
    doit pouvoir se rouvrir juste après.
    """
    operateur = await creer_utilisateur(session, email="eod.suppr.operateur@afgbank.ml")
    admin = await creer_utilisateur(session, email="eod.suppr.admin@afgbank.ml", profil="ADMIN")
    ident = await _ouvrir(client, operateur, "2026-06-10")

    r = await client.delete(f"/eod/{ident}", headers=entetes(operateur))
    assert r.status_code == 403, r.text

    r = await client.delete(f"/eod/{ident}", headers=entetes(admin))
    assert r.status_code == 204, r.text
    r = await client.get(f"/eod/{ident}", headers=entetes(admin))
    assert r.status_code == 404

    # La journée comptable est libre : c'est tout l'objet de la suppression.
    r = await client.post(
        "/eod", json={"journee": "2026-06-10"}, headers=entetes(operateur)
    )
    assert r.status_code in (200, 201), r.text


# --- Le rapport du soir -------------------------------------------------------------------------


async def test_le_rapport_du_soir_s_exporte(client: AsyncClient, session: AsyncSession) -> None:
    """C'est la sortie attendue par la hiérarchie : elle doit exister sans détour."""
    operateur = await creer_utilisateur(session, email="eod.rapport@afgbank.ml")
    ident = await _ouvrir(client, operateur, "2026-09-03")

    r = await client.get(f"/eod/{ident}/rapport?format=csv", headers=entetes(operateur))
    assert r.status_code == 200, r.text
    corps = r.content.decode("utf-8-sig", errors="replace")
    assert "Intégration fichier CARTHAGO" in corps
    assert "PART 1" in corps

    r = await client.get(f"/eod/{ident}/rapport", headers=entetes(operateur))
    assert r.status_code == 200
    assert "spreadsheet" in r.headers["content-type"]


async def test_la_liste_s_exporte_avec_ses_colonnes(
    client: AsyncClient, session: AsyncSession
) -> None:
    """L'export de la LISTE (et non d'une soirée) : comparer les nuits entre elles.

    Il porte le socle commun — référence, statut, responsable, SLA — plus ce qui ne se lit que
    sur une soirée : la journée comptable close, le nombre d'étapes, les anomalies, les relances
    d'agence et la plage réellement tenue. Sans ces cinq-là, le fichier ne répondrait à aucune des
    questions pour lesquelles on l'ouvre.
    """
    operateur = await creer_utilisateur(session, email="eod.export.liste@afgbank.ml")
    await _ouvrir(client, operateur, "2026-07-15")

    r = await client.get("/eod/export?format=csv", headers=entetes(operateur))
    assert r.status_code == 200, r.text
    corps = r.content.decode("utf-8-sig", errors="replace")
    entete = corps.splitlines()[0]
    for colonne in (
        "Référence",
        "Statut",
        "Avancement",
        "Journée comptable",
        "Étapes",
        "Anomalies",
        "Relances d'agence",
        "Début effectif",
        "Fin effective",
    ):
        assert colonne in entete, entete
    # Et pas de colonne « Commentaires » : une soirée ne se commente pas, elle se pointe — la
    # colonne vaudrait 0 sur toutes les lignes.
    assert "Commentaires" not in entete
    assert "15/07/2026" in corps

    r = await client.get("/eod/export?format=xlsx", headers=entetes(operateur))
    assert r.status_code == 200
    assert "spreadsheet" in r.headers["content-type"]


async def test_le_rapport_porte_les_relances_d_agence(
    client: AsyncClient, session: AsyncSession
) -> None:
    """L'heure, l'agence et ce qui a été fait : ce que la hiérarchie cherche si la nuit dérape."""
    operateur = await creer_utilisateur(session, email="eod.rapport.relance@afgbank.ml")
    ident = await _ouvrir(client, operateur, "2026-08-26")
    etape = _etape(
        await _detail(client, operateur, ident), "EOD till last stage for all branches POSTEOPD3"
    )
    r = await client.post(
        f"/eod/{ident}/etapes/{etape['id']}/observations",
        headers=entetes(operateur),
        json={
            "nature": "incident",
            "agence": "Agence 11 Kayes",
            "relance": "01H12",
            "texte": "POSTEOPD3 relancé, reprise OK.",
        },
    )
    assert r.status_code == 201, r.text

    r = await client.get(f"/eod/{ident}/rapport?format=csv", headers=entetes(operateur))
    corps = r.content.decode("utf-8-sig", errors="replace")
    assert "01H12" in corps
    assert "Agence 11 Kayes" in corps
    assert "POSTEOPD3 relancé, reprise OK." in corps


async def test_un_incident_pose_une_etape_relance_sous_l_etape_qui_a_bloque(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le rapport réel l'écrit ainsi : sous l'étape en anomalie, « RELANCE | 20H15 | 20H20 |
    Complete ». Une relance a un début, une fin, un verdict — c'est une étape, pas une note."""
    operateur = await creer_utilisateur(session, email="eod.relance.etape@afgbank.ml")
    ident = await _ouvrir(client, operateur, "2026-08-25")
    parent = _etape(
        await _detail(client, operateur, ident), "Post EOFI_1 for all branch including 000 BAM"
    )

    r = await client.post(
        f"/eod/{ident}/etapes/{parent['id']}/observations",
        headers=entetes(operateur),
        json={
            "nature": "incident",
            "agence": "018",
            "relance": "20H15",
            "texte": "Error code AE-VALS-053, relance du batch.",
        },
    )
    assert r.status_code == 201, r.text
    etapes = r.json()["etapes"]

    # Juste sous le parent, même section, En cours depuis l'heure de relance, l'agence en clair.
    rang = next(i for i, e in enumerate(etapes) if e["id"] == parent["id"])
    relance = etapes[rang + 1]
    assert relance["relance_de"] == parent["id"]
    assert relance["libelle"] == "RELANCE · 018"
    assert relance["section"] == parent["section"]
    assert relance["agence"] == "018"
    assert relance["statut"] == "En cours"
    assert relance["debut"] is not None and relance["debut"].endswith("T20:15:00Z")
    # Une étape de plus dans la nuit : l'avancement la compte, comme le rapport la compte.
    assert r.json()["nb_etapes"] == 29

    # Elle se termine comme n'importe quelle étape.
    r = await client.post(
        f"/eod/{ident}/etapes/{relance['id']}/pointer",
        headers=entetes(operateur),
        json={"quoi": "fin"},
    )
    assert r.status_code == 200, r.text
    finie = next(e for e in r.json()["etapes"] if e["id"] == relance["id"])
    assert finie["statut"] == "Complété"
    assert finie["fin"] is not None

    # Et le rapport du soir porte la ligne RELANCE avec ses heures — la forme que la hiérarchie
    # lit depuis toujours.
    r = await client.get(f"/eod/{ident}/rapport?format=csv", headers=entetes(operateur))
    corps = r.content.decode("utf-8-sig", errors="replace")
    assert "RELANCE · 018" in corps
    assert "20H15" in corps


async def test_une_simple_note_ne_pose_aucune_relance(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Seul l'incident d'agence relance quelque chose ; une observation ordinaire n'ajoute rien."""
    operateur = await creer_utilisateur(session, email="eod.note.sans.relance@afgbank.ml")
    ident = await _ouvrir(client, operateur, "2026-08-24")
    etape = _etape(await _detail(client, operateur, ident), "EODM")
    r = await client.post(
        f"/eod/{ident}/etapes/{etape['id']}/observations",
        headers=entetes(operateur),
        json={"nature": "note", "texte": "Batch terminé sans rejet."},
    )
    assert r.status_code == 201, r.text
    assert r.json()["nb_etapes"] == 28
    assert all(e["relance_de"] is None for e in r.json()["etapes"])


async def test_la_liste_resume_chaque_nuit(client: AsyncClient, session: AsyncSession) -> None:
    """La liste doit dire d'un coup d'œil où en est la nuit et si elle a dérapé."""
    operateur = await creer_utilisateur(session, email="eod.liste@afgbank.ml")
    await _ouvrir(client, operateur, "2026-09-02")

    r = await client.get("/eod", headers=entetes(operateur))
    assert r.status_code == 200, r.text
    lignes = [e for e in r.json()["elements"] if e["journee"] == "2026-09-02"]
    assert len(lignes) == 1
    assert lignes[0]["nb_etapes"] == 28
    assert lignes[0]["reste"] == 28
    assert lignes[0]["anomalies"] == 0
