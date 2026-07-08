-- Révision des profils : tous les utilisateurs sont DSI. On retire Technicien, Métier, Chef de
-- service et Chef de projet ; on introduit « Gestionnaire ». Les comptes portant un profil retiré
-- sont bascules en Gestionnaire.
INSERT INTO core.profil (code, libelle, transverse) VALUES ('GESTIONNAIRE', 'Gestionnaire', false)
ON CONFLICT (code) DO UPDATE SET libelle = excluded.libelle, transverse = excluded.transverse;

UPDATE core.utilisateur
SET profil_id = (SELECT id FROM core.profil WHERE code = 'GESTIONNAIRE')
WHERE profil_id IN (
    SELECT id FROM core.profil WHERE code IN ('CHEF_SERVICE', 'CHEF_PROJET', 'TECHNICIEN', 'METIER')
);

DELETE FROM core.acces_role
WHERE profil_code IN ('CHEF_SERVICE', 'CHEF_PROJET', 'TECHNICIEN', 'METIER');
DELETE FROM core.profil
WHERE code IN ('CHEF_SERVICE', 'CHEF_PROJET', 'TECHNICIEN', 'METIER');

-- Accès par défaut du Gestionnaire : tout l'opérationnel (hors administration).
DELETE FROM core.acces_role WHERE profil_code = 'GESTIONNAIRE';
INSERT INTO core.acces_role (profil_code, acces) VALUES
    ('GESTIONNAIRE', 'tableau-de-bord'),
    ('GESTIONNAIRE', 'analyses'),
    ('GESTIONNAIRE', 'incidents'),
    ('GESTIONNAIRE', 'demandes'),
    ('GESTIONNAIRE', 'projets'),
    ('GESTIONNAIRE', 'changements'),
    ('GESTIONNAIRE', 'audit'),
    ('GESTIONNAIRE', 'risques'),
    ('GESTIONNAIRE', 'cybersecurite'),
    ('GESTIONNAIRE', 'gouvernance')
ON CONFLICT (profil_code, acces) DO NOTHING;
