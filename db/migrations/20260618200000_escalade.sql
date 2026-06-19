-- Escalade : une seule alerte d'escalade par activité (dédoublonnage).
CREATE UNIQUE INDEX uq_notification_escalade
    ON core.notification(activite_id, type)
    WHERE type = 'ESCALADE';
