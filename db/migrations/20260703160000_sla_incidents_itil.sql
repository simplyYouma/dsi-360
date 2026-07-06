-- Aligne les délais de RÉSOLUTION des incidents sur la procédure ITIL SI-12.01 :
-- P1 = 2 h, P2 = 4 h, P3 = 8 h, P4 = 48 h, P5 = 72 h. La prise en charge (démarrage) reste
-- celle du cahier (non spécifiée par la procédure incidents). Reste paramétrable depuis l'admin.
UPDATE core.sla_regle SET resolution_minutes = 120,  maj_le = now() WHERE module='incident' AND priorite=1;
UPDATE core.sla_regle SET resolution_minutes = 240,  maj_le = now() WHERE module='incident' AND priorite=2;
UPDATE core.sla_regle SET resolution_minutes = 480,  maj_le = now() WHERE module='incident' AND priorite=3;
UPDATE core.sla_regle SET resolution_minutes = 2880, maj_le = now() WHERE module='incident' AND priorite=4;
UPDATE core.sla_regle SET resolution_minutes = 4320, maj_le = now() WHERE module='incident' AND priorite=5;
