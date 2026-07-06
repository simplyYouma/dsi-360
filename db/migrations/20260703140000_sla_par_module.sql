-- SLA par MODULE : chaque type d'activité a ses propres cibles P1..P5 (le cahier demande des SLA
-- paramétrables par type d'activité). On passe la clé de (priorité) à (module, priorité).
-- Les lignes globales existantes sont réaffectées au module 'incident' (cibles ITIL de départ).

ALTER TABLE core.sla_regle ADD COLUMN module text;
UPDATE core.sla_regle SET module = 'incident' WHERE module IS NULL;
ALTER TABLE core.sla_regle ALTER COLUMN module SET NOT NULL;
ALTER TABLE core.sla_regle DROP CONSTRAINT sla_regle_pkey;
ALTER TABLE core.sla_regle ADD CONSTRAINT sla_regle_pkey PRIMARY KEY (module, priorite);

-- Cibles par défaut, distinctes par module (prise en charge, résolution) en minutes. Éditables
-- ensuite depuis l'administration (un incident P1 ≠ une demande P1).
INSERT INTO core.sla_regle (module, priorite, prise_en_charge_minutes, resolution_minutes) VALUES
    -- Demandes de service : prise en charge plus souple qu'un incident.
    ('demande', 1, 30, 480), ('demande', 2, 60, 960), ('demande', 3, 240, 2880),
    ('demande', 4, 1440, 7200), ('demande', 5, 2880, 14400),
    -- Changements (ITIL) : planifiés, délais plus longs.
    ('changement', 1, 60, 1440), ('changement', 2, 120, 2880), ('changement', 3, 480, 5760),
    ('changement', 4, 1440, 10080), ('changement', 5, 2880, 20160),
    -- Problèmes : analyse de fond.
    ('probleme', 1, 60, 1440), ('probleme', 2, 120, 2880), ('probleme', 3, 480, 5760),
    ('probleme', 4, 1440, 10080), ('probleme', 5, 2880, 20160),
    -- Cybersécurité : traitement strict.
    ('cybersecurite', 1, 15, 240), ('cybersecurite', 2, 30, 480), ('cybersecurite', 3, 120, 1440),
    ('cybersecurite', 4, 1440, 5760), ('cybersecurite', 5, 2880, 11520)
ON CONFLICT (module, priorite) DO NOTHING;

COMMENT ON TABLE core.sla_regle IS
    'Cibles SLA par (module, priorite) en minutes, reparametrable sans deploiement.';
