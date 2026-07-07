-- Discussion au niveau des tâches : un commentaire peut se rattacher à une tâche précise (en plus
-- de l'activité). Le fil de l'activité n'affiche que les commentaires sans tâche ; chaque tâche a
-- son propre fil. Suppression en cascade avec la tâche.
ALTER TABLE core.commentaire ADD COLUMN tache_id uuid REFERENCES core.tache(id) ON DELETE CASCADE;
CREATE INDEX idx_commentaire_tache ON core.commentaire (tache_id);
