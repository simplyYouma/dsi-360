-- Frein sur les tentatives de connexion : un mot de passe ne se devine pas en boucle.
--
-- Le verrou est temporaire (cf. settings.login_verrou_minutes). Un verrou définitif donnerait à un
-- attaquant le pouvoir d'exclure n'importe quel agent du système en se trompant exprès.

ALTER TABLE core.utilisateur
    ADD COLUMN IF NOT EXISTS echecs_connexion smallint NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS verrouille_jusqu_a timestamptz;

COMMENT ON COLUMN core.utilisateur.echecs_connexion IS
    'Échecs consécutifs depuis la dernière connexion réussie. Remis à zéro au succès et au verrou.';
COMMENT ON COLUMN core.utilisateur.verrouille_jusqu_a IS
    'Instant avant lequel toute connexion est refusée (429), même avec le bon mot de passe.';
