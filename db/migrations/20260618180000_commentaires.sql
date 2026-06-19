-- Fil de discussion interne DSI sur une activité (le demandeur n'a pas accès à la plateforme).
CREATE TABLE core.commentaire (
    id           bigserial PRIMARY KEY,
    activite_id  uuid NOT NULL REFERENCES core.activite(id) ON DELETE CASCADE,
    auteur_id    uuid REFERENCES core.utilisateur(id),
    auteur_email text NOT NULL,                 -- figé à l'écriture (survit à la suppression du compte)
    texte        text NOT NULL,
    cree_le      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_commentaire_activite ON core.commentaire(activite_id, cree_le);

COMMENT ON TABLE core.commentaire IS
    'Echanges internes DSI rattaches a une activite. Append-only par usage (tracabilite).';
