"""Schémas Pydantic d'entrée/sortie de l'API (couche interface)."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class Connexion(BaseModel):
    email: str
    mot_de_passe: str = Field(min_length=1)


class Rafraichissement(BaseModel):
    refresh: str


class ChangementMotDePasse(BaseModel):
    ancien: str = Field(min_length=1)
    nouveau: str = Field(min_length=8)


class MotDePasseOublie(BaseModel):
    email: str = Field(min_length=3, max_length=160)


class Reinitialisation(BaseModel):
    jeton: str = Field(min_length=10)
    nouveau: str = Field(min_length=8)


class Jetons(BaseModel):
    acces: str
    refresh: str
    type_jeton: str = "bearer"


class MoiReponse(BaseModel):
    id: str
    email: str
    nom: str
    prenom: str
    profil: str
    profil_libelle: str
    transverse: bool
    direction: str | None
    doit_changer_mdp: bool
    acces: list[str]


# --- Activités / Incidents ---


class ResponsableBref(BaseModel):
    prenom: str
    nom: str
    email: str


class Contributeur(BaseModel):
    """Acteur secondaire : commente et suit l'activité, sans en être responsable."""

    id: str
    prenom: str
    nom: str
    email: str
    # Décision d'un valideur : APPROUVE / REJETE, ou None (en attente / non applicable).
    decision: str | None = None


class DecisionDemande(BaseModel):
    decision: Literal["APPROUVE", "REJETE"]


Periodicite = Literal["Mensuelle", "Trimestrielle", "Semestrielle", "Annuelle"]


class RevueDemande(BaseModel):
    """Planification d'une revue périodique (accès, risques, comités…)."""

    periodicite: Periodicite | None = None
    prochaine_revue: date | None = None


class EvaluationDemande(BaseModel):
    """Ré-évaluation de l'impact et/ou de l'urgence (recalcule priorité + échéances SLA)."""

    impact: int | None = Field(default=None, ge=1, le=5)
    urgence: int | None = Field(default=None, ge=1, le=5)


class MaTache(BaseModel):
    """Une tâche assignée à l'utilisateur connecté, avec son activité parente (navigation)."""

    id: str
    titre: str
    statut: str
    echeance: date | None
    activite_id: str
    module: str
    reference: str
    activite_titre: str


class ActiviteCreation(BaseModel):
    titre: str = Field(min_length=3, max_length=200)
    description: str | None = None
    impact: int = Field(ge=1, le=5)
    urgence: int = Field(ge=1, le=5)
    categorie_id: str | None = None
    direction_id: str | None = None
    responsable_id: str | None = None
    demandeur: str | None = Field(default=None, max_length=160)


class EntreeHistorique(BaseModel):
    statut: str
    horodatage: datetime
    acteur: str | None


class ActiviteResume(BaseModel):
    id: str
    reference: str
    titre: str
    statut: str
    priorite: int
    categorie: str | None
    direction: str | None
    sla_resolution_le: datetime | None
    statut_sla: str
    cree_le: datetime
    responsable: ResponsableBref | None
    demandeur: str | None
    gestionnaire: str | None
    responsable_id: str | None
    nb_commentaires: int = 0
    nb_non_vus: int = 0


class ActiviteDetail(ActiviteResume):
    description: str | None
    categorie_id: str | None = None
    impact: int | None
    urgence: int | None
    sla_prise_en_charge_le: datetime | None
    resolu_le: datetime | None
    cloture_le: datetime | None
    transitions_possibles: list[str]
    etats: list[str]
    historique: list[EntreeHistorique]
    contributeurs: list[Contributeur] = []
    valideurs: list[Contributeur] = []
    # Avancement dérivé des tâches (modules avec tâches : changement…). 0 sinon.
    avancement: int = 0
    # Niveau de support ITIL (1 = N1 Service Desk, 2 = N2, 3 = N3). Défaut N1.
    niveau_support: int = 1
    # Champs RFC (changement, ITIL SI-12.04) — stockés dans donnees, None si non renseignés.
    analyse_impact: str | None = None
    analyse_risque: str | None = None
    plan_deploiement: str | None = None
    plan_retour_arriere: str | None = None
    bilan_post_implementation: str | None = None
    # Revue périodique (risques, cybersécurité, gouvernance) — stockés dans donnees.
    periodicite: str | None = None
    prochaine_revue: date | None = None


class PageActivites(BaseModel):
    elements: list[ActiviteResume]
    total: int
    page: int
    taille: int


class TransitionDemande(BaseModel):
    vers: str = Field(min_length=1)
    # Justification (obligatoire pour certaines transitions : suspension/clôture d'un projet).
    note: str | None = Field(default=None, max_length=2000)


class NoteItem(BaseModel):
    """Note du journal de bord d'un projet (justifications de suspension/clôture comprises)."""

    id: str
    texte: str
    contexte: str | None
    auteur: str | None
    cree_le: datetime


class NoteCreation(BaseModel):
    texte: str = Field(min_length=3, max_length=2000)


class LienItem(BaseModel):
    """Lien utile d'un projet (espace documentaire, wiki, dossier réseau…)."""

    id: str
    libelle: str
    url: str
    cree_le: datetime


class LienCreation(BaseModel):
    libelle: str = Field(min_length=2, max_length=120)
    url: str = Field(min_length=8, max_length=2000, pattern=r"^(https?|file)://.+")


class AssignationDemande(BaseModel):
    responsable_id: str | None = None


class CategorieDemande(BaseModel):
    categorie_id: str | None = None


class ActiviteMaj(BaseModel):
    """Édition en place d'une activité : titre/description + champs RFC (changement).

    Les champs RFC (analyse d'impact/risque, plans, bilan) sont stockés dans `donnees` (ITIL
    SI-12.04). Tous optionnels : seuls les champs fournis sont modifiés.
    """

    titre: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = None
    analyse_impact: str | None = None
    analyse_risque: str | None = None
    plan_deploiement: str | None = None
    plan_retour_arriere: str | None = None
    bilan_post_implementation: str | None = None


class ContributeurDemande(BaseModel):
    utilisateur_id: str = Field(min_length=1)


class AssignationLot(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=500)
    responsable_id: str | None = None


class ResultatAssignationLot(BaseModel):
    assignes: int


class AgentItem(BaseModel):
    id: str
    nom: str
    profil: str


class MonTicket(BaseModel):
    module: str
    id: str
    reference: str
    titre: str
    statut: str
    priorite: int | None
    statut_sla: str
    sla_resolution_le: datetime | None
    demandeur: str | None
    cree_le: datetime
    nb_commentaires: int = 0
    nb_non_vus: int = 0


class CompteLibelle(BaseModel):
    libelle: str
    valeur: int


class JourResolus(BaseModel):
    jour: str
    resolus: int


class AgentBref(BaseModel):
    nom: str
    profil: str
    direction: str | None


class MesStats(BaseModel):
    """Tableau de bord personnel de l'agent connecté."""

    agent: AgentBref
    ouverts: int
    a_lheure: int
    approche: int
    en_retard: int
    resolus_7j: int
    resolus_30j: int
    respect_sla: int  # pourcentage
    mttr_jours: float | None  # délai moyen de résolution (90 j)
    plus_ancien_jours: int | None
    par_priorite: list[CompteLibelle]
    par_module: list[CompteLibelle]
    par_statut: list[CompteLibelle]
    tendance: list[JourResolus]


class CreationReponse(BaseModel):
    id: str


class CategorieItem(BaseModel):
    id: str
    code: str
    libelle: str


class CreationCategorie(BaseModel):
    module: str = Field(min_length=1, max_length=40)
    libelle: str = Field(min_length=1, max_length=80)


class DocumentItem(BaseModel):
    id: str
    nom: str
    type_mime: str
    taille: int
    depose_par: str | None
    depose_le: datetime


class DocumentRenommage(BaseModel):
    nom: str = Field(min_length=1, max_length=200)


# --- Notifications ---


class NotificationItem(BaseModel):
    id: int
    type: str
    titre: str
    message: str
    lu: bool
    cree_le: datetime
    module: str | None
    activite_id: str | None


class ResultatRecherche(BaseModel):
    module: str
    id: str
    reference: str
    titre: str
    statut: str


class NotificationsReponse(BaseModel):
    elements: list[NotificationItem]
    non_lus: int


class PreferencesNotif(BaseModel):
    interne: bool = True
    email: bool = True
    teams: bool = False
    whatsapp: bool = False


# --- Commentaires (fil de discussion interne DSI) ---


class CommentaireItem(BaseModel):
    id: int
    auteur: str
    auteur_id: str | None = None
    texte: str
    cree_le: datetime
    edite: bool = False
    nb_vues: int = 0
    vu: bool = False


class CommentaireMaj(BaseModel):
    texte: str = Field(min_length=1, max_length=4000)


class LecteurCommentaire(BaseModel):
    """Un lecteur d'un commentaire (accusé de lecture)."""

    nom: str
    vu_le: datetime


class CommentaireCreation(BaseModel):
    texte: str = Field(min_length=1, max_length=4000)
    # Identifiants des personnes mentionnées avec @ (notifiées en interne).
    mentions: list[str] = []


# --- Ingestion / Ticketing ---


class RapportImport(BaseModel):
    total: int
    incidents: int
    demandes: int
    crees: int
    mis_a_jour: int
    inchanges: int
    demandeurs_crees: int
    gestionnaires_crees: int


class DemandeurItem(BaseModel):
    id: str
    nom_complet: str
    direction: str | None
    email: str | None
    actif: bool


class PageDemandeurs(BaseModel):
    elements: list[DemandeurItem]
    total: int
    page: int
    taille: int


class DemandeurCreation(BaseModel):
    nom_complet: str = Field(min_length=2, max_length=160)
    direction_code: str | None = None
    email: str | None = None


class DemandeurMaj(BaseModel):
    nom_complet: str = Field(min_length=2, max_length=160)
    direction_code: str | None = None
    email: str | None = None
    actif: bool


# --- Administration ---


class ProfilItem(BaseModel):
    code: str
    libelle: str


class DirectionItem(BaseModel):
    code: str
    libelle: str


class UtilisateurResume(BaseModel):
    id: str
    email: str
    nom: str
    prenom: str
    profil: str
    profil_libelle: str
    direction: str | None
    niveau_support: int | None = None
    actif: bool
    expire_le: datetime | None = None
    doit_changer_mdp: bool


class PageUtilisateurs(BaseModel):
    elements: list[UtilisateurResume]
    total: int
    page: int
    taille: int


class CreationUtilisateur(BaseModel):
    email: str
    nom: str
    prenom: str
    profil_code: str
    direction_code: str | None = None
    niveau_support: int | None = Field(default=None, ge=1, le=3)
    expire_le: datetime | None = None


class MajUtilisateur(BaseModel):
    nom: str
    prenom: str
    profil_code: str
    direction_code: str | None = None
    niveau_support: int | None = Field(default=None, ge=1, le=3)
    actif: bool
    expire_le: datetime | None = None


class RoleAcces(BaseModel):
    profil: str
    libelle: str
    acces: list[str]


class MatriceAcces(BaseModel):
    modules: list[str]
    roles: list[RoleAcces]


class MajAcces(BaseModel):
    profil: str
    acces: list[str]


class SlaRegleItem(BaseModel):
    priorite: int = Field(ge=1, le=5)
    prise_en_charge_minutes: int = Field(gt=0)
    resolution_minutes: int = Field(gt=0)


class MajSlaRegles(BaseModel):
    module: str = Field(min_length=1, max_length=40)
    regles: list[SlaRegleItem] = Field(min_length=1, max_length=5)


class EntreeJournal(BaseModel):
    horodatage: datetime
    acteur: str | None
    module: str | None
    action: str
    cible: str | None


class PageJournal(BaseModel):
    elements: list[EntreeJournal]
    total: int
    page: int
    taille: int


# --- Projets ---


class ProjetCreation(BaseModel):
    titre: str = Field(min_length=3, max_length=200)
    description: str | None = None
    direction_id: str | None = None
    responsable_id: str | None = None  # chef de projet
    sponsor: str | None = None
    budget: float | None = None
    date_debut: str | None = None
    date_fin: str | None = None


class ProjetMaj(BaseModel):
    """Édition en place du cadrage d'un projet (tous champs optionnels)."""

    titre: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = None
    sponsor: str | None = None
    budget: float | None = None
    date_debut: str | None = None
    date_fin: str | None = None
    responsable_id: str | None = None


class ProjetResume(BaseModel):
    id: str
    reference: str
    titre: str
    statut: str
    direction: str | None
    chef: ResponsableBref | None
    responsable_id: str | None = None
    avancement: int
    budget: float | None
    date_fin: str | None
    cree_le: datetime


class ProjetDetail(ProjetResume):
    description: str | None
    sponsor: str | None
    date_debut: str | None
    transitions_possibles: list[str]


class PageProjets(BaseModel):
    elements: list[ProjetResume]
    total: int
    page: int
    taille: int


class AvancementDemande(BaseModel):
    avancement: int = Field(ge=0, le=100)


class JalonItem(BaseModel):
    id: str
    titre: str
    echeance: date | None
    atteint: bool
    ordre: int


class JalonCreation(BaseModel):
    titre: str = Field(min_length=2, max_length=200)
    echeance: date | None = None
    ordre: int = 0


class JalonMaj(BaseModel):
    titre: str | None = Field(default=None, min_length=2, max_length=200)
    echeance: date | None = None
    atteint: bool | None = None
    ordre: int | None = None


# --- Tâches (d'un projet, d'un changement…) ---

StatutTache = Literal["À faire", "En cours", "Terminée"]


class Tache(BaseModel):
    id: str
    titre: str
    description: str | None
    statut: StatutTache
    assigne: ResponsableBref | None
    assigne_id: str | None
    echeance: date | None
    ordre: int
    nb_commentaires: int = 0
    nb_non_vus: int = 0


class TacheCreation(BaseModel):
    titre: str = Field(min_length=2, max_length=200)
    description: str | None = None
    assigne_id: str | None = None
    echeance: date | None = None
    ordre: int = 0


class TacheMaj(BaseModel):
    titre: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = None
    statut: StatutTache | None = None
    assigne_id: str | None = None
    echeance: date | None = None
    ordre: int | None = None


class ReordreTaches(BaseModel):
    """Nouvel ordre des tâches (liste d'identifiants, position = rang)."""

    ordre: list[str]


# --- Risques IT ---


class RisqueCreation(BaseModel):
    titre: str = Field(min_length=3, max_length=200)
    description: str | None = None
    direction_id: str | None = None
    responsable_id: str | None = None
    categorie_id: str | None = None
    probabilite: int = Field(ge=1, le=5)
    impact: int = Field(ge=1, le=5)


class RisqueResume(BaseModel):
    id: str
    reference: str
    titre: str
    statut: str
    direction: str | None
    responsable: ResponsableBref | None
    responsable_id: str | None
    nb_commentaires: int = 0
    nb_non_vus: int = 0
    probabilite: int
    impact: int
    criticite: int
    cree_le: datetime


class RisqueDetail(RisqueResume):
    description: str | None
    categorie_id: str | None = None
    transitions_possibles: list[str]
    etats: list[str]
    historique: list[EntreeHistorique]
    periodicite: str | None = None
    prochaine_revue: date | None = None


class PageRisques(BaseModel):
    elements: list[RisqueResume]
    total: int
    page: int
    taille: int


# --- Tableau de bord ---


class CartesBord(BaseModel):
    incidents_ouverts: int
    incidents_critiques: int
    respect_sla: int
    demandes_en_cours: int
    projets_en_retard: int
    risques_critiques: int


class SlaBuckets(BaseModel):
    a_lheure: int
    approche: int
    depasse: int


class RepartitionItem(BaseModel):
    module: str
    valeur: int


class SerieSlaItem(BaseModel):
    periode: str
    a_lheure: int
    approche: int
    depasse: int


class TableauBord(BaseModel):
    cartes: CartesBord
    sla: SlaBuckets
    repartition: list[RepartitionItem]
    serie: list[SerieSlaItem]


class AnalyseItem(BaseModel):
    libelle: str
    valeur: int


class KpisAnalyse(BaseModel):
    ouvertes: int
    respect_sla: int
    mttr_jours: float
    en_retard: int


class SlaModule(BaseModel):
    module: str
    a_lheure: int
    approche: int
    depasse: int


class CaseRisque(BaseModel):
    probabilite: int
    impact: int
    valeur: int


class PointTendance(BaseModel):
    periode: str
    crees: int
    resolus: int


class PointActivite(BaseModel):
    jour: int  # 1 = lundi … 7 = dimanche
    heure: int
    valeur: int


class SlaPrioriteItem(BaseModel):
    priorite: str
    dans_delai: int
    total: int
    taux: int


class GestionnaireEval(BaseModel):
    id: str
    gestionnaire: str
    volume: int
    charge: int
    resolus: int
    mttr_jours: float | None
    prise_en_charge_h: float | None


class GestionnaireDetail(GestionnaireEval):
    activite: list[PointActivite]


class AnalysesReponse(BaseModel):
    total: int
    kpis: KpisAnalyse
    par_module: list[AnalyseItem]
    par_direction: list[AnalyseItem]
    par_responsable: list[AnalyseItem]
    par_priorite: list[AnalyseItem]
    sla: SlaBuckets
    sla_par_module: list[SlaModule]
    sla_par_priorite: list[SlaPrioriteItem]
    matrice_risques: list[CaseRisque]
    tendance: list[PointTendance]
    activite: list[PointActivite]
