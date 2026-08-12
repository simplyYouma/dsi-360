-- Une application a UN cycle de vie, pas deux.
--
-- Elle portait à la fois un `statut` (En service / En projet / Arrêtée) et un drapeau `actif`
-- (« retirée du parc »). Les deux disaient la même chose de deux façons : on pouvait déclarer une
-- application « Arrêtée » tout en la laissant « active », et l'écran affichait alors les deux
-- versions de la vérité côte à côte. Le bouton « Retirer du parc » n'avait, de fait, aucun sens
-- que le statut ne portait déjà.
--
-- On garde le statut — il est plus riche (il distingue « En projet » d'« Arrêtée ») — et l'on
-- supprime le drapeau. Rien n'est perdu : ce qui était retiré du parc devient « Arrêtée ».

UPDATE core.application SET statut = 'ARRETE' WHERE actif = false AND statut <> 'ARRETE';

ALTER TABLE core.application DROP COLUMN IF EXISTS actif;

COMMENT ON COLUMN core.application.statut IS
    'Cycle de vie : EN_SERVICE, EN_PROJET, ARRETE. Seule source de vérité sur l''état de '
    'l''application — le drapeau « actif » a été supprimé, il disait la même chose deux fois.';
