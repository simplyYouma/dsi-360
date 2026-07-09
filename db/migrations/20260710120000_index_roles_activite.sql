-- Rôles d'un utilisateur sur une activité : la garde les lit à chaque requête (application/
-- autorisations.charger_roles). Les clés primaires existantes commencent par activite_id, ce qui ne
-- sert pas la recherche « suis-je acteur ? » quand on part de l'utilisateur.

CREATE INDEX IF NOT EXISTS idx_activite_acteur_utilisateur
    ON core.activite_acteur (utilisateur_id);

CREATE INDEX IF NOT EXISTS idx_tache_assigne
    ON core.tache (assigne_id) WHERE assigne_id IS NOT NULL;
