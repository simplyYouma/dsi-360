-- Images jointes à un message de discussion (captures d'écran).
-- Uniquement des images : le type est vérifié côté serveur (extension + décodage réel).
-- Contenu en bytea : sauvegardé avec la base, transactionnel, sans infrastructure supplémentaire.

CREATE TABLE core.commentaire_image (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    commentaire_id bigint NOT NULL REFERENCES core.commentaire(id) ON DELETE CASCADE,
    nom            text NOT NULL,
    type_mime      text NOT NULL,
    taille         integer NOT NULL,
    largeur        integer,
    hauteur        integer,
    contenu        bytea NOT NULL,
    depose_le      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_commentaire_image_commentaire ON core.commentaire_image (commentaire_id);
