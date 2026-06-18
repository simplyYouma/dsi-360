-- Ticketing : référentiel des demandeurs (agents de la banque, toutes directions) et
-- traçabilité de la source d'ingestion (rechargement quotidien idempotent par n° de ticket).

CREATE TABLE core.demandeur (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nom_complet  text NOT NULL,
    direction_id uuid REFERENCES core.direction(id),  -- rattachement (renseigné/édité ensuite)
    email        text,
    actif        boolean NOT NULL DEFAULT true,
    cree_le      timestamptz NOT NULL DEFAULT now(),
    maj_le       timestamptz NOT NULL DEFAULT now()
);
-- Reconnaissance d'un demandeur d'un import à l'autre : nom normalisé unique.
CREATE UNIQUE INDEX uq_demandeur_nom ON core.demandeur (lower(nom_complet));

COMMENT ON TABLE core.demandeur IS
    'Agents de la banque qui remontent incidents/demandes. Pas des comptes applicatifs.';

-- Activité : qui a remonté (demandeur externe) + provenance (saisie vs import) + clé externe.
ALTER TABLE core.activite
    ADD COLUMN demandeur_externe_id uuid REFERENCES core.demandeur(id),
    ADD COLUMN source   text NOT NULL DEFAULT 'SAISIE',  -- SAISIE | IMPORT_SD
    ADD COLUMN source_id text;                           -- n° de ticket d'origine

-- Idempotence : un même ticket (module + n°) ne crée jamais de doublon.
CREATE UNIQUE INDEX uq_activite_source
    ON core.activite (module, source_id) WHERE source_id IS NOT NULL;
