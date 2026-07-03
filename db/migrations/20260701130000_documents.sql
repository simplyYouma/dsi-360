-- Documents (pièces jointes) rattachés à une activité. Contenu stocké en base (bytea) : sauvegardé
-- avec la DB, transactionnel, sans infra supplémentaire. Exposé d'abord sur les projets.
-- Suppression en cascade si l'activité est supprimée.
CREATE TABLE core.document (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    activite_id uuid NOT NULL REFERENCES core.activite(id) ON DELETE CASCADE,
    nom         text NOT NULL,
    type_mime   text NOT NULL,
    taille      integer NOT NULL,
    contenu     bytea NOT NULL,
    depose_par  text,                                   -- e-mail de l'acteur, figé à l'écriture
    depose_le   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_document_activite ON core.document (activite_id);
