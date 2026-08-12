-- Qui répond d'une application : plusieurs personnes, et pas toujours des comptes.
--
-- Jusqu'ici, « administrateur » et « administrateur de secours » étaient deux colonnes de texte.
-- Deux limites, l'une et l'autre rencontrées dès le premier chargement :
--   1. le fichier y inscrit souvent DEUX personnes (« Youssouf DIARRA / Soungalo SIDIBE ») ;
--   2. quand c'est un agent de la maison, on veut le désigner par son compte — pour que la fiche
--      suive le nom s'il change, et qu'on puisse remonter à la personne.
--
-- On passe donc à une table de rattachement, sur le modèle de core.activite_acteur : un compte
-- OU un nom libre (prestataire, adresse de support, personne sans compte), plusieurs par rôle.

CREATE TABLE IF NOT EXISTS core.application_responsable (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id uuid NOT NULL REFERENCES core.application(id) ON DELETE CASCADE,
    -- Compte rattaché, quand la personne en a un. ON DELETE SET NULL : la suppression d'un compte
    -- ne doit pas effacer le fait qu'une application avait un responsable — le nom libre prend
    -- alors le relais si on l'a, sinon la ligne reste et se voit comme « à réattribuer ».
    utilisateur_id uuid REFERENCES core.utilisateur(id) ON DELETE SET NULL,
    -- Nom écrit à la main : prestataire, support éditeur, personne sans compte.
    nom_libre      text,
    -- ADMIN (celui qui en répond) ou SECOURS (le relais).
    role           text NOT NULL,
    ordre          integer NOT NULL DEFAULT 0,
    cree_le        timestamptz NOT NULL DEFAULT now(),
    -- Une ligne qui ne désigne personne n'a pas de sens.
    CONSTRAINT ck_application_responsable_designe
        CHECK (utilisateur_id IS NOT NULL OR btrim(coalesce(nom_libre, '')) <> '')
);

CREATE INDEX IF NOT EXISTS ix_application_responsable_app
    ON core.application_responsable (application_id, role, ordre);

-- Jamais deux fois le même compte pour le même rôle sur la même application.
CREATE UNIQUE INDEX IF NOT EXISTS uq_application_responsable_compte
    ON core.application_responsable (application_id, role, utilisateur_id)
    WHERE utilisateur_id IS NOT NULL;

-- Idem pour un nom libre (comparaison insensible à la casse et aux espaces).
CREATE UNIQUE INDEX IF NOT EXISTS uq_application_responsable_nom
    ON core.application_responsable (application_id, role, upper(btrim(nom_libre)))
    WHERE utilisateur_id IS NULL;

COMMENT ON TABLE core.application_responsable IS
    'Responsables d''une application (ADMIN / SECOURS) : un compte ou un nom libre, plusieurs '
    'par rôle. Même principe que core.activite_acteur.';

-- --- Reprise de l'existant ---------------------------------------------------------------------
-- Les deux colonnes de texte portent parfois plusieurs personnes, séparées par « / » ou « , ».
-- On découpe, on nettoie, et l'on rattache au compte quand le nom correspond EXACTEMENT à un
-- agent (comparaison insensible à la casse). Aucun rapprochement approximatif : mieux vaut un nom
-- libre exact qu'un compte deviné (même principe que le gestionnaire d'un ticket importé).
WITH decoupe AS (
    SELECT a.id AS application_id,
           r.role,
           btrim(part.nom) AS nom,
           part.ordinalite - 1 AS ordre
    FROM core.application a
    CROSS JOIN LATERAL (
        VALUES ('ADMIN', a.administrateur), ('SECOURS', a.administrateur_secours)
    ) AS r(role, texte)
    CROSS JOIN LATERAL unnest(
        string_to_array(replace(coalesce(r.texte, ''), ',', '/'), '/')
    ) WITH ORDINALITY AS part(nom, ordinalite)
    WHERE btrim(part.nom) <> ''
)
INSERT INTO core.application_responsable (application_id, utilisateur_id, nom_libre, role, ordre)
SELECT d.application_id,
       u.id,
       CASE WHEN u.id IS NULL THEN d.nom END,
       d.role,
       d.ordre
FROM decoupe d
LEFT JOIN core.utilisateur u
       ON upper(btrim(u.prenom || ' ' || u.nom)) = upper(d.nom)
ON CONFLICT DO NOTHING;

-- Les colonnes de texte ont fait leur office : les garder ferait deux sources de vérité pour la
-- même question, et l'une des deux finirait par mentir.
ALTER TABLE core.application DROP COLUMN IF EXISTS administrateur;
ALTER TABLE core.application DROP COLUMN IF EXISTS administrateur_secours;
