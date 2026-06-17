"""Schémas Pydantic d'entrée/sortie de l'API (couche interface)."""

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
