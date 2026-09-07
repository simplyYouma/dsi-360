-- Libellés des profils, arrêtés par la DSI, et leur département.
--
--   IT Support Applicatif             -> « Applicatif »      · Production et Applicatif
--   IT Support Applicatif et HelpDesk -> « Production »      · Production et Applicatif
--   Réseau télécom                    -> inchangé            · Réseau et Infrastructure
--   Système et Réseau télécom         -> « Infrastructure »  · Réseau et Infrastructure
--   Administrateur                    -> inchangé            · transverse, aucun département
--
-- Un RENOMMAGE, pas une refonte : le code technique ne bouge pas. Il est référencé par les comptes
-- et par la matrice d'accès (`core.acces_role`) — le changer reviendrait à changer les droits de
-- tout le monde, sur un système en production. Aucun compte n'est réaffecté, aucun accès n'est
-- touché : seul l'intitulé affiché change.
--
-- Le rattachement aux départements avait déjà été posé par 20260907090000 selon la nature des
-- profils ; on le rejoue ici pour que cette migration soit lisible seule et vraie quoi qu'il arrive
-- (quelqu'un a pu détacher un profil à l'écran entre-temps).

UPDATE core.profil SET libelle = 'Applicatif'     WHERE code = 'SUPPORT_APP';
UPDATE core.profil SET libelle = 'Production'     WHERE code = 'SUPPORT_APP_HELPDESK';
UPDATE core.profil SET libelle = 'Infrastructure' WHERE code = 'SYSTEME_RESEAU_TELECOM';

UPDATE core.profil p
   SET departement_id = d.id
  FROM core.departement d
 WHERE d.code = 'PRODUCTION_APPLICATIF'
   AND p.code IN ('SUPPORT_APP', 'SUPPORT_APP_HELPDESK');

UPDATE core.profil p
   SET departement_id = d.id
  FROM core.departement d
 WHERE d.code = 'RESEAU_INFRASTRUCTURE'
   AND p.code IN ('RESEAU_TELECOM', 'SYSTEME_RESEAU_TELECOM');
