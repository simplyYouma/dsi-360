-- Département : le niveau d'organisation qui manquait entre la direction et le profil.
--
-- La DSI doit distinguer ce qui relève de « Production et Applicatif » de ce qui relève de
-- « Réseau et Infrastructure », à la saisie comme à la lecture. Le système ne connaissait qu'un
-- seul niveau — la DIRECTION — et celle-ci sert de **cloisonnement de sécurité** : elle décide ce
-- qu'un agent a le droit de voir (`autorisations.visible`). On ne pouvait donc pas s'en servir pour
-- ranger, sans du même coup cacher.
--
-- Le département, lui, ORGANISE et ANALYSE. Il ne masque rien : deux agents de départements
-- différents continuent de voir les mêmes dossiers de leur direction. Confondre les deux rôles
-- aurait transformé un besoin de lisibilité en cloisonnement d'accès non demandé.
--
-- Il est porté par le PROFIL, pas par le compte : le département d'un agent se déduit de son
-- profil, une seule vérité, aucune divergence possible. Un profil transverse (ADMIN) n'appartient
-- à aucun département — d'où la colonne nullable.

CREATE TABLE IF NOT EXISTS core.departement (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code         text NOT NULL UNIQUE,
    libelle      text NOT NULL,
    direction_id uuid NOT NULL REFERENCES core.direction(id),
    cree_le      timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE core.departement IS
    'Subdivision d''une direction. Sert a organiser et a analyser, JAMAIS a cloisonner les acces : '
    'le perimetre de securite reste core.direction.';

-- Unicite du libelle insensible a la casse et aux espaces : « Production et Applicatif » et
-- « production et applicatif  » sont le meme departement, et l'ecran d'administration s'appuie
-- dessus pour refuser un doublon avant de l'ecrire.
CREATE UNIQUE INDEX IF NOT EXISTS uq_departement_libelle
    ON core.departement (upper(btrim(libelle)));

ALTER TABLE core.profil
    ADD COLUMN IF NOT EXISTS departement_id uuid REFERENCES core.departement(id);

COMMENT ON COLUMN core.profil.departement_id IS
    'Departement du profil. NULL pour un profil transverse, qui n''appartient a aucun departement.';

-- Les deux departements de la DSI. Idempotent : relancer la migration ne duplique rien.
INSERT INTO core.departement (code, libelle, direction_id)
SELECT v.code, v.libelle, d.id
  FROM (VALUES
        ('PRODUCTION_APPLICATIF', 'Production et Applicatif'),
        ('RESEAU_INFRASTRUCTURE', 'Réseau et Infrastructure')
       ) AS v(code, libelle)
  JOIN core.direction d ON d.code = 'DSI'
ON CONFLICT (code) DO NOTHING;

-- Rattachement des profils EXISTANTS, selon leur nature. On ne fusionne ni ne renomme : le systeme
-- est en production, ces profils portent des comptes reels et leurs acces. Changer un profil,
-- c'est changer les droits de quelqu'un ; ce n'est pas le role d'une migration de structure.
-- Le renommage se fait depuis l'ecran d'administration, qui sait deja le faire sans toucher au code
-- technique ni aux comptes.
--
-- La clause « departement_id IS NULL » rend le rattachement rejouable sans ecraser un choix fait
-- ensuite a l'ecran.
UPDATE core.profil p
   SET departement_id = d.id
  FROM core.departement d
 WHERE d.code = 'PRODUCTION_APPLICATIF'
   AND p.code IN ('SUPPORT_APP_HELPDESK', 'SUPPORT_APP')
   AND p.departement_id IS NULL;

UPDATE core.profil p
   SET departement_id = d.id
  FROM core.departement d
 WHERE d.code = 'RESEAU_INFRASTRUCTURE'
   AND p.code IN ('RESEAU_TELECOM', 'SYSTEME_RESEAU_TELECOM')
   AND p.departement_id IS NULL;
