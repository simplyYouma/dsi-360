-- Plusieurs contributeurs par activité, un seul valideur.
--
-- La règle posée en juillet (20260711120000_un_acteur_par_role) était : « Un seul contributeur et
-- un seul valideur par activité. Nommer quelqu'un d'autre est une réaffectation, pas un ajout. »
-- Elle ne tient plus pour la DSI : un sujet de gouvernance, un projet, un changement mobilisent
-- couramment plusieurs personnes en appui, et l'écran obligeait à en effacer une pour en nommer une
-- autre. La décision est prise en connaissance de cause, et elle vaut pour TOUS les modules : une
-- règle qui varierait de module en module ne serait plus garantie par la base, seulement espérée
-- par le code.
--
-- Le VALIDEUR, lui, reste unique. Ce n'est pas une symétrie oubliée : la décision de validation est
-- un acte engageant, le circuit CAB/ECAB s'appuie sur un décideur identifié, et la liste se fige
-- dès la première décision rendue. Ouvrir ce rôle demanderait de revoir cette mécanique — ce n'est
-- pas l'objet ici.
--
-- Aucune donnée n'est perdue : les contributeurs déjà désignés le restent. La clé primaire
-- (activite_id, utilisateur_id, role) continue d'empêcher de nommer deux fois la même personne au
-- même titre.

DROP INDEX IF EXISTS core.ux_activite_acteur_role;

-- Dédoublonnage défensif avant de reposer l'unicité sur les seuls valideurs : l'index précédent la
-- garantissait, mais on ne repose pas une contrainte sur une hypothèse.
DELETE FROM core.activite_acteur a
USING core.activite_acteur b
WHERE a.activite_id = b.activite_id
  AND a.role = 'VALIDEUR'
  AND b.role = 'VALIDEUR'
  AND a.ctid < b.ctid;

CREATE UNIQUE INDEX IF NOT EXISTS ux_activite_valideur_unique
    ON core.activite_acteur (activite_id)
 WHERE role = 'VALIDEUR';

COMMENT ON INDEX core.ux_activite_valideur_unique IS
    'Un seul valideur par activite. Les contributeurs, eux, sont plusieurs depuis le 07/09/2026.';
