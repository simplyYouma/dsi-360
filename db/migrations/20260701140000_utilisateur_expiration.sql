-- Comptes temporaires : date d'expiration d'accès (NULL = compte permanent). Au-delà de cette date,
-- l'accès est refusé côté serveur à chaque requête (comme le blocage via actif = false).
ALTER TABLE core.utilisateur ADD COLUMN expire_le timestamptz;
