-- Le niveau de support (N1/N2/N3) est désormais une propriété du GESTIONNAIRE (utilisateur), fixée
-- à la création/édition du compte — et non plus des groupes de support par direction. L'escalade
-- réaffecte le ticket à un gestionnaire du niveau cible (dans sa direction si possible).
ALTER TABLE core.utilisateur
    ADD COLUMN niveau_support smallint CHECK (niveau_support IS NULL OR niveau_support BETWEEN 1 AND 3);

-- Abandon des groupes de support (remplacés par le niveau porté par l'utilisateur).
DROP TABLE IF EXISTS core.groupe_support_membre;
DROP TABLE IF EXISTS core.groupe_support;
