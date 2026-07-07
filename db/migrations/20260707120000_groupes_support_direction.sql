-- Groupes de support par direction : chaque direction a ses propres niveaux et membres
-- (DSI : N1/N2/N3 ; DBS : N3 uniquement). L'escalade route vers le groupe de la direction du
-- ticket ; si le niveau cible n'existe pas ou est vide dans cette direction, on monte jusqu'au N3.
-- Un ticket sans gestionnaire est considéré d'office au niveau 3.

-- La direction DBS (le libellé exact reste ajustable dans le référentiel).
INSERT INTO core.direction (code, libelle) VALUES ('DBS', 'Direction DBS')
ON CONFLICT (code) DO NOTHING;

ALTER TABLE core.groupe_support ADD COLUMN direction_id uuid REFERENCES core.direction(id);
-- Les groupes existants (globaux) deviennent ceux de la DSI.
UPDATE core.groupe_support
SET direction_id = (SELECT id FROM core.direction WHERE code = 'DSI');
ALTER TABLE core.groupe_support ALTER COLUMN direction_id SET NOT NULL;

-- Unicité par (direction, niveau) au lieu d'un seul groupe global par niveau.
ALTER TABLE core.groupe_support DROP CONSTRAINT groupe_support_niveau_key;
ALTER TABLE core.groupe_support
    ADD CONSTRAINT uq_groupe_support_direction_niveau UNIQUE (direction_id, niveau);

-- DBS : uniquement le niveau 3.
INSERT INTO core.groupe_support (niveau, nom, direction_id)
SELECT 3, 'Support niveau 3 — Référents et éditeurs', d.id
FROM core.direction d WHERE d.code = 'DBS'
ON CONFLICT ON CONSTRAINT uq_groupe_support_direction_niveau DO NOTHING;
