-- Nettoyage des catégories parasites issues d'imports : « None » et « N/A » ne sont pas de vraies
-- catégories (décision produit). Les activités concernées passent « sans catégorie » (categorie_id
-- NULL), puis les catégories vides sont supprimées. Aucune activité n'est perdue.
-- Portée : demande(None, N/A) et incident(N/A). Les variantes « Software » sont conservées.

UPDATE core.activite a
SET categorie_id = NULL
FROM core.categorie c
WHERE a.categorie_id = c.id
  AND (
    (c.module = 'demande' AND c.code IN ('NONE', 'N/A'))
    OR (c.module = 'incident' AND c.code = 'N/A')
  );

DELETE FROM core.categorie
WHERE (module = 'demande' AND code IN ('NONE', 'N/A'))
   OR (module = 'incident' AND code = 'N/A');
