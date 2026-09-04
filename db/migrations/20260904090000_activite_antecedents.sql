-- Identités précédentes d'un dossier — quand un ticket change de module entre deux imports.
--
-- SysAid numérote incidents et demandes dans la MÊME série : le numéro d'un ticket ne change pas
-- quand on le requalifie, seul son type change. Chez nous, l'unicité porte sur (module, source_id) :
-- le même ticket requalifié entrait donc une seconde fois, sous un autre module, et les deux
-- fiches coexistaient — l'ancienne figée à jamais, la nouvelle sans son histoire.
--
-- L'import reconnaît désormais la requalification au `source_id` et DÉPLACE la fiche existante au
-- lieu d'en créer une seconde. La fiche garde son identifiant, donc ses commentaires, ses pièces
-- jointes, ses contributeurs et ses notifications. Mais sa RÉFÉRENCE change (INC-1234 -> DEM-1234),
-- et le journal d'audit est append-only : les écritures d'avant portent l'ancienne référence et
-- l'ancien module. Sans mémoire du passage, l'historique de la fiche repartirait de zéro.
--
-- D'où cette colonne : la liste des identités successives, la plus ancienne d'abord.
--   [{"module": "incident", "reference": "INC-1234", "le": "2026-09-04T09:00:00+00:00"}]
--
-- Elle vit à part de `donnees`, qui ne contient que ce que dit le rapport : ce sont deux natures
-- différentes, et l'upsert d'import écrase `donnees` à chaque passage.

ALTER TABLE core.activite
    ADD COLUMN IF NOT EXISTS antecedents jsonb NOT NULL DEFAULT '[]'::jsonb;

COMMENT ON COLUMN core.activite.antecedents IS
    'Identités précédentes du dossier (module + référence) après requalification à l''import. '
    'Sert à retrouver, dans le journal append-only, les écritures faites sous l''ancienne '
    'référence.';

-- Retrouver vite les tickets requalifiés : la reconnaissance se fait sur le numéro de ticket,
-- indépendamment du module.
CREATE INDEX IF NOT EXISTS idx_activite_source_id
    ON core.activite (source_id)
    WHERE source_id IS NOT NULL;
