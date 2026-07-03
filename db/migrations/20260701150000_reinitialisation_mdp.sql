-- Jetons de réinitialisation de mot de passe (mot de passe oublié). On stocke uniquement l'empreinte
-- du jeton (jamais le jeton en clair). Usage unique, avec expiration ; supprimé en cascade.
CREATE TABLE core.reinitialisation_mdp (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    utilisateur_id uuid NOT NULL REFERENCES core.utilisateur(id) ON DELETE CASCADE,
    jeton_hash     text NOT NULL,
    expire_le      timestamptz NOT NULL,
    utilise        boolean NOT NULL DEFAULT false,
    cree_le        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_reset_jeton ON core.reinitialisation_mdp (jeton_hash);
