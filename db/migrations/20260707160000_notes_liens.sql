-- Journal de bord d'un projet : notes horodatées (auteur figé). Une suspension ou une clôture
-- DOIT être justifiée : la justification est enregistrée comme note (contexte = état cible).
CREATE TABLE core.note (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    activite_id  uuid NOT NULL REFERENCES core.activite(id) ON DELETE CASCADE,
    texte        text NOT NULL,
    contexte     text,               -- NULL = note libre ; sinon « Suspendu », « Clôturé »…
    auteur_email text,
    cree_le      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_note_activite ON core.note (activite_id);

-- Liens utiles d'un projet (espace documentaire, wiki, dossier réseau…) : remplacent le dépôt de
-- documents au niveau du projet — les tâches, elles, gardent leurs pièces jointes.
CREATE TABLE core.lien (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    activite_id uuid NOT NULL REFERENCES core.activite(id) ON DELETE CASCADE,
    libelle     text NOT NULL,
    url         text NOT NULL,
    cree_par    text,
    cree_le     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_lien_activite ON core.lien (activite_id);
