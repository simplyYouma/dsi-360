-- Tâches d'une activité (projets, puis changements). Chaque tâche est assignable à une personne,
-- porte un statut simple et une échéance. L'avancement du projet et son passage « En cours » se
-- déduisent des tâches (cf. application/taches.py). Suppression en cascade avec l'activité parente.
CREATE TABLE core.tache (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    activite_id uuid NOT NULL REFERENCES core.activite(id) ON DELETE CASCADE,
    titre       text NOT NULL,
    description text,
    statut      text NOT NULL DEFAULT 'À faire'
                CHECK (statut IN ('À faire', 'En cours', 'Terminée')),
    assigne_id  uuid REFERENCES core.utilisateur(id),
    echeance    date,
    ordre       integer NOT NULL DEFAULT 0,
    cree_le     timestamptz NOT NULL DEFAULT now(),
    maj_le      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_tache_activite ON core.tache (activite_id);

-- Documents rattachables à une tâche précise (en plus du rattachement à l'activité).
ALTER TABLE core.document ADD COLUMN tache_id uuid REFERENCES core.tache(id) ON DELETE CASCADE;
CREATE INDEX idx_document_tache ON core.document (tache_id);
