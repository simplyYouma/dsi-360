-- Base de test dédiée — à lancer UNE SEULE FOIS, en superuser postgres :
--   & "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -f infra\local\provisionner-db-test.sql
--
-- La suite de tests (backend/tests/conftest.py) y joue les migrations puis exécute chaque test
-- dans une transaction annulée à la fin. Elle refuse de tourner sur une base dont le nom ne
-- finit pas par « _test » : aucun risque pour la base de développement.
--
-- Le rôle applicatif garde ses privilèges limités (ni CREATEDB ni superuser) : c'est le
-- superuser qui crée la base, le rôle n'en est que propriétaire.

SELECT 'CREATE DATABASE dsi360_test OWNER dsi360'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'dsi360_test')
\gexec

-- gen_random_uuid() : fournie par pgcrypto sur les versions anciennes, native depuis PG13.
\connect dsi360_test
CREATE EXTENSION IF NOT EXISTS pgcrypto;
