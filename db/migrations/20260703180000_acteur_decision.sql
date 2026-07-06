-- Décision d'un valideur sur une activité (approbation ITIL : CAB/ECAB, demandes à valider).
-- Portée par l'acteur (core.activite_acteur) : NULL = en attente, APPROUVE / REJETE sinon.
ALTER TABLE core.activite_acteur
    ADD COLUMN decision text CHECK (decision IN ('APPROUVE', 'REJETE')),
    ADD COLUMN decide_le timestamptz;
