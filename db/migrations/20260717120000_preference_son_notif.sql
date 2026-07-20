-- Le carillon de notification suit le compte, pas le navigateur.
--
-- Il était réglé en stockage local : un agent qui change de poste, ou vide son cache, retrouvait
-- le réglage par défaut. Rattaché au compte, il le suit partout — c'est une préférence de la
-- personne, au même titre que le canal e-mail.
--
-- Actif par défaut, comme les autres canaux : une notification qu'on n'entend pas ne sert à rien.

ALTER TABLE core.preference_notification
    ADD COLUMN IF NOT EXISTS son boolean NOT NULL DEFAULT true;
