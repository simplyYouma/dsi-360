-- Normalise les libellés de catégories existants (réécriture lisible : initiale de chaque mot
-- en majuscule). La reconnaissance reste insensible à la casse via le code (en majuscules).
UPDATE core.categorie SET libelle = initcap(libelle);
