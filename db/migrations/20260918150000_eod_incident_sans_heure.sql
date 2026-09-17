-- EOD — un incident d'agence ne porte plus d'heure : c'est la ligne RELANCE qui la porte.
--
-- L'observation « incident » exigeait une heure de relance, posée d'office à l'instant de la
-- saisie quand l'opérateur n'en donnait pas. Sur la ligne de l'étape, « 15H13 · Agence 04 ZI »
-- se lisait alors comme un démarrage automatique de la relance — ce qu'il n'était pas, et ce
-- qu'on venait justement d'interdire. Depuis que la relance est une étape à part entière, que
-- l'opérateur démarre lui-même (« Maintenant » ou l'heure qu'il donne), l'observation n'a plus
-- d'heure à porter : elle dit l'agence et ce qui a été fait, la ligne RELANCE dit quand.
--
-- La colonne reste (les lignes qui la portent ne perdent rien) ; seule l'obligation tombe.

ALTER TABLE core.eod_observation DROP CONSTRAINT IF EXISTS ck_eod_observation_incident;
ALTER TABLE core.eod_observation
    ADD CONSTRAINT ck_eod_observation_incident CHECK (
        nature <> 'incident' OR (agence IS NOT NULL AND btrim(agence) <> '')
    );
