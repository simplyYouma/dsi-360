-- Base de vérification des sauvegardes — à lancer UNE SEULE FOIS, en superuser postgres :
--   & "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -f infra\local\base\provisionner-db-verif.sql
--
-- `infra\local\serveur\verifier-restauration.ps1` y restaure chaque semaine la dernière
-- sauvegarde, compte ce qui en sort, puis vide la base. Elle ne sert qu'à cela : son contenu est
-- jetable, et la base de production n'est jamais touchée.
--
-- Le rôle applicatif garde ses privilèges limités (ni CREATEDB ni superuser) : c'est le superuser
-- qui crée la base, le rôle n'en est que propriétaire. Donner CREATEDB au compte de production
-- pour qu'il fabrique lui-même sa base de contrôle élargirait les droits du compte qui sert
-- l'application — un prix bien trop élevé pour une vérification hebdomadaire.

SELECT 'CREATE DATABASE dsi360_verif OWNER dsi360'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'dsi360_verif')
\gexec

-- gen_random_uuid() : fournie par pgcrypto sur les versions anciennes, native depuis PG13.
\connect dsi360_verif
CREATE EXTENSION IF NOT EXISTS pgcrypto;
