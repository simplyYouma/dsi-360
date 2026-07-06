-- Jalons (dates clés) d'un projet — cf. cahier des charges, module Projets.
-- Distincts des tâches : un jalon marque une échéance importante (atteinte ou non), sans piloter
-- l'avancement. Suppression en cascade avec le projet.
CREATE TABLE core.jalon (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    activite_id uuid NOT NULL REFERENCES core.activite(id) ON DELETE CASCADE,
    titre       text NOT NULL,
    echeance    date,
    atteint     boolean NOT NULL DEFAULT false,
    ordre       integer NOT NULL DEFAULT 0,
    cree_le     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_jalon_activite ON core.jalon (activite_id);
