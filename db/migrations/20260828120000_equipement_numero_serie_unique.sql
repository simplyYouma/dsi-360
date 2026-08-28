-- Le numéro de série identifie physiquement le matériel : il est unique, et il ne change pas.
--
-- Deux fiches portant le même numéro, c'est un équipement compté deux fois — au parc comme au
-- bilan. Le contrôle vivait jusqu'ici nulle part : ni à l'écran, ni en base.
--
-- Avant de poser l'index, on vérifie qu'aucun doublon ne subsiste. S'il en reste, la migration
-- s'arrête en les nommant plutôt que d'échouer sur une erreur d'index illisible : c'est une
-- décision humaine (lequel des deux garde le numéro ?), pas quelque chose que l'on tranche ici.
DO $$
DECLARE
    doublons text;
BEGIN
    SELECT string_agg(ns || ' (' || n || ' fiches)', ', ')
    INTO doublons
    FROM (
        SELECT upper(btrim(numero_serie)) AS ns, count(*) AS n
        FROM core.equipement
        WHERE numero_serie IS NOT NULL AND btrim(numero_serie) <> ''
        GROUP BY 1 HAVING count(*) > 1
    ) d;

    IF doublons IS NOT NULL THEN
        RAISE EXCEPTION
            'Numéros de série en double dans l''inventaire : %. '
            'Corrigez-les depuis l''écran Inventaire (un numéro par matériel), puis relancez la '
            'mise à jour.', doublons;
    END IF;
END $$;

-- Unique seulement quand il est renseigné : tout le parc n'a pas encore son numéro relevé, et une
-- case vide n'est pas une identité. Comparaison insensible à la casse et aux espaces de bordure,
-- comme pour le code d'immobilisation.
CREATE UNIQUE INDEX IF NOT EXISTS uq_equipement_numero_serie
    ON core.equipement (upper(btrim(numero_serie)))
    WHERE numero_serie IS NOT NULL AND btrim(numero_serie) <> '';

COMMENT ON COLUMN core.equipement.numero_serie IS
    'Numéro de série constructeur. Unique dans le parc, et figé une fois renseigné : il est gravé '
    'sur le matériel, il ne se corrige pas — on corrige la fiche qui s''est trompée de matériel.';
