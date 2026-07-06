-- Groupes de support ITIL (N1/N2/N3). L'escalade fonctionnelle d'un incident/demande ne se contente
-- plus d'incrémenter un compteur : elle réaffecte le ticket au membre le moins chargé du groupe du
-- niveau cible. Groupes paramétrables (membres gérés depuis l'administration), un seul par niveau.
CREATE TABLE core.groupe_support (
    id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    niveau smallint NOT NULL UNIQUE CHECK (niveau BETWEEN 1 AND 3),
    nom    text NOT NULL
);

CREATE TABLE core.groupe_support_membre (
    groupe_id      uuid NOT NULL REFERENCES core.groupe_support(id) ON DELETE CASCADE,
    utilisateur_id uuid NOT NULL REFERENCES core.utilisateur(id) ON DELETE CASCADE,
    PRIMARY KEY (groupe_id, utilisateur_id)
);

-- Niveaux par défaut (les membres se rattachent ensuite via l'administration).
INSERT INTO core.groupe_support (niveau, nom) VALUES
    (1, 'Support niveau 1 — Service Desk'),
    (2, 'Support niveau 2 — Experts'),
    (3, 'Support niveau 3 — Référents et éditeurs');
