-- EOD — l'anomalie est une ligne du journal, pas le verdict de l'étape.
--
-- Le rapport réel : « Post EOFI_1 | 19H53 | 20H08 | Completed For All Branch Expected Branch 018
-- Error code:AE-VALS-053 ». L'étape a FINI — et porte une anomalie. Faire de « Anomalie » le
-- verdict de l'étape, comme nous l'avions modélisé, forçait à choisir entre « elle a fini » et
-- « quelque chose a coincé », alors que les deux sont vrais à la fois, et souvent plusieurs fois
-- sur la même étape.
--
-- L'anomalie devient donc une NATURE d'observation, à côté de la note et de l'incident d'agence :
-- on en ajoute autant qu'il en survient, chacune signée et horodatée, l'étape gardant son verdict
-- de pointage. Le statut d'étape « Anomalie » reste accepté par la base pour les lignes qui le
-- portent déjà ; l'écran ne le pose plus.

ALTER TABLE core.eod_observation DROP CONSTRAINT IF EXISTS eod_observation_nature_check;
ALTER TABLE core.eod_observation
    ADD CONSTRAINT eod_observation_nature_check CHECK (nature IN ('note', 'anomalie', 'incident'));
