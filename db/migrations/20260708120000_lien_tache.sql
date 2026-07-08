-- Liens utiles au niveau des tâches (en plus des pièces jointes) : un lien peut se rattacher à
-- une tâche précise. Les liens de l'activité restent ceux sans tâche. Cascade avec la tâche.
ALTER TABLE core.lien ADD COLUMN tache_id uuid REFERENCES core.tache(id) ON DELETE CASCADE;
CREATE INDEX idx_lien_tache ON core.lien (tache_id);
