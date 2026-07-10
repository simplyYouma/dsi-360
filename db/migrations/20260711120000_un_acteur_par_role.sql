-- Un seul contributeur et un seul valideur par activité : c'est la règle métier.
-- Nommer quelqu'un d'autre est une réaffectation, pas un ajout.
--
-- On dédoublonne d'abord (le plus récent reste), puis l'unicité est portée par la base :
-- l'écran peut se tromper, pas la contrainte.

DELETE FROM core.activite_acteur a
USING core.activite_acteur b
WHERE a.activite_id = b.activite_id
  AND a.role = b.role
  AND a.ctid < b.ctid;

CREATE UNIQUE INDEX IF NOT EXISTS ux_activite_acteur_role
    ON core.activite_acteur (activite_id, role);
