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
        json={"statut": "Non applicable", "notes": "Pas une fin de mois."},
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

    r = await client.patch(
        f"/eod/{ident}/etapes/{etape['id']}",
        headers=entetes(operateur),
        json={
            "statut": "Anomalie",
            "notes": "Jobs démarrés mais la date reste au 15/09 au lieu du 16/09.",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["anomalies"] == 1


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
        json={"statut": "Anomalie", "notes": "Sauvegarde post-EOD relancée à la main."},
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
