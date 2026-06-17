-- Rend le journal d'audit strictement append-only : toute modification ou suppression est bloquée.
-- (Le chaînage par empreinte rend en plus toute altération détectable.) Cf. docs/04-SECURITY §3.

CREATE OR REPLACE FUNCTION audit.interdire_modification()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Le journal d''audit est append-only : % interdit.', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_journal_pas_de_update
    BEFORE UPDATE ON audit.journal
    FOR EACH ROW EXECUTE FUNCTION audit.interdire_modification();

CREATE TRIGGER trg_journal_pas_de_delete
    BEFORE DELETE ON audit.journal
    FOR EACH ROW EXECUTE FUNCTION audit.interdire_modification();
