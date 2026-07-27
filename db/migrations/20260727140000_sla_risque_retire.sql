-- Retrait des règles SLA du module « risque », posées à tort par 20260727140000... (jour même).
--
-- Le risque ne porte pas d'échéance SLA : il n'a ni impact ni urgence (donc pas de priorité), il
-- vit sur la criticité (probabilité × impact) et la revue périodique. Les règles P1..P5 ajoutées
-- pour lui n'étaient donc jamais consultées — de la donnée morte. On la retire pour que la table
-- reflète la réalité : seuls les modules à priorité y figurent (cf. domain.sla.MODULES_SLA).

DELETE FROM core.sla_regle WHERE module = 'risque';
