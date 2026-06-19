-- SLA paramétrables : cibles de prise en charge et de résolution par priorité (minutes).
-- Remplacent les valeurs en dur ; éditables depuis l'administration.
CREATE TABLE core.sla_regle (
    priorite                smallint PRIMARY KEY CHECK (priorite BETWEEN 1 AND 5),
    prise_en_charge_minutes int NOT NULL CHECK (prise_en_charge_minutes > 0),
    resolution_minutes      int NOT NULL CHECK (resolution_minutes > 0),
    maj_le                  timestamptz NOT NULL DEFAULT now()
);

-- Valeurs initiales = cibles ITIL par défaut (P1 le plus strict).
INSERT INTO core.sla_regle (priorite, prise_en_charge_minutes, resolution_minutes) VALUES
    (1, 15, 240),
    (2, 30, 480),
    (3, 120, 2880),
    (4, 1440, 7200),
    (5, 2880, 14400);

COMMENT ON TABLE core.sla_regle IS 'Cibles SLA par priorite (minutes), reparametrable sans deploiement.';
