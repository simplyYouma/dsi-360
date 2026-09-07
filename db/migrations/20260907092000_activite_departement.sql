-- Le département d'une activité : à quel département de la DSI ce dossier appartient.
--
-- Posé pour la GOUVERNANCE, où le besoin est né : un sujet de COPIL relève de « Production et
-- Applicatif » ou de « Réseau et Infrastructure », et les analyses doivent pouvoir le dire. La
-- colonne vit néanmoins sur `core.activite`, comme `direction_id` : c'est une propriété
-- d'organisation du dossier, pas une particularité de module — les autres modules l'adopteront
-- sans nouvelle migration le jour où ce sera décidé.
--
-- Nullable, et elle le restera : les incidents et les demandes viennent du rapport SysAid, qui ne
-- connaît pas le découpage interne de la DSI. Les y forcer produirait des milliers de lignes
-- remplies au hasard — les analyses par département en deviendraient trompeuses.
--
-- Rappel : ce champ n'entre PAS dans le cloisonnement des accès. Le périmètre de sécurité reste la
-- direction (`autorisations.visible`).

ALTER TABLE core.activite
    ADD COLUMN IF NOT EXISTS departement_id uuid REFERENCES core.departement(id);

COMMENT ON COLUMN core.activite.departement_id IS
    'Departement de la DSI dont releve le dossier. Sert au rangement et aux analyses, jamais au '
    'cloisonnement des acces (qui reste porte par direction_id).';

-- Index partiel : seules les activités effectivement rattachées sont indexées. Sur un parc où la
-- très grande majorité des lignes vient de l'import et restera sans département, un index complet
-- coûterait de la place pour ne rien accélérer.
CREATE INDEX IF NOT EXISTS idx_activite_departement
    ON core.activite (departement_id)
 WHERE departement_id IS NOT NULL;
