-- Référence système de l'équipement : « INV-00001 », générée par la plateforme.
--
-- À ne pas confondre avec le code d'immobilisation (code_immo), qui vient de la comptabilité et se
-- saisit à la main ou par l'import. La référence, elle, est interne, attribuée automatiquement à
-- chaque création (saisie ou import) et jamais saisie — un identifiant stable, propre à DSI 360.

CREATE SEQUENCE IF NOT EXISTS core.equipement_reference_seq;

ALTER TABLE core.equipement ADD COLUMN IF NOT EXISTS reference text;

-- Backfill du parc existant, dans l'ordre d'entrée (plus ancien = plus petit numéro).
WITH ordonnes AS (
    SELECT id, row_number() OVER (ORDER BY cree_le, id) AS n FROM core.equipement
)
UPDATE core.equipement e
SET reference = 'INV-' || lpad(o.n::text, 5, '0')
FROM ordonnes o
WHERE o.id = e.id AND e.reference IS NULL;

-- La séquence reprend après le dernier numéro attribué.
SELECT setval(
    'core.equipement_reference_seq',
    greatest((SELECT count(*) FROM core.equipement), 1)
);

-- Toute insertion future reçoit sa référence d'office (saisie, import, démo — sans code applicatif).
ALTER TABLE core.equipement
    ALTER COLUMN reference
    SET DEFAULT 'INV-' || lpad(nextval('core.equipement_reference_seq')::text, 5, '0');
ALTER TABLE core.equipement ALTER COLUMN reference SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_equipement_reference ON core.equipement (reference);
