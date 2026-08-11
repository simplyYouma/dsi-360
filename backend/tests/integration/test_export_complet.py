"""Les exports d'activités disent TOUT ce que le dossier porte.

Un export sert à travailler hors de l'écran : à recouper, à justifier, à rendre compte. Amputé de
ses échéances, de ses jours de dépassement ou de son gestionnaire, il oblige à revenir dans
l'application — donc à ressaisir. On vérifie ici que rien de ce qui existe ne reste au chaud :
les colonnes communes, ET celles que seuls certains modules portent.
"""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_activite, creer_utilisateur, entetes


async def _entetes_export(client: AsyncClient, base: str, uid: str) -> list[str]:
    r = await client.get(f"{base}/export?format=csv", headers=entetes(uid))
    assert r.status_code == 200, r.text
    return r.content.decode("utf-8-sig").splitlines()[0].split(";")


async def _lignes_export(client: AsyncClient, base: str, uid: str) -> list[str]:
    r = await client.get(f"{base}/export?format=csv", headers=entetes(uid))
    assert r.status_code == 200, r.text
    return r.content.decode("utf-8-sig").splitlines()


#: Le socle : ce que tout dossier porte, quel que soit son module.
_COMMUNES = (
    "Référence",
    "Titre",
    "Statut",
    "Priorité",
    "Impact",
    "Urgence",
    "Catégorie",
    "Direction",
    "Demandeur",
    "Responsable",
    "Contributeur",
    "Description",
    "Créé le",
    "Échéance de prise en charge",
    "Échéance de résolution",
    "Situation SLA",
    "Jours de dépassement",
    "Résolu le",
    "Clôturé le",
    "Délai de traitement (jours)",
    "Commentaires",
)


async def test_export_porte_toutes_les_colonnes_communes(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await creer_utilisateur(session, email="exp.commun@afgbank.ml", profil="ADMIN")
    colonnes = await _entetes_export(client, "/projets", admin)
    for attendue in _COMMUNES:
        assert attendue in colonnes, colonnes


async def test_incidents_exportent_gestionnaire_et_niveau(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Modules importés : le gestionnaire du fichier et le niveau qui s'en déduit (ADR-0005)."""
    admin = await creer_utilisateur(session, email="exp.inc@afgbank.ml", profil="ADMIN")
    colonnes = await _entetes_export(client, "/incidents", admin)
    for attendue in ("Gestionnaire", "Niveau de support", "Transféré DBS"):
        assert attendue in colonnes, colonnes


async def test_changements_exportent_le_dossier_rfc(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le dossier ITIL d'un changement : ce qui a été analysé, prévu, et constaté après coup."""
    admin = await creer_utilisateur(session, email="exp.chg@afgbank.ml", profil="ADMIN")
    colonnes = await _entetes_export(client, "/changements", admin)
    for attendue in (
        "Analyse d'impact",
        "Analyse de risque",
        "Plan de déploiement",
        "Plan de retour arrière",
        "Bilan post-implémentation",
        "Avancement (%)",
    ):
        assert attendue in colonnes, colonnes


async def test_risques_exportent_la_revue_periodique(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await creer_utilisateur(session, email="exp.risq@afgbank.ml", profil="ADMIN")
    colonnes = await _entetes_export(client, "/risques", admin)
    for attendue in ("Périodicité de revue", "Dernière revue", "Prochaine revue"):
        assert attendue in colonnes, colonnes


async def test_pas_de_colonne_qu_un_module_ne_peut_pas_remplir(
    client: AsyncClient, session: AsyncSession
) -> None:
    """L'exhaustivité n'est pas le bruit : un projet n'a ni dossier RFC, ni niveau de support."""
    admin = await creer_utilisateur(session, email="exp.bruit@afgbank.ml", profil="ADMIN")
    colonnes = await _entetes_export(client, "/projets", admin)
    for absente in ("Analyse d'impact", "Niveau de support", "Transféré DBS"):
        assert absente not in colonnes, colonnes


async def test_les_jours_de_depassement_sont_comptes(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le chiffre qu'on vient chercher : de combien l'échéance a-t-elle été dépassée ?"""
    admin = await creer_utilisateur(session, email="exp.retard@afgbank.ml", profil="ADMIN")
    ident = await creer_activite(
        session, module="projet", reference="PRJ-2026-09001", responsable_id=admin
    )
    # Échéance dépassée depuis 4 j 23 h, dossier toujours ouvert : le compteur court. Un jour
    # entamé compte pour un jour (arrondi au supérieur, comme le retard final) : on attend 5.
    # Borne choisie loin d'un compte rond : la durée du test ne peut pas la faire basculer.
    await session.execute(
        text("UPDATE core.activite SET sla_resolution_le = :quand WHERE id = cast(:id as uuid)"),
        {"quand": datetime.now(UTC) - timedelta(days=4, hours=23), "id": ident},
    )
    await session.commit()

    lignes = await _lignes_export(client, "/projets", admin)
    colonnes = lignes[0].split(";")
    ligne = next(x for x in lignes[1:] if "PRJ-2026-09001" in x).split(";")
    depassement = ligne[colonnes.index("Jours de dépassement")]
    situation = ligne[colonnes.index("Situation SLA")]

    assert depassement == "5", ligne
    assert situation == "Dépassé", ligne


async def test_un_dossier_sans_echeance_laisse_la_case_vide(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Vide veut dire « pas d'échéance » ; zéro voudrait dire « dans les délais ». Deux sens."""
    admin = await creer_utilisateur(session, email="exp.sansech@afgbank.ml", profil="ADMIN")
    ident = await creer_activite(
        session, module="projet", reference="PRJ-2026-09002", responsable_id=admin
    )
    await session.execute(
        text("UPDATE core.activite SET sla_resolution_le = NULL WHERE id = cast(:id as uuid)"),
        {"id": ident},
    )
    await session.commit()

    lignes = await _lignes_export(client, "/projets", admin)
    colonnes = lignes[0].split(";")
    ligne = next(x for x in lignes[1:] if "PRJ-2026-09002" in x).split(";")
    assert ligne[colonnes.index("Jours de dépassement")] == "", ligne


async def test_export_xlsx_reste_ouvrable(client: AsyncClient, session: AsyncSession) -> None:
    """Le classeur doit s'ouvrir : c'est le format que la direction reçoit."""
    admin = await creer_utilisateur(session, email="exp.xlsx@afgbank.ml", profil="ADMIN")
    await creer_activite(
        session, module="projet", reference="PRJ-2026-09003", responsable_id=admin
    )

    r = await client.get("/projets/export?format=xlsx", headers=entetes(admin))
    assert r.status_code == 200, r.text
    # Signature d'un .xlsx (archive ZIP) : le fichier est bien un classeur, pas un message d'erreur.
    assert r.content[:2] == b"PK"
    assert len(r.content) > 1000
