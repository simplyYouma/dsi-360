-- Un rappel d'échéance s'adresse à quelqu'un : le destinataire entre dans la clé.
--
-- L'échéance d'une tâche concerne son porteur, mais aussi le chef de projet (ou le gestionnaire
-- du changement) qui répond du dossier. Sans le destinataire dans la clé, le premier rappel
-- inséré consommait le palier et le second n'était jamais envoyé : une seule des deux personnes
-- était prévenue, au hasard de l'ordre de lecture.
--
-- La table est recréée plutôt qu'altérée : les lignes existantes ne portent aucun destinataire,
-- et le seul effet d'en repartir est qu'un rappel récent puisse être émis une fois de plus.
-- La fenêtre de rattrapage (7 jours) borne cet effet.

DROP TABLE IF EXISTS core.rappel_echeance;

CREATE TABLE core.rappel_echeance (
    -- sla | tache | jalon | projet | revue
    cible_type      text        NOT NULL,
    -- identifiant de l'objet porteur de l'échéance (activité, tâche ou jalon)
    cible_id        uuid        NOT NULL,
    destinataire_id uuid        NOT NULL REFERENCES core.utilisateur(id) ON DELETE CASCADE,
    echeance        timestamptz NOT NULL,
    -- avant_2 (le plus tôt) | avant_1 | jour_j
    palier          text        NOT NULL,
    envoye_le       timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (cible_type, cible_id, destinataire_id, echeance, palier)
);

-- Purge : on ne garde pas indéfiniment la trace des rappels d'échéances anciennes.
CREATE INDEX IF NOT EXISTS idx_rappel_echeance_envoye ON core.rappel_echeance (envoye_le);
