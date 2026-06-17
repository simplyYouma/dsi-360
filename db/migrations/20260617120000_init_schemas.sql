-- DSI 360 — migration initiale : schémas + socle de domaine (Activité, RBAC, audit).
-- Voir docs/02-DOMAIN-MODEL.md. Migration jamais modifiée rétroactivement.

CREATE SCHEMA IF NOT EXISTS core;   -- référentiels + données métier
CREATE SCHEMA IF NOT EXISTS audit;  -- journal append-only

COMMENT ON SCHEMA core IS 'Référentiels et activités de la DSI.';
COMMENT ON SCHEMA audit IS 'Journal d''audit append-only et chaîné.';

-- Profils (RBAC, 7 profils). transverse = voit au-delà de son périmètre.
CREATE TABLE core.profil (
    id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code      text NOT NULL UNIQUE,         -- ADMIN, DSI, CHEF_SERVICE, CHEF_PROJET, TECHNICIEN, METIER, DG
    libelle   text NOT NULL,
    transverse boolean NOT NULL DEFAULT false
);

CREATE TABLE core.direction (
    id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code    text NOT NULL UNIQUE,
    libelle text NOT NULL
);

CREATE TABLE core.utilisateur (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email            text NOT NULL UNIQUE,
    nom              text NOT NULL,
    prenom           text NOT NULL,
    profil_id        uuid NOT NULL REFERENCES core.profil(id),
    direction_id     uuid REFERENCES core.direction(id),  -- périmètre (NULL si transverse)
    source_auth      text NOT NULL DEFAULT 'LOCAL' CHECK (source_auth IN ('LOCAL','OIDC','LDAP')),
    mot_de_passe_hash text,                 -- uniquement pour les comptes LOCAL
    actif            boolean NOT NULL DEFAULT true,
    doit_changer_mdp boolean NOT NULL DEFAULT false,
    cree_le          timestamptz NOT NULL DEFAULT now()
);

-- Catégories paramétrables par module.
CREATE TABLE core.categorie (
    id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    module  text NOT NULL,                  -- incident, demande, probleme, changement, projet, audit, risque
    code    text NOT NULL,
    libelle text NOT NULL,
    UNIQUE (module, code)
);

-- Entité pivot : Activité (socle commun à tous les modules). Détails métier dans `donnees` (jsonb).
CREATE TABLE core.activite (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    reference       text NOT NULL UNIQUE,                 -- INC-2026-00042, DEM-…, CHG-…
    module          text NOT NULL,                        -- incident, demande, probleme, changement, projet, audit, risque
    titre           text NOT NULL,
    description     text,
    direction_id    uuid REFERENCES core.direction(id),
    categorie_id    uuid REFERENCES core.categorie(id),
    demandeur_id    uuid REFERENCES core.utilisateur(id),
    responsable_id  uuid REFERENCES core.utilisateur(id),
    impact          smallint,                             -- 1..5
    urgence         smallint,                             -- 1..5
    priorite        smallint CHECK (priorite BETWEEN 1 AND 5),  -- P1..P5 (1 = critique)
    statut          text NOT NULL,                        -- propre au module (cf. machines à états)
    sla_prise_en_charge_le timestamptz,
    sla_resolution_le      timestamptz,
    cree_le          timestamptz NOT NULL DEFAULT now(),
    pris_en_charge_le timestamptz,
    resolu_le        timestamptz,
    cloture_le       timestamptz,
    donnees          jsonb NOT NULL DEFAULT '{}'::jsonb,  -- champs spécifiques du module (CAB, jalons, criticité…)
    CONSTRAINT chk_impact CHECK (impact IS NULL OR impact BETWEEN 1 AND 5),
    CONSTRAINT chk_urgence CHECK (urgence IS NULL OR urgence BETWEEN 1 AND 5)
);
CREATE INDEX idx_activite_module_statut ON core.activite(module, statut);
CREATE INDEX idx_activite_responsable ON core.activite(responsable_id);
CREATE INDEX idx_activite_echeance ON core.activite(sla_resolution_le);

-- Acteurs additionnels d'une activité (contributeurs, valideurs).
CREATE TABLE core.activite_acteur (
    activite_id   uuid NOT NULL REFERENCES core.activite(id) ON DELETE CASCADE,
    utilisateur_id uuid NOT NULL REFERENCES core.utilisateur(id),
    role          text NOT NULL CHECK (role IN ('CONTRIBUTEUR','VALIDEUR')),
    PRIMARY KEY (activite_id, utilisateur_id, role)
);

-- Journal d'audit append-only et chaîné (cf. docs/04-SECURITY.md).
CREATE TABLE audit.journal (
    id             bigserial PRIMARY KEY,
    horodatage     timestamptz NOT NULL DEFAULT now(),
    acteur_id      uuid,
    acteur_email   text,                                  -- figé à l'écriture (survit à la suppression)
    module         text,
    action         text NOT NULL,
    cible_type     text,
    cible_id       text,
    ancienne_valeur jsonb,
    nouvelle_valeur jsonb,
    adresse_ip     inet,
    hash_precedent text,
    hash_courant   text NOT NULL
);
CREATE INDEX idx_journal_horodatage ON audit.journal(horodatage DESC);
