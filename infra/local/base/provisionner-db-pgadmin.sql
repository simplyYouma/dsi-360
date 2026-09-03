-- ==========================================================================
--  DSI 360 -- Creation de la base, DEPUIS PGADMIN.
--
--  Variante SQL pure de provisionner-db.sql : pgAdmin ne comprend pas les
--  commandes de psql (\gexec, \connect), d'ou ce fichier separe.
--
--  A EXECUTER EN TROIS TEMPS -- voir les etapes ci-dessous. Rejouable sans risque.
-- ==========================================================================


-- ==========================================================================
--  ETAPE 1 -- connecte a la base « postgres » avec le compte SUPERUSER postgres.
--  (pgAdmin : clic droit sur la base « postgres » > Query Tool, puis coller ceci.)
--  Cree le role applicatif, a privileges limites : ni superuser, ni creation de
--  base, ni creation de role. Le superuser cree la base, le role n'en est que
--  proprietaire.
-- ==========================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dsi360') THEN
        CREATE ROLE dsi360 LOGIN PASSWORD 'MOT_DE_PASSE_FORT';
    END IF;
END
$$;

-- Reapplique le mot de passe et les garde-fous, meme si le role preexistait.
ALTER ROLE dsi360 WITH LOGIN PASSWORD 'MOT_DE_PASSE_FORT'
    NOSUPERUSER NOCREATEDB NOCREATEROLE;


-- ==========================================================================
--  ETAPE 2 -- toujours connecte a « postgres », en superuser.
--  CREATE DATABASE ne peut PAS s'executer dans un bloc DO ni dans une
--  transaction : lancez cette ligne SEULE (selectionnez-la, puis F5).
--  Si la base existe deja, pgAdmin dira « database "dsi360" already exists » :
--  c'est sans gravite, passez a l'etape 3.
-- ==========================================================================

CREATE DATABASE dsi360 OWNER dsi360;


-- ==========================================================================
--  ETAPE 3 -- CHANGEZ DE CONNEXION : ouvrez un Query Tool sur la base « dsi360 »
--  (et non plus « postgres »), puis lancez cette ligne.
--  gen_random_uuid() est native depuis PG13, mais l'extension reste requise par
--  les migrations.
-- ==========================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;


-- ==========================================================================
--  ENSUITE : les tables et le compte administrateur ne se creent pas ici.
--  Ils viennent des migrations de l'application, qui n'ont PAS besoin du
--  superuser -- le role dsi360 suffit. Lancez :
--
--      infra\local\migrer.ps1
--
--  ou dites-le simplement a l'assistant, qui s'en charge.
-- ==========================================================================
