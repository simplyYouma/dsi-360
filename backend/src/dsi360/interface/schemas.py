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


class Incarnation(BaseModel):
    """Compte dont on prend l'identité pour éprouver sa vue (développement seulement)."""

    utilisateur_id: str


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
    # « dev » | « recette » | « prod ». Le front ne peut pas le deviner : un build de production
    # servi depuis un poste de développement mentirait.
    environnement: str = "prod"
    # E-mail de l'administrateur qui incarne ce compte, sinon None. L'écran s'en sert pour ne pas
    # réclamer à un visiteur le mot de passe de celui qu'il regarde.
    incarne_par: str | None = None


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
    cree_le: datetime
    activite_id: str
    module: str
    reference: str
    activite_titre: str
    # RESPONSABLE (chef/gestionnaire) · CONTRIBUTEUR · ASSIGNE (seulement cette tâche).
    role_activite: str


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
    # Compteur figé : l'activité est terminée, le SLA ne court plus (verdict à l'arrêt).
    sla_arrete: bool = False
    cree_le: datetime
    responsable: ResponsableBref | None
    demandeur: str | None
    gestionnaire: str | None
    contributeur: str | None = None
    responsable_id: str | None
    nb_commentaires: int = 0
    nb_non_vus: int = 0
    # Niveau de support, déduit du gestionnaire pour les tickets importés (ADR-0005). Le support
    # voit d'un coup d'œil où se trouve chaque ticket, sans ouvrir les fiches une à une.
    # `None` : aucun gestionnaire renseigné à l'import — ni chez nous, ni chez DBS.
    niveau_support: int | None = 1
    transfere_dbs: bool = False


class PermissionsActivite(BaseModel):
    """Ce que l'appelant peut faire sur *cette* activité, calculé par le serveur.

    L'écran obéit à ces booléens plutôt que de rejouer la règle : sinon elle vit à deux endroits
    et finit par diverger (cf. application/autorisations.py et docs/adr/0003).
    """

    peut_assigner: bool = False  # gestionnaire, chef de projet
    peut_evaluer: bool = False  # impact/urgence, Type du changement
    peut_gerer_acteurs: bool = False  # contributeurs, valideurs
    peut_travailler: bool = False  # transitions, tâches, notes, documents, liens
    peut_decider: bool = False  # approuver / rejeter
    # analyses/plans (RFC) et liens — restent ouverts même après clôture
    peut_completer_dossier: bool = False
    # description d'un incident/demande importé — saisissable par les acteurs (jamais écrasée)
    peut_editer_description: bool = False


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
    en_attente_validation: bool = False
    historique: list[EntreeHistorique]
    contributeurs: list[Contributeur] = []
    valideurs: list[Contributeur] = []
    # Décision de l'appelant s'il est valideur (fige ses boutons) ; verrou de la liste.
    ma_decision: str | None = None
    valideurs_verrouilles: bool = False
    # Avancement dérivé des tâches (modules avec tâches : changement…). 0 sinon.
    avancement: int = 0
    permissions: PermissionsActivite = PermissionsActivite()
    # Champs RFC (changement, ITIL SI-12.04) — stockés dans donnees, None si non renseignés.
    analyse_impact: str | None = None
    analyse_risque: str | None = None
    plan_deploiement: str | None = None
    plan_retour_arriere: str | None = None
    bilan_post_implementation: str | None = None
    # Revue périodique (risques, cybersécurité, gouvernance) — stockés dans donnees.
    periodicite: str | None = None
    prochaine_revue: date | None = None
    derniere_revue: date | None = None
    #: Verdict figé d'un dossier terminé : jours de retard à l'arrivée (0 = dans les délais).
    #: ``None`` : pas d'échéance, ou date de fin inconnue. Le compteur ne court plus, mais le
    #: retard avec lequel on a fini reste une information de pilotage.
    retard_final_jours: int | None = None


class PageActivites(BaseModel):
    elements: list[ActiviteResume]
    total: int
    page: int
    taille: int


# --- Inventaire des équipements (parc matériel) ---


class EquipementResume(BaseModel):
    id: str
    code_immo: str | None
    numero_serie: str | None
    modele: str | None
    designation: str
    emplacement: str | None
    departement: str | None
    #: Détenteur rapproché d'un compte ; sinon le matricule brut du fichier reste seul.
    detenteur: str | None
    matricule: str | None
    date_acquisition: date | None
    valeur_acquisition: float | None
    #: Valeur nette comptable et part amortie, calculées (jamais stockées).
    valeur_nette: float | None
    amorti_pct: int | None
    actif: bool


class EvenementEquipement(BaseModel):
    """Une action journalisée sur l'équipement : la mémoire administrative du matériel."""

    action: str
    horodatage: datetime
    acteur: str | None
    #: Ce qui a changé, en clair (« emplacement : Siège → Agence Kayes ») : l'acheminement.
    detail: str | None = None


class EquipementDetail(EquipementResume):
    #: Dernières actions (création, modifications, import), du plus récent au plus ancien.
    historique: list[EvenementEquipement] = []
    emplacement_id: str | None
    departement_id: str | None
    detenteur_id: str | None
    taux: float | None
    duree_annees: int | None
    source: str
    #: Amortissement détaillé, pour la fiche.
    dotation_annuelle: float | None
    amortissement_cumule: float | None
    fin_amortissement: date | None
    totalement_amorti: bool
    #: Le taux et la durée du fichier se contredisent : donnée à vérifier.
    amortissement_incoherent: bool


class PageEquipements(BaseModel):
    elements: list[EquipementResume]
    total: int
    page: int
    taille: int


class StatsInventaire(BaseModel):
    total: int
    en_service: int
    sortis: int
    sans_detenteur: int
    valeur_acquisition: float


class _EquipementChamps(BaseModel):
    """Champs communs à la création et à la modification (tous facultatifs ici)."""

    code_immo: str | None = Field(default=None, max_length=40)
    numero_serie: str | None = Field(default=None, max_length=80)
    modele: str | None = Field(default=None, max_length=120)
    emplacement_id: str | None = None
    departement_id: str | None = None
    detenteur_id: str | None = None
    taux: float | None = Field(default=None, ge=0, le=100)
    date_acquisition: date | None = None
    duree_annees: int | None = Field(default=None, ge=0, le=99)
    valeur_acquisition: float | None = Field(default=None, ge=0)


class EquipementCreation(_EquipementChamps):
    #: Seul champ exigé : un matériel sans désignation serait introuvable dans la liste.
    designation: str = Field(min_length=2, max_length=200)


class EquipementMaj(_EquipementChamps):
    #: Omis = inchangé (le routeur n'envoie que les champs réellement fournis).
    designation: str | None = Field(default=None, min_length=2, max_length=200)
    #: Sorti du parc (cédé, détruit) : conservé pour l'historique, hors des listes actives.
    actif: bool | None = None


class TrancheParc(BaseModel):
    """Un groupe d'équipements (par lieu, département ou âge) et son poids au bilan."""

    libelle: str
    nombre: int
    valeur_acquisition: float
    valeur_nette: float


class AnalysesParc(BaseModel):
    """Le parc actif en chiffres : localisation, valeur au bilan, obsolescence (lot 4)."""

    parc_actif: int
    valeur_acquisition: float
    valeur_nette: float
    totalement_amortis: int
    #: Ni valeur, ni date, ni taux : rien de calculable — à compléter côté comptabilité.
    sans_donnee_comptable: int
    par_emplacement: list[TrancheParc]
    par_departement: list[TrancheParc]
    par_age: list[TrancheParc]


class CampagneInventaire(BaseModel):
    """Un recensement daté du parc, avec ses comptes par constat."""

    id: str
    libelle: str
    #: OUVERTE | CLOTUREE — une seule campagne ouverte à la fois.
    statut: str
    ouverte_le: datetime
    cloturee_le: datetime | None
    ouverte_par: str | None
    constates: int
    bons: int
    rebuts: int
    casses: int
    #: Posés à la clôture sur tout matériel actif jamais recensé.
    non_retrouves: int


class PageCampagnes(BaseModel):
    campagnes: list[CampagneInventaire]
    #: Taille du parc actif : le dénominateur de l'avancement d'une campagne ouverte.
    parc_actif: int


class CampagneCreation(BaseModel):
    libelle: str = Field(min_length=2, max_length=120)


class ConstatCreation(BaseModel):
    #: NON_RETROUVE ne se saisit pas : il se déduit à la clôture.
    etat: Literal["BON", "REBUT", "CASSE"]


class LigneRecensement(BaseModel):
    """Un équipement du parc face à la campagne : recensé (avec son constat) ou pas encore."""

    id: str
    code_immo: str | None
    designation: str
    numero_serie: str | None
    emplacement: str | None
    detenteur: str | None
    etat: str | None
    constate_le: datetime | None
    constate_par: str | None


class ClotureCampagne(BaseModel):
    #: Le chiffre que la clôture vient chercher.
    non_retrouves: int
    campagne: CampagneInventaire


class ReferentielItem(BaseModel):
    id: str
    libelle: str
    actif: bool


class ReferentielCreation(BaseModel):
    libelle: str = Field(min_length=1, max_length=120)


class StatsListe(BaseModel):
    """Comptes par phase pour l'en-tête d'une liste, plus le retard (qui traverse les phases)."""

    total: int
    en_cours: int
    termines: int
    abandonnes: int
    en_retard: int


class EtatReferentiel(BaseModel):
    """Un statut du cycle de vie d'un module, avec le sens que lui donne le domaine."""

    cle: str
    libelle: str
    #: en_cours | termine | abandonne — l'axe des filtres et des compteurs.
    phase: str
    #: nouveau | actif | attente | recul | succes | echec — la nuance visuelle du badge.
    ton: str
    #: État sans suite : le dossier ne bouge plus, il passe en lecture seule. Distinct de la
    #: phase — « Résolu » est terminé mais reste clôturable et réouvrable.
    verrou: bool


class ApercuLien(BaseModel):
    """Métadonnées d'aperçu d'une URL (unfurl) pour la discussion."""

    url: str
    titre: str | None = None
    description: str | None = None
    image: str | None = None
    site: str | None = None


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


class DescriptionMaj(BaseModel):
    """Saisie de la description d'un ticket importé (incident/demande) par un acteur."""

    description: str | None = None


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
    sla_arrete: bool = False
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


class PageMesTickets(BaseModel):
    elements: list[MonTicket]
    total: int
    a_valider: int = 0  # nombre d'activités où ma décision de valideur est attendue (badge)


class StatsTaches(BaseModel):
    a_faire: int
    en_cours: int
    en_retard: int


class PageMesTaches(BaseModel):
    elements: list[MaTache]
    total: int
    stats: StatsTaches


class MesStats(BaseModel):
    """Tableau de bord personnel de l'agent connecté."""

    agent: AgentBref
    ouverts: int
    a_lheure: int
    approche: int
    en_retard: int
    resolus_periode: int  # résolus sur la période choisie (7/30/90 j, plage, ou tout)
    respect_sla: int  # pourcentage, sur les résolus de la période
    mttr_jours: float | None  # délai moyen de résolution, sur la période
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
    #: Carillon à l'arrivée d'une notification. Suit le compte, pas le navigateur.
    son: bool = True
    teams: bool = False
    whatsapp: bool = False


# --- Commentaires (fil de discussion interne DSI) ---


class ImageCommentaire(BaseModel):
    """Image jointe à un message de discussion (capture d'écran)."""

    id: str
    nom: str
    type_mime: str
    largeur: int | None = None
    hauteur: int | None = None


class CommentaireItem(BaseModel):
    id: int
    auteur: str
    auteur_id: str | None = None
    texte: str
    cree_le: datetime
    edite: bool = False
    nb_vues: int = 0
    vu: bool = False
    images: list[ImageCommentaire] = []


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


class DernierImport(BaseModel):
    """Dernier import d'une nature donnée, lu dans le journal d'audit — la mémoire des dépôts."""

    #: tickets | equipements
    nature: str
    horodatage: datetime
    acteur: str | None
    #: Compte-rendu tel que journalisé (créés, mis à jour…). Les clés varient selon la nature.
    details: dict[str, int]


class EtatImports(BaseModel):
    #: Un élément par nature déjà importée ; vide tant que rien n'a jamais été déposé.
    derniers: list[DernierImport]


class RapportImportEquipements(BaseModel):
    """Compte-rendu d'un import d'inventaire, tel qu'affiché après le dépôt du fichier."""

    total: int
    crees: int
    mis_a_jour: int
    #: Lignes sans code d'immobilisation : impossible de les reconnaître d'un import à l'autre.
    ignores: int
    #: Matricules que le fichier nomme mais qu'aucun compte ne porte : rattachements à faire.
    detenteurs_non_rapproches: int
    #: Lignes portant un état constaté (bon / rebut / casse) — exploité par les campagnes.
    avec_etat_constate: int
    #: Constats effectivement rattachés à la campagne ouverte (0 si aucune campagne en cours).
    constats_enregistres: int = 0


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
    # Voit au-delà de son périmètre de direction (cf. activites_communs._visible).
    transverse: bool = False


class CreationProfil(BaseModel):
    # Le code technique est dérivé du libellé : l'administrateur nomme, il ne code pas.
    libelle: str = Field(min_length=1, max_length=80)
    transverse: bool = False


class MajProfil(BaseModel):
    libelle: str = Field(min_length=1, max_length=80)
    # Omis = inchangé. Retirer le transverse à ADMIN est refusé (anti-verrouillage).
    transverse: bool | None = None


class DirectionItem(BaseModel):
    code: str
    libelle: str


class UtilisateurResume(BaseModel):
    id: str
    email: str
    nom: str
    prenom: str
    #: Matricule bancaire : c'est par lui que l'inventaire désigne le détenteur d'un équipement.
    matricule: str | None = None
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
    matricule: str | None = Field(default=None, max_length=40)
    profil_code: str
    direction_code: str | None = None
    # La DSI n'a que N1 et N2 : le niveau 3 désigne un transfert vers DBS, qui n'a pas de compte
    # ici (ADR-0003 §3). Miroir de la contrainte CHECK sur core.utilisateur.
    niveau_support: int | None = Field(default=None, ge=1, le=2)
    expire_le: datetime | None = None


class MajUtilisateur(BaseModel):
    nom: str
    prenom: str
    matricule: str | None = Field(default=None, max_length=40)
    profil_code: str
    direction_code: str | None = None
    # La DSI n'a que N1 et N2 : le niveau 3 désigne un transfert vers DBS, qui n'a pas de compte
    # ici (ADR-0003 §3). Miroir de la contrainte CHECK sur core.utilisateur.
    niveau_support: int | None = Field(default=None, ge=1, le=2)
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
    #: Fin réelle d'un projet clôturé : porte le verdict d'échéance (à temps / en retard).
    cloture_le: datetime | None = None
    transitions_possibles: list[str]
    permissions: PermissionsActivite = PermissionsActivite()


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
    #: Date de fin d'une tâche terminée (dernière modification) : porte le verdict d'échéance.
    terminee_le: datetime | None = None
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
    en_attente_validation: bool = False
    historique: list[EntreeHistorique]
    periodicite: str | None = None
    prochaine_revue: date | None = None
    derniere_revue: date | None = None
    permissions: PermissionsActivite = PermissionsActivite()


class PageRisques(BaseModel):
    elements: list[RisqueResume]
    total: int
    page: int
    taille: int


# --- Tableau de bord ---


class CartesBord(BaseModel):
    # État général transverse (tous modules), pas centré incidents.
    activites_ouvertes: int
    critiques: int
    charge_dsi: int
    en_retard: int
    resolues: int
    respect_sla: int
    respect_sla_base: int  # nombre de tickets réellement mesurés (pour neutraliser les petits n)


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


class ATraiterItem(BaseModel):
    """Une activité à traiter en premier : l'échéance la plus proche, ou la plus dépassée."""

    module: str
    id: str
    reference: str
    titre: str
    priorite: int | None
    statut: str
    sla_resolution_le: datetime


class TableauBord(BaseModel):
    cartes: CartesBord
    sla: SlaBuckets
    repartition: list[RepartitionItem]
    serie: list[SerieSlaItem]
    a_traiter: list[ATraiterItem]
    # Créations hebdomadaires (8 semaines) : la respiration du flux, en miniature sur les cartes.
    creations_hebdo: dict[str, list[int]]
    dbs_ouverts: int
    dbs_age_jours: float | None
    rouverts_30j: int
    resolus_30j: int
    # Signaux additionnels : stock qui traîne (> 30 j) et tickets pas encore pris en charge.
    ouverts_30j: int
    non_pris_en_charge: int
    ouverts_total: int


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
    # Respect SLA (%) : part des tickets résolus dans les temps parmi ceux à durée mesurée.
    respect_sla: int | None = None
    # Activités que l'agent suit comme contributeur : elles comptent dans sa file, pas dans
    # son volume traité — suivre n'est pas résoudre.
    suivis: int = 0


class GestionnaireDetail(GestionnaireEval):
    activite: list[PointActivite]


class DureeStatut(BaseModel):
    """Temps moyen passé dans un statut (séjours terminés, reconstitués du journal)."""

    module: str
    statut: str
    jours: float
    passages: int


class ReouvertureItem(BaseModel):
    """Un ticket rouvert est une résolution qui n'a pas tenu."""

    libelle: str
    rouverts: int
    resolus: int
    taux: int


class DbsSynthese(BaseModel):
    """Part des tickets importés restée à la DSI vs partie chez DBS (ADR-0005)."""

    dsi: int
    dbs: int
    dbs_ouverts: int
    dbs_age_jours: float | None


class ParetoItem(BaseModel):
    libelle: str
    valeur: int
    cumul_pct: int


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
    durees_statuts: list[DureeStatut]
    reouvertures: list[ReouvertureItem]
    vieillissement: list[AnalyseItem]
    distribution_delais: list[AnalyseItem]
    dbs: DbsSynthese
    pareto_categories: list[ParetoItem]
    pec_par_priorite: list[SlaPrioriteItem]


# --- Répartition mensuelle (tableaux croisés par mois) -------------------------------------------


class MoisEntete(BaseModel):
    """Une colonne de mois : clé technique (tri) + libellé court affiché."""

    cle: str  # ex. "2023-03"
    libelle: str  # ex. "mars 23"


class CelluleSla(BaseModel):
    """Cellule d'un mois pour la volumétrie par priorité : volume + respect SLA."""

    mois: str
    total: int
    population_sla: int  # tickets à durée mesurée (base du taux)
    sla_taux: float | None  # None = pas de population mesurable ce mois-là


class LignePriorite(BaseModel):
    priorite: int
    cible_minutes: int | None
    cellules: list[CelluleSla]


class CelluleEntite(BaseModel):
    mois: str
    total: int
    fermes: int
    ouverts: int
    rejetes: int
    incidents: int
    demandes: int


class LigneEntite(BaseModel):
    cle: str  # DSI | DBS
    libelle: str
    total: int
    fermes: int
    ouverts: int
    incidents: int
    demandes: int
    cellules: list[CelluleEntite]


class CelluleNiveau(BaseModel):
    mois: str
    total: int
    fermes: int
    ouverts: int
    incidents: int
    demandes: int


class LigneNiveau(BaseModel):
    cle: str  # nom du gestionnaire
    libelle: str
    niveau: str  # N1 | N2 | DBS | Autre — pour regrouper les gestionnaires
    total: int
    fermes: int
    ouverts: int
    incidents: int
    demandes: int
    cellules: list[CelluleNiveau]


class AnalysesMensuelles(BaseModel):
    # Granularité de l'axe de temps : heure | jour | semaine | mois | annee (selon la période).
    granularite: str
    # Fenêtre réellement retenue (bornes des buckets). Affichée telle quelle : comparer ces
    # chiffres à ceux d'une liste n'a de sens qu'en sachant sur quoi ils portent.
    debut: datetime
    fin: datetime
    mois: list[MoisEntete]  # colonnes de l'axe de temps (nom historique)
    total_priorites: list[CelluleSla]  # ligne d'en-tête (toutes priorités confondues)
    priorites: list[LignePriorite]
    entites: list[LigneEntite]
    niveaux: list[LigneNiveau]  # répartition par niveau de support (N1/N2/DBS), incidents+demandes
