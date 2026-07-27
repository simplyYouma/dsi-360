-- SLA propres aux modules « lents » : gouvernance, risques, audit.
--
-- Ces trois modules n'avaient pas de règles SLA à eux : ils retombaient donc sur le repli
-- codé (SLA_DEFAUT), calibré pour un incident — P1 = résolution en 4 h. Conséquence absurde :
-- une action de gouvernance P1 créée le matin voyait son échéance fixée l'après-midi même.
--
-- Un COPIL, un plan de traitement de risque, une recommandation d'audit ne se « résolvent » pas
-- en heures mais en jours et en semaines. On leur donne des cadences propres, en minutes, comme
-- pour les autres modules. Restent pleinement reparamétrables depuis l'administration.
--
-- N'impacte pas l'existant : les activités déjà créées gardent l'échéance déjà stockée jusqu'à
-- leur prochaine réévaluation d'impact/urgence. Seules les suivantes en profitent.

INSERT INTO core.sla_regle (module, priorite, prise_en_charge_minutes, resolution_minutes) VALUES
    -- Gouvernance : COPIL, décisions, engagements, plans d'actions — cadence délibérée.
    ('gouvernance', 1, 1440, 7200),   ('gouvernance', 2, 2880, 14400),
    ('gouvernance', 3, 4320, 28800),  ('gouvernance', 4, 7200, 43200),
    ('gouvernance', 5, 14400, 86400),
    -- Risques : identification puis traitement de fond, revu périodiquement.
    ('risque', 1, 1440, 14400),   ('risque', 2, 2880, 28800),
    ('risque', 3, 7200, 43200),   ('risque', 4, 14400, 86400),
    ('risque', 5, 28800, 129600),
    -- Audit & recommandations : plan d'action avec échéance de mise en œuvre.
    ('audit', 1, 2880, 21600),   ('audit', 2, 7200, 43200),
    ('audit', 3, 14400, 64800),  ('audit', 4, 28800, 86400),
    ('audit', 5, 43200, 129600)
ON CONFLICT (module, priorite) DO NOTHING;
