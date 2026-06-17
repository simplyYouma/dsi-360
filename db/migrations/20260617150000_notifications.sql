-- Notifications internes (canal "interne" du cahier ; l'e-mail s'ajoute par-dessus).
-- Alimentées notamment par l'ordonnanceur SLA (approche / dépassement d'échéance).

CREATE TABLE core.notification (
    id              bigserial PRIMARY KEY,
    destinataire_id uuid REFERENCES core.utilisateur(id) ON DELETE CASCADE,
    activite_id     uuid REFERENCES core.activite(id) ON DELETE CASCADE,
    type            text NOT NULL,          -- SLA_APPROCHE, SLA_DEPASSE, AFFECTATION, ...
    titre           text NOT NULL,
    message         text NOT NULL,
    lu              boolean NOT NULL DEFAULT false,
    cree_le         timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_notification_destinataire ON core.notification(destinataire_id, lu);

-- Évite les doublons d'alerte SLA pour une même activité et un même type.
CREATE UNIQUE INDEX uq_notification_sla
    ON core.notification(activite_id, type)
    WHERE type IN ('SLA_APPROCHE', 'SLA_DEPASSE');
