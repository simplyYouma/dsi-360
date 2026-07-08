-- Accusés de lecture des commentaires (façon réseaux sociaux) : qui a vu quel message, et quand.
-- Sert à distinguer les messages « vus / non vus », à compter les vues et à lister les lecteurs.
CREATE TABLE core.commentaire_vue (
    commentaire_id bigint NOT NULL REFERENCES core.commentaire(id) ON DELETE CASCADE,
    utilisateur_id uuid NOT NULL REFERENCES core.utilisateur(id) ON DELETE CASCADE,
    vu_le          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (commentaire_id, utilisateur_id)
);
CREATE INDEX idx_commentaire_vue_utilisateur ON core.commentaire_vue (utilisateur_id);
