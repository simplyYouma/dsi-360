"""Schémas Pydantic d'entrée/sortie de l'API (couche interface)."""

from datetime import datetime

from pydantic import BaseModel, Field


class Connexion(BaseModel):
    email: str
    mot_de_passe: str = Field(min_length=1)


class Rafraichissement(BaseModel):
    refresh: str


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


class PageActivites(BaseModel):
    elements: list[ActiviteResume]
    total: int
    page: int
    taille: int


class TransitionDemande(BaseModel):
    vers: str = Field(min_length=1)


class CreationReponse(BaseModel):
    id: str
