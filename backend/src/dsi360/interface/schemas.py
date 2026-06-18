"""Schémas Pydantic d'entrée/sortie de l'API (couche interface)."""

from datetime import datetime

from pydantic import BaseModel, Field


class Connexion(BaseModel):
    email: str
    mot_de_passe: str = Field(min_length=1)


class Rafraichissement(BaseModel):
    refresh: str


class ChangementMotDePasse(BaseModel):
    ancien: str = Field(min_length=1)
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


class ActiviteCreation(BaseModel):
    titre: str = Field(min_length=3, max_length=200)
    description: str | None = None
    impact: int = Field(ge=1, le=5)
    urgence: int = Field(ge=1, le=5)
    categorie_id: str | None = None
    direction_id: str | None = None
    responsable_id: str | None = None


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


class ActiviteDetail(ActiviteResume):
    description: str | None
    impact: int | None
    urgence: int | None
    sla_prise_en_charge_le: datetime | None
    resolu_le: datetime | None
    cloture_le: datetime | None
    transitions_possibles: list[str]
    etats: list[str]
    historique: list[EntreeHistorique]


class PageActivites(BaseModel):
    elements: list[ActiviteResume]
    total: int
    page: int
    taille: int


class TransitionDemande(BaseModel):
    vers: str = Field(min_length=1)


class CreationReponse(BaseModel):
    id: str


class CategorieItem(BaseModel):
    id: str
    code: str
    libelle: str


# --- Notifications ---


class NotificationItem(BaseModel):
    id: int
    type: str
    titre: str
    message: str
    lu: bool
    cree_le: datetime


class NotificationsReponse(BaseModel):
    elements: list[NotificationItem]
    non_lus: int


class PreferencesNotif(BaseModel):
    interne: bool = True
    email: bool = True
    teams: bool = False
    whatsapp: bool = False


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
    actif: bool
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
    mot_de_passe: str = Field(min_length=8)


class MajUtilisateur(BaseModel):
    nom: str
    prenom: str
    profil_code: str
    direction_code: str | None = None
    actif: bool


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


class ProjetResume(BaseModel):
    id: str
    reference: str
    titre: str
    statut: str
    direction: str | None
    chef: ResponsableBref | None
    avancement: int
    date_fin: str | None
    cree_le: datetime


class ProjetDetail(ProjetResume):
    description: str | None
    sponsor: str | None
    budget: float | None
    date_debut: str | None
    transitions_possibles: list[str]


class PageProjets(BaseModel):
    elements: list[ProjetResume]
    total: int
    page: int
    taille: int


class AvancementDemande(BaseModel):
    avancement: int = Field(ge=0, le=100)


# --- Risques IT ---


class RisqueCreation(BaseModel):
    titre: str = Field(min_length=3, max_length=200)
    description: str | None = None
    direction_id: str | None = None
    responsable_id: str | None = None
    probabilite: int = Field(ge=1, le=5)
    impact: int = Field(ge=1, le=5)


class RisqueResume(BaseModel):
    id: str
    reference: str
    titre: str
    statut: str
    direction: str | None
    responsable: ResponsableBref | None
    probabilite: int
    impact: int
    criticite: int
    cree_le: datetime


class RisqueDetail(RisqueResume):
    description: str | None
    transitions_possibles: list[str]
    etats: list[str]
    historique: list[EntreeHistorique]


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


class AnalysesReponse(BaseModel):
    total: int
    par_module: list[AnalyseItem]
    par_direction: list[AnalyseItem]
    par_responsable: list[AnalyseItem]
    sla: SlaBuckets
