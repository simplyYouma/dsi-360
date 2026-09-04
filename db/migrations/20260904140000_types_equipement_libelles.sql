-- Libellés de deux types d'équipement, corrigés à la demande de la DSI.
--
--   « Ordinateur fixe »  ->  « Ordinateur desktop »
--   « Vidéoprojecteur »  ->  « Vidéo projecteur »
--
-- Un renommage, pas une création : les équipements pointent le type par son identifiant, ils
-- suivent donc sans être touchés. Le seed d'origine (20260728120000) reste tel quel — les
-- migrations sont en ajout seul ; c'est celle-ci qui fait foi pour l'état courant.
--
-- Idempotent, et prudent : l'unicité du libellé est insensible à la casse et aux espaces
-- (uq_type_equipement_libelle). Si le nom d'arrivée existe déjà — quelqu'un l'a saisi à l'écran
-- entre-temps — renommer lèverait une violation de contrainte et bloquerait toute la migration.
-- On ne renomme donc que si la place est libre.

DO $$
DECLARE
    renommages CONSTANT text[][] := ARRAY[
        ARRAY['Ordinateur fixe',  'Ordinateur desktop'],
        ARRAY['Vidéoprojecteur',  'Vidéo projecteur']
    ];
    couple text[];
BEGIN
    FOREACH couple SLICE 1 IN ARRAY renommages LOOP
        UPDATE core.type_equipement
           SET libelle = couple[2]
         WHERE upper(btrim(libelle)) = upper(btrim(couple[1]))
           AND NOT EXISTS (
               SELECT 1 FROM core.type_equipement autre
                WHERE upper(btrim(autre.libelle)) = upper(btrim(couple[2]))
           );
    END LOOP;
END $$;
