-- Rappels d'échéance déjà envoyés : un palier n'est notifié qu'une fois.
--
-- Jusqu'ici chaque type d'échéance avait son propre garde-fou : un index unique pour le SLA, un
-- marqueur `revue_notifiee_le` dans les données du risque, une colonne `rappel_le` sur le jalon.
-- Trois mécanismes pour une seule règle, et rien du tout pour les tâches ni les fins de projet.
--
-- Cette table les remplace tous. La DATE D'ÉCHÉANCE fait partie de la clé : si l'échéance est
-- repoussée, les rappels repartent de zéro sur la nouvelle date — c'est le comportement voulu.
-- Elle traite du même coup les revues périodiques (chaque nouvelle date porte ses rappels) et
-- les tâches (plusieurs par activité, chacune la sienne).

CREATE TABLE IF NOT EXISTS core.rappel_echeance (
    -- sla | tache | jalon | projet | revue
    cible_type text        NOT NULL,
    -- identifiant de l'objet porteur de l'échéance (activité, tâche ou jalon)
    cible_id   uuid        NOT NULL,
    echeance   timestamptz NOT NULL,
    -- avant_2 (le plus tôt) | avant_1 | jour_j
    palier     text        NOT NULL,
    envoye_le  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (cible_type, cible_id, echeance, palier)
);

-- Purge : on ne garde pas indéfiniment la trace des rappels d'échéances anciennes.
CREATE INDEX IF NOT EXISTS idx_rappel_echeance_envoye ON core.rappel_echeance (envoye_le);

-- L'ancien garde-fou SLA devient nuisible : il n'autorisait QU'UNE notification « SLA_APPROCHE »
-- par activité, ce qui ferait échouer le deuxième rappel (50 % puis 80 % du délai). C'est
-- désormais `rappel_echeance` qui garantit l'unicité, palier par palier.
DROP INDEX IF EXISTS core.uq_notification_sla;
