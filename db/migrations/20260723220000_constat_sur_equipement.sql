-- Le constat vit sur l'équipement, plus dans une campagne.
--
-- Pourquoi : l'état d'un matériel (bon, rebut, cassé) et sa sortie du parc suffisaient déjà à
-- dire ce qu'il en est. La campagne n'apportait qu'une chose — savoir ce qu'il reste à
-- contrôler — et cette information tient dans une date : « non contrôlé depuis douze mois ».
-- Un conteneur à ouvrir, remplir et clore pour un besoin que porte un horodatage, c'était de
-- la machinerie ; on la retire.
--
-- Ce qu'on ne perd pas : l'historique complet des constats reste au journal d'audit (qui a dit
-- quoi, quand, pourquoi), et la comparaison d'une année sur l'autre s'y lit.

ALTER TABLE core.equipement
    ADD COLUMN IF NOT EXISTS etat_constate  text
        CHECK (etat_constate IN ('BON', 'REBUT', 'CASSE')),
    ADD COLUMN IF NOT EXISTS constate_le    timestamptz,
    ADD COLUMN IF NOT EXISTS constate_par   uuid REFERENCES core.utilisateur(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS constat_motif  text;

COMMENT ON COLUMN core.equipement.etat_constate IS
    'Dernier état constaté sur le terrain. NULL = jamais contrôlé : ce n''est pas un verdict, '
    'c''est un trou — personne n''y est allé.';
COMMENT ON COLUMN core.equipement.constate_le IS
    'Date du dernier contrôle. C''est elle qui dit ce qu''il reste à faire : « non contrôlé '
    'depuis douze mois » remplace l''avancement d''une campagne.';

-- Reprise : le constat le plus récent de chaque équipement remonte sur sa fiche. NON_RETROUVE
-- ne remonte pas — il ne disait pas un état observé, mais l'absence de contrôle avant clôture.
UPDATE core.equipement e
SET etat_constate = k.etat,
    constate_le   = k.constate_le,
    constate_par  = k.constate_par,
    constat_motif = k.justification
FROM (
    SELECT DISTINCT ON (equipement_id) equipement_id, etat, constate_le, constate_par, justification
    FROM core.constat_inventaire
    WHERE etat <> 'NON_RETROUVE'
    ORDER BY equipement_id, constate_le DESC
) AS k
WHERE k.equipement_id = e.id;

-- Les matériels qu'on n'a jamais contrôlés se retrouvent en tête de la liste de travail.
CREATE INDEX IF NOT EXISTS idx_equipement_constate_le ON core.equipement (constate_le);

DROP TABLE IF EXISTS core.constat_inventaire;
DROP TABLE IF EXISTS core.campagne_inventaire;
