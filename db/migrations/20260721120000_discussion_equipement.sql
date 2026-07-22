-- La discussion interne s'ouvre aux équipements.
--
-- Le fil était rattaché à une activité (NOT NULL). Un équipement n'en est pas une : il lui faut
-- sa propre clé, sans dupliquer tout le mécanisme (mentions, images, accusés de lecture, export).
--
-- Un commentaire porte donc sur l'UN ou l'AUTRE, jamais les deux, jamais aucun : la contrainte
-- le garantit en base plutôt que de s'en remettre au code appelant.

ALTER TABLE core.commentaire
    ALTER COLUMN activite_id DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS equipement_id uuid
        REFERENCES core.equipement(id) ON DELETE CASCADE;

ALTER TABLE core.commentaire
    DROP CONSTRAINT IF EXISTS commentaire_un_seul_sujet;
ALTER TABLE core.commentaire
    ADD CONSTRAINT commentaire_un_seul_sujet CHECK (
        (activite_id IS NOT NULL AND equipement_id IS NULL)
        OR (activite_id IS NULL AND equipement_id IS NOT NULL)
    );

CREATE INDEX IF NOT EXISTS idx_commentaire_equipement
    ON core.commentaire (equipement_id, cree_le);

COMMENT ON TABLE core.commentaire IS
    'Échanges internes DSI rattachés à une activité OU à un équipement. '
    'Append-only par usage (traçabilité).';
