-- Module Inventaire : le parc matériel de la DSI (immobilisations IT).
--
-- Un équipement n'est PAS une activité : ni statut de workflow, ni SLA, ni valideur. Il ne passe
-- donc pas par core.activite mais par sa propre table.
--
-- Le fichier source mêle deux natures : des colonnes comptables (code immo, taux, date et valeur
-- d'acquisition, durée) qui viennent de la comptabilité, et des colonnes de terrain (n° de série,
-- modèle, emplacement, détenteur) que la DSI seule connaît. Les deux cohabitent ici, mais l'import
-- ne les traite pas de la même façon (cf. application/import_equipements).

-- Matricule des agents : c'est par lui que le fichier d'inventaire désigne le détenteur d'un
-- équipement. Sans matricule sur les comptes, aucun rattachement n'est possible.
ALTER TABLE core.utilisateur ADD COLUMN IF NOT EXISTS matricule text;

-- Unique seulement quand il est renseigné : les comptes existants n'en ont pas encore.
CREATE UNIQUE INDEX IF NOT EXISTS uq_utilisateur_matricule
    ON core.utilisateur (upper(btrim(matricule)))
    WHERE matricule IS NOT NULL AND btrim(matricule) <> '';

-- Emplacement physique (site) : GAB EXT, AGENCE ZONE INDUST, AGENCE YIRIMADIO…
CREATE TABLE IF NOT EXISTS core.emplacement (
    id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    libelle text NOT NULL,
    actif   boolean NOT NULL DEFAULT true,
    cree_le timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_emplacement_libelle
    ON core.emplacement (upper(btrim(libelle)));

-- Rattachement porté par le fichier sous l'intitulé « DEPARTEMENT ». Attention : les valeurs
-- observées (GAB SYAMA, SALLE GAB) désignent plutôt un sous-lieu qu'un département au sens RH.
-- On le garde donc comme référentiel libre, distinct de core.direction, tant que ce n'est pas
-- tranché sur le fichier complet.
CREATE TABLE IF NOT EXISTS core.departement_equipement (
    id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    libelle text NOT NULL,
    actif   boolean NOT NULL DEFAULT true,
    cree_le timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_departement_equipement_libelle
    ON core.departement_equipement (upper(btrim(libelle)));

COMMENT ON TABLE core.departement_equipement IS
    'Rattachement des équipements (colonne DEPARTEMENT du fichier d''inventaire). '
    'Distinct de core.direction, qui porte l''organisation de la banque.';

CREATE TABLE IF NOT EXISTS core.equipement (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Code d'immobilisation comptable (INF00208). Clé de rapprochement à l'import ; facultatif
    -- pour un matériel saisi par la DSI avant son entrée en comptabilité.
    code_immo          text,
    numero_serie       text,
    modele             text,
    designation        text NOT NULL,
    emplacement_id     uuid REFERENCES core.emplacement(id),
    departement_id     uuid REFERENCES core.departement_equipement(id),
    -- Détenteur rapproché d'un compte, et matricule brut du fichier : on conserve le second même
    -- quand le premier échoue, pour qu'un import ultérieur puisse rattacher (cf. ADR-0005, même
    -- principe que le gestionnaire d'un ticket importé).
    detenteur_id       uuid REFERENCES core.utilisateur(id) ON DELETE SET NULL,
    matricule_brut     text,
    -- Amortissement : le taux fait foi, la durée sert de contrôle de cohérence.
    taux               numeric(6, 3),
    date_acquisition   date,
    duree_annees       integer,
    valeur_acquisition numeric(16, 2),
    source             text NOT NULL DEFAULT 'SAISIE'
                       CHECK (source IN ('SAISIE', 'IMPORT_IMMO')),
    -- Sorti du parc (cédé, détruit) : conservé pour l'historique, hors des listes actives.
    actif              boolean NOT NULL DEFAULT true,
    cree_le            timestamptz NOT NULL DEFAULT now(),
    maj_le             timestamptz NOT NULL DEFAULT now()
);

-- Idempotence de l'import : un même code immo ne crée jamais de doublon.
CREATE UNIQUE INDEX IF NOT EXISTS uq_equipement_code_immo
    ON core.equipement (upper(btrim(code_immo)))
    WHERE code_immo IS NOT NULL AND btrim(code_immo) <> '';

CREATE INDEX IF NOT EXISTS idx_equipement_emplacement ON core.equipement (emplacement_id);
CREATE INDEX IF NOT EXISTS idx_equipement_departement ON core.equipement (departement_id);
CREATE INDEX IF NOT EXISTS idx_equipement_detenteur ON core.equipement (detenteur_id);
