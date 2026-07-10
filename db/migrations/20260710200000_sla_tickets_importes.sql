-- Échéances SLA des tickets déjà importés (ADR-0005 §6).
--
-- L'import ne les calculait pas : la fiche affichait « Échéance — » alors que le ticket portait une
-- priorité, donc un engagement. Le calcul est désormais fait à l'import, mais un ticket que le
-- rapport ne fait plus bouger ne serait jamais réécrit. On rattrape ici l'existant, une fois.
--
-- La règle vient de core.sla_regle (module, priorité). Un ticket sans priorité, sans date de
-- création, ou dont la priorité n'a pas de règle, reste sans échéance : on n'invente pas un
-- engagement qui n'a pas été pris.

UPDATE core.activite a
SET sla_prise_en_charge_le = a.cree_le + make_interval(mins => r.prise_en_charge_minutes),
    sla_resolution_le      = a.cree_le + make_interval(mins => r.resolution_minutes)
FROM core.sla_regle r
WHERE r.module = a.module
  AND r.priorite = a.priorite
  AND a.source = 'IMPORT_SD'
  AND a.cree_le IS NOT NULL
  AND a.sla_resolution_le IS NULL;
