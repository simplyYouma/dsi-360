-- Rappel d'échéance de jalon : horodate l'envoi du rappel pour ne notifier qu'une seule fois par
-- jalon (l'ordonnanceur scanne les jalons non atteints dont l'échéance approche). Cf. ADR-0002.
ALTER TABLE core.jalon ADD COLUMN rappel_le timestamptz;
