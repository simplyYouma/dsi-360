-- Chaque constat d'inventaire se justifie.
--
-- Un clic sur « Rebut » engage : il peut mener à la sortie du parc d'un bien qui vaut encore
-- quelque chose au bilan. Sans un mot pour dire ce qui a été vu — « écran fêlé », « retrouvé
-- en réserve », « ne démarre plus » — le constat n'est qu'une opinion sans preuve, et la
-- campagne se relit un an plus tard sans que personne ne sache ce qui s'est passé.

ALTER TABLE core.constat_inventaire ADD COLUMN IF NOT EXISTS justification text;

COMMENT ON COLUMN core.constat_inventaire.justification IS
    'Ce qui a été observé sur le terrain, en une phrase. Exigé à la saisie ; les constats '
    'venus de l''import portent la mention du fichier d''origine.';

-- Les constats déjà posés n'en ont pas : on le dit plutôt que d'inventer une observation.
UPDATE core.constat_inventaire
SET justification = 'Constat antérieur à la saisie du motif'
WHERE justification IS NULL;
