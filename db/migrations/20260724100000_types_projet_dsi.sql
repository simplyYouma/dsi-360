-- Types de projet au niveau DSI, avec leur déroulé.
--
-- Remplace le jeu de départ trop vague du 20260724090000 : on nomme les natures réelles de
-- projets que conduit la DSI — développement, réseau, infrastructure, sécurité, migration,
-- étude — plutôt que des intitulés qu'on ne sait pas relier à un vrai projet.
--
-- On ne touche qu'aux types encore inutilisés. Un type déjà porté par un projet reste tel quel :
-- son libellé et ses jalons appartiennent à l'histoire du dossier, on ne les réécrit pas dans son
-- dos. L'administrateur, lui, reste libre d'ajouter, de renommer et de retirer depuis l'écran.

-- 1. Retirer les types de départ restés sans projet (leurs jalons modèles suivent en cascade).
DELETE FROM core.categorie c
WHERE c.module = 'projet'
  AND c.code IN (
      'DEPLOIEMENT_APPLICATIF', 'INFRASTRUCTURE', 'MIGRATION', 'SECURITE', 'ETUDE_ET_CADRAGE'
  )
  AND NOT EXISTS (SELECT 1 FROM core.activite a WHERE a.categorie_id = c.id);

-- 2. Le jeu DSI. Un code déjà présent (type utilisé, non retiré ci-dessus) est laissé intact.
INSERT INTO core.categorie (module, code, libelle) VALUES
    ('projet', 'DEVELOPPEMENT_APPLICATIF', 'Développement applicatif'),
    ('projet', 'RESEAU_TELECOM',           'Réseau et télécom'),
    ('projet', 'INFRASTRUCTURE',           'Infrastructure et systèmes'),
    ('projet', 'SECURITE',                 'Sécurité'),
    ('projet', 'MIGRATION',                'Migration'),
    ('projet', 'ETUDE_ET_CADRAGE',         'Étude et cadrage')
ON CONFLICT (module, code) DO NOTHING;

-- 3. Leur déroulé habituel — un point de départ, que le chef de projet ajuste ensuite.
INSERT INTO core.modele_jalon (categorie_id, titre, ordre)
SELECT c.id, m.titre, m.ordre
FROM core.categorie c
JOIN (VALUES
    ('DEVELOPPEMENT_APPLICATIF', 'Expression de besoin validée',        1),
    ('DEVELOPPEMENT_APPLICATIF', 'Conception et cadrage technique',     2),
    ('DEVELOPPEMENT_APPLICATIF', 'Développement',                       3),
    ('DEVELOPPEMENT_APPLICATIF', 'Tests et recette utilisateurs',       4),
    ('DEVELOPPEMENT_APPLICATIF', 'Mise en production',                  5),
    ('DEVELOPPEMENT_APPLICATIF', 'Période de garantie',                 6),

    ('RESEAU_TELECOM',           'Étude technique validée',             1),
    ('RESEAU_TELECOM',           'Commande des équipements',            2),
    ('RESEAU_TELECOM',           'Réception du matériel',               3),
    ('RESEAU_TELECOM',           'Installation et configuration',       4),
    ('RESEAU_TELECOM',           'Tests et bascule',                    5),
    ('RESEAU_TELECOM',           'Recette et documentation',            6),

    ('INFRASTRUCTURE',           'Étude et dimensionnement',            1),
    ('INFRASTRUCTURE',           'Acquisition validée',                 2),
    ('INFRASTRUCTURE',           'Installation',                        3),
    ('INFRASTRUCTURE',           'Configuration et intégration',        4),
    ('INFRASTRUCTURE',           'Tests de qualification',              5),
    ('INFRASTRUCTURE',           'Mise en service',                     6),

    ('SECURITE',                 'Analyse de risque',                   1),
    ('SECURITE',                 'Définition des mesures',              2),
    ('SECURITE',                 'Mise en œuvre',                       3),
    ('SECURITE',                 'Contrôle d''efficacité',              4),
    ('SECURITE',                 'Bilan de conformité',                 5),

    ('MIGRATION',                'État des lieux de l''existant',       1),
    ('MIGRATION',                'Plan de migration et retour arrière', 2),
    ('MIGRATION',                'Migration à blanc concluante',        3),
    ('MIGRATION',                'Migration réelle',                    4),
    ('MIGRATION',                'Vérification post-migration',         5),
    ('MIGRATION',                'Décommissionnement de l''ancien',     6),

    ('ETUDE_ET_CADRAGE',         'Recueil du besoin',                   1),
    ('ETUDE_ET_CADRAGE',         'Analyse des options',                 2),
    ('ETUDE_ET_CADRAGE',         'Chiffrage',                           3),
    ('ETUDE_ET_CADRAGE',         'Note de cadrage rédigée',             4),
    ('ETUDE_ET_CADRAGE',         'Décision COPIL',                      5)
) AS m(code, titre, ordre) ON m.code = c.code
WHERE c.module = 'projet'
ON CONFLICT (categorie_id, titre) DO NOTHING;
