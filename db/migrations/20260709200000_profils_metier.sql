-- Profils métier de la DSI, direction unique, niveaux N1/N2 (cf. docs/adr/0003).
--
-- Les profils DSI / GESTIONNAIRE / DG décrivaient une hiérarchie, pas le travail réel. On les
-- remplace par les métiers effectifs. Seul ADMIN est transverse.
--
-- Cette migration est **autonome** : elle crée la direction dont elle a besoin. Une migration ne
-- peut pas dépendre du seed, qui s'exécute après elle (cf. 20260707120000, corrigée pour la même
-- raison).

INSERT INTO core.direction (code, libelle)
VALUES ('DSI', 'Direction des Systèmes d''Information')
ON CONFLICT (code) DO NOTHING;

-- 1. Les cinq profils (ADR-0003 §1). Point de départ : l'administration peut ensuite en créer,
--    en renommer, en supprimer. ADMIN reste protégé côté API.
INSERT INTO core.profil (code, libelle, transverse) VALUES
    ('ADMIN',                  'Administrateur',                    true),
    ('SUPPORT_APP_HELPDESK',   'IT Support Applicatif et HelpDesk', false),
    ('RESEAU_TELECOM',         'Réseau télécom',                    false),
    ('SYSTEME_RESEAU_TELECOM', 'Système et Réseau télécom',         false),
    ('SUPPORT_APP',            'IT Support Applicatif',             false)
ON CONFLICT (code) DO UPDATE
    SET libelle = excluded.libelle, transverse = excluded.transverse;

-- 2. Les comptes des profils supprimés basculent vers le profil métier le plus courant.
--    L'administrateur réaffecte ensuite chacun depuis l'écran Administration.
UPDATE core.utilisateur
SET profil_id = (SELECT id FROM core.profil WHERE code = 'SUPPORT_APP_HELPDESK')
WHERE profil_id IN (SELECT id FROM core.profil WHERE code IN ('DSI', 'GESTIONNAIRE', 'DG'));

DELETE FROM core.acces_role WHERE profil_code IN ('DSI', 'GESTIONNAIRE', 'DG');
DELETE FROM core.profil     WHERE code        IN ('DSI', 'GESTIONNAIRE', 'DG');

-- 3. Accès par défaut. Les quatre profils métier partagent l'opérationnel : ils ne se distinguent
--    pas encore par leurs actions (lot suivant, ADR-0003 §4), mais par leur périmètre de travail.
INSERT INTO core.acces_role (profil_code, acces)
SELECT p.code, m.acces
FROM (VALUES
        ('SUPPORT_APP_HELPDESK'), ('RESEAU_TELECOM'),
        ('SYSTEME_RESEAU_TELECOM'), ('SUPPORT_APP')
     ) AS p(code)
CROSS JOIN (VALUES
        ('tableau-de-bord'), ('analyses'), ('incidents'), ('demandes'), ('projets'),
        ('changements'), ('audit'), ('risques'), ('cybersecurite'), ('gouvernance')
     ) AS m(acces)
ON CONFLICT (profil_code, acces) DO NOTHING;

INSERT INTO core.acces_role (profil_code, acces)
SELECT 'ADMIN', m.acces
FROM (VALUES
        ('tableau-de-bord'), ('analyses'), ('incidents'), ('demandes'), ('projets'),
        ('changements'), ('audit'), ('risques'), ('cybersecurite'), ('gouvernance'),
        ('administration')
     ) AS m(acces)
ON CONFLICT (profil_code, acces) DO NOTHING;

-- 4. Une seule direction : la DSI (ADR-0003 §2). Les activités des directions supprimées lui sont
--    rattachées — elles restent visibles et comptabilisées, plutôt que de perdre leur origine.
UPDATE core.activite
SET direction_id = (SELECT id FROM core.direction WHERE code = 'DSI')
WHERE direction_id IS NOT NULL;

UPDATE core.utilisateur
SET direction_id = (SELECT id FROM core.direction WHERE code = 'DSI')
WHERE direction_id IS NOT NULL;

-- Un demandeur vient d'une autre direction : c'est une origine, pas un périmètre de sécurité.
-- On ne le déclare pas DSI ; le champ reste à renseigner quand la notion sera séparée.
UPDATE core.demandeur SET direction_id = NULL WHERE direction_id IS NOT NULL;

DELETE FROM core.direction WHERE code <> 'DSI';

-- 5. Niveaux de support : la DSI n'a que N1 et N2. Le niveau 3 désigne un transfert vers DBS, qui
--    n'a aucun compte ici (ADR-0003 §3). Les éventuels N3 existants redescendent en N2.
UPDATE core.utilisateur SET niveau_support = 2 WHERE niveau_support = 3;

ALTER TABLE core.utilisateur DROP CONSTRAINT utilisateur_niveau_support_check;
ALTER TABLE core.utilisateur ADD CONSTRAINT utilisateur_niveau_support_check
    CHECK (niveau_support IS NULL OR niveau_support BETWEEN 1 AND 2);
