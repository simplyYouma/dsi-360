-- Préférences de notification par utilisateur (canaux). Cf. cahier §6.
-- E-mail + interne actifs ; Teams / WhatsApp prévus en Phase 2.

CREATE TABLE core.preference_notification (
    utilisateur_id uuid PRIMARY KEY REFERENCES core.utilisateur(id) ON DELETE CASCADE,
    interne   boolean NOT NULL DEFAULT true,
    email     boolean NOT NULL DEFAULT true,
    teams     boolean NOT NULL DEFAULT false,
    whatsapp  boolean NOT NULL DEFAULT false
);
