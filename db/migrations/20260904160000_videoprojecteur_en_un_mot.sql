-- Retour à « Vidéoprojecteur », en un seul mot — l'orthographe usuelle.
--
-- La migration précédente (20260904140000_types_equipement_libelles) l'avait séparé en
-- « Vidéo projecteur ». C'était une mauvaise lecture de ma part ; la DSI a tranché pour le mot
-- collé. On ne corrige pas la migration d'avant : elle est déjà appliquée en développement, la
-- réécrire y laisserait une base qui ne dit pas la même chose que le fichier. Les migrations sont
-- en ajout seul, et celle-ci fait foi.
--
-- « Ordinateur desktop » n'est pas touché : ce renommage-là est bien celui demandé.
--
-- Mêmes précautions : renommage insensible à la casse et aux espaces, et seulement si le nom
-- d'arrivée est libre — l'unicité du libellé refuserait un doublon et bloquerait la migration.

UPDATE core.type_equipement
   SET libelle = 'Vidéoprojecteur'
 WHERE upper(btrim(libelle)) = upper(btrim('Vidéo projecteur'))
   AND NOT EXISTS (
       SELECT 1 FROM core.type_equipement autre
        WHERE upper(btrim(autre.libelle)) = upper(btrim('Vidéoprojecteur'))
   );
