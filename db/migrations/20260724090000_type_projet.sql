-- Type de projet, et les jalons qu'il amène avec lui.
--
-- Tous les projets ne se ressemblent pas : un déploiement applicatif ne passe pas par les mêmes
-- étapes qu'une migration de données. Le type est une catégorie du module « projet » (donc
-- paramétrable comme les autres, cf. CLAUDE.md §6.2) ; ce qu'on ajoute ici, c'est la liste des
-- jalons que chaque type pose d'office à la création d'un projet.
--
-- Un modèle n'est qu'un point de départ : une fois posés, les jalons appartiennent au projet et
-- se modifient librement. Changer un modèle ne touche donc aucun projet existant.
CREATE TABLE core.modele_jalon (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    categorie_id uuid NOT NULL REFERENCES core.categorie(id) ON DELETE CASCADE,
    titre        text NOT NULL,
    ordre        integer NOT NULL DEFAULT 0,
    cree_le      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (categorie_id, titre)
);
CREATE INDEX idx_modele_jalon_categorie ON core.modele_jalon (categorie_id, ordre);

-- Jeu de départ : les types de projet que la DSI conduit réellement, avec leur déroulé habituel.
-- L'administrateur en ajoute, en retire, et réécrit les jalons ; rien ici n'est figé.
INSERT INTO core.categorie (module, code, libelle) VALUES
    ('projet', 'DEPLOIEMENT_APPLICATIF', 'Déploiement applicatif'),
    ('projet', 'INFRASTRUCTURE',         'Infrastructure'),
    ('projet', 'MIGRATION',              'Migration'),
    ('projet', 'SECURITE',               'Sécurité'),
    ('projet', 'ETUDE_ET_CADRAGE',       'Étude et cadrage')
ON CONFLICT (module, code) DO NOTHING;

INSERT INTO core.modele_jalon (categorie_id, titre, ordre)
SELECT c.id, m.titre, m.ordre
FROM core.categorie c
JOIN (VALUES
    ('DEPLOIEMENT_APPLICATIF', 'Expression de besoin validée',        1),
    ('DEPLOIEMENT_APPLICATIF', 'Solution retenue',                    2),
    ('DEPLOIEMENT_APPLICATIF', 'Installation en environnement test',  3),
    ('DEPLOIEMENT_APPLICATIF', 'Recette utilisateurs prononcée',      4),
    ('DEPLOIEMENT_APPLICATIF', 'Mise en production',                  5),
    ('DEPLOIEMENT_APPLICATIF', 'Transfert au support',                6),

    ('INFRASTRUCTURE',         'Étude technique validée',             1),
    ('INFRASTRUCTURE',         'Commande passée',                     2),
    ('INFRASTRUCTURE',         'Matériel réceptionné',                3),
    ('INFRASTRUCTURE',         'Installation et configuration',       4),
    ('INFRASTRUCTURE',         'Tests et bascule',                    5),
    ('INFRASTRUCTURE',         'Documentation remise',                6),

    ('MIGRATION',              'État des lieux de l''existant',       1),
    ('MIGRATION',              'Plan de migration et retour arrière', 2),
    ('MIGRATION',              'Migration à blanc concluante',        3),
    ('MIGRATION',              'Migration réelle',                    4),
    ('MIGRATION',              'Vérification post-migration',         5),
    ('MIGRATION',              'Décommissionnement de l''ancien',     6),

    ('SECURITE',               'Analyse de risque',                   1),
    ('SECURITE',               'Mesures définies',                    2),
    ('SECURITE',               'Mise en œuvre',                       3),
    ('SECURITE',               'Contrôle d''efficacité',              4),
    ('SECURITE',               'Bilan de conformité',                 5),

    ('ETUDE_ET_CADRAGE',       'Recueil du besoin',                   1),
    ('ETUDE_ET_CADRAGE',       'Analyse des options',                 2),
    ('ETUDE_ET_CADRAGE',       'Chiffrage',                           3),
    ('ETUDE_ET_CADRAGE',       'Note de cadrage rédigée',             4),
    ('ETUDE_ET_CADRAGE',       'Décision COPIL',                      5)
) AS m(code, titre, ordre) ON m.code = c.code
WHERE c.module = 'projet'
ON CONFLICT (categorie_id, titre) DO NOTHING;
