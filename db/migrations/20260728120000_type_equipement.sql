-- Type d'inventaire : la nature d'un équipement (portable, serveur, imprimante…).
--
-- Troisième référentiel du parc, à côté de l'emplacement et du département : même forme, même
-- alimentation à la volée (saisie ou import). L'équipement le porte via `type_id`.

CREATE TABLE IF NOT EXISTS core.type_equipement (
    id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    libelle text NOT NULL,
    actif   boolean NOT NULL DEFAULT true,
    cree_le timestamptz NOT NULL DEFAULT now()
);
-- Unicité insensible à la casse et aux espaces : « Serveur » et « serveur  » sont le même type.
CREATE UNIQUE INDEX IF NOT EXISTS uq_type_equipement_libelle
    ON core.type_equipement (upper(btrim(libelle)));

ALTER TABLE core.equipement
    ADD COLUMN IF NOT EXISTS type_id uuid REFERENCES core.type_equipement(id);

-- Types de départ d'un parc informatique. L'administrateur ajoute, renomme et retire ensuite.
INSERT INTO core.type_equipement (libelle) VALUES
    ('Ordinateur portable'),
    ('Ordinateur fixe'),
    ('Serveur'),
    ('Écran'),
    ('Imprimante'),
    ('Onduleur'),
    ('Switch réseau'),
    ('Point d''accès Wi-Fi'),
    ('Téléphone IP'),
    ('Scanner')
ON CONFLICT DO NOTHING;
