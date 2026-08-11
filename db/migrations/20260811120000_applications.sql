-- Module Applications : l'inventaire applicatif (le patrimoine logiciel de la banque).
--
-- Une application n'est pas une activité : ni workflow, ni SLA, ni valideur. Comme l'équipement,
-- elle vit dans sa propre table plutôt que dans core.activite.
--
-- Le fichier source (« Liste des Logiciels/Applications métiers ») porte 21 colonnes dont 8
-- seulement sont renseignées à ce jour. On crée pourtant les 21 : les vides ne sont pas des
-- colonnes inutiles, ce sont celles que la DSI compte remplir depuis l'écran (version, propriétaire,
-- serveurs, port, lien…). Les couper aurait obligé à une migration de plus au premier ajout.

-- Éditeur (ORACLE, CISCO/FORTINET, DBS…). Référentiel plutôt que texte libre : c'est une
-- dimension d'analyse (« tout ce qui vient de tel fournisseur ») et une dépendance à connaître.
-- Alimenté tout seul à l'import, comme les emplacements du parc matériel.
CREATE TABLE IF NOT EXISTS core.editeur_application (
    id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    libelle text NOT NULL,
    actif   boolean NOT NULL DEFAULT true,
    cree_le timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_editeur_application_libelle
    ON core.editeur_application (upper(btrim(libelle)));

COMMENT ON TABLE core.editeur_application IS
    'Éditeurs / fournisseurs des applications (colonne « Editeur » du fichier source).';

-- Référence système « APP-00001 », attribuée par la plateforme et jamais saisie — même principe
-- que la référence INV du parc matériel : un repère stable, indépendant du nom commercial, qui
-- survit au renommage d'une application.
CREATE SEQUENCE IF NOT EXISTS core.application_reference_seq;

CREATE TABLE IF NOT EXISTS core.application (
    id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    reference              text NOT NULL
        DEFAULT 'APP-' || lpad(nextval('core.application_reference_seq')::text, 5, '0'),
    -- Nom du logiciel (« AFG E-bank (OBDX) »). Seul champ vraiment obligatoire : une application
    -- sans nom serait introuvable.
    nom                    text NOT NULL,
    -- Ce que l'application fait tourner côté métier (« Banque mobile »), et le détail de ses
    -- fonctions. Deux textes libres : ils ne se répètent jamais d'une application à l'autre.
    processus_metier       text,
    fonctionnalites        text,
    version                text,
    editeur_id             uuid REFERENCES core.editeur_application(id),
    -- Où tournent les données. Le fichier écrit « Banque » / « Hors Banque » dans la colonne
    -- « Pays de localisation des bases de données » : ce n'est pas un pays, c'est un lieu
    -- d'hébergement. On le range donc ici, sous son vrai sens (INTERNE / EXTERNE / INCONNU),
    -- et la colonne « pays » du fichier reste disponible pour un vrai pays.
    hebergement            text,
    pays_donnees           text,
    -- L'application échange-t-elle avec d'autres (OUI / NON / NA) ? C'est le premier signal
    -- d'un effet de bord lors d'un changement.
    interfacage            text,
    -- Cycle de vie : EN_SERVICE, EN_PROJET, ARRETE. Texte et non contrainte figée — un statut
    -- nouveau ne doit pas demander une migration (même choix que l'état constaté du parc).
    statut                 text NOT NULL DEFAULT 'EN_SERVICE',
    proprietaire           text,
    date_debut             date,
    date_fin               date,
    nb_comptes_actifs      integer,
    lien                   text,
    serveur_application    text,
    serveur_base           text,
    port                   text,
    -- Qui l'administre, et qui prend le relais. Texte libre, jamais un compte : le fichier y
    -- inscrit parfois deux personnes (« Youssouf DIARRA / Soungalo SIDIBE »), parfois une
    -- adresse de support prestataire. On conserve ce qui est écrit plutôt que d'inventer un
    -- rattachement — même principe que le gestionnaire d'un ticket importé (ADR-0005).
    administrateur         text,
    administrateur_secours text,
    -- Retirée du parc applicatif sans être effacée : l'historique d'une application décommissionnée
    -- reste consultable.
    actif                  boolean NOT NULL DEFAULT true,
    source                 text NOT NULL DEFAULT 'SAISIE',
    cree_le                timestamptz NOT NULL DEFAULT now(),
    maj_le                 timestamptz NOT NULL DEFAULT now()
);

-- Le nom identifie l'application : deux fiches pour le même logiciel scinderaient son suivi.
-- C'est aussi la clé de rapprochement du chargement initial (insertion idempotente).
CREATE UNIQUE INDEX IF NOT EXISTS uq_application_nom
    ON core.application (upper(btrim(nom)));
CREATE UNIQUE INDEX IF NOT EXISTS uq_application_reference ON core.application (reference);
CREATE INDEX IF NOT EXISTS ix_application_editeur ON core.application (editeur_id);
CREATE INDEX IF NOT EXISTS ix_application_statut ON core.application (statut);

COMMENT ON TABLE core.application IS
    'Inventaire applicatif : le patrimoine logiciel, ses éditeurs, ses administrateurs et son '
    'hébergement. Alimenté une première fois par la liste des logiciels métiers, tenu à jour '
    'ensuite depuis l''écran.';

-- Le module s'ouvre aux profils existants, en une passe unique (cf. 20260722120000_acces_inventaire) :
-- le seed n'est jamais rejoué en production, un nouveau module s'y déploie donc par migration.
-- Si l'administrateur retire ensuite l'accès à un profil, rien ne le réintroduira.
INSERT INTO core.acces_role (profil_code, acces)
SELECT DISTINCT ar.profil_code, 'applications'
FROM core.acces_role ar
ON CONFLICT DO NOTHING;
