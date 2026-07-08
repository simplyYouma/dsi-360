-- Édition des commentaires de discussion : trace de la dernière modification (affichée « modifié »).
-- Seul l'auteur peut éditer/supprimer son commentaire (contrôle côté API).
ALTER TABLE core.commentaire ADD COLUMN maj_le timestamptz;
