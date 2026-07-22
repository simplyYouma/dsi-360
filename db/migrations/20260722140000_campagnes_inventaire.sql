-- Campagnes d'inventaire (lot 3) : l'état d'un équipement n'est pas un attribut du matériel,
-- c'est le résultat d'un recensement daté. On historise donc des CONSTATS rattachés à une
-- CAMPAGNE — ce qui permet l'avancement, les non retrouvés à la clôture, et la comparaison
-- d'une année sur l'autre.

CREATE TABLE IF NOT EXISTS core.campagne_inventaire (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    libelle     text NOT NULL,
    statut      text NOT NULL DEFAULT 'OUVERTE' CHECK (statut IN ('OUVERTE', 'CLOTUREE')),
    ouverte_le  timestamptz NOT NULL DEFAULT now(),
    cloturee_le timestamptz,
    ouverte_par uuid REFERENCES core.utilisateur(id) ON DELETE SET NULL
);

-- Deux campagnes ouvertes en même temps sèmeraient la confusion : où va le constat ?
CREATE UNIQUE INDEX IF NOT EXISTS uq_campagne_ouverte
    ON core.campagne_inventaire ((statut)) WHERE statut = 'OUVERTE';

CREATE UNIQUE INDEX IF NOT EXISTS uq_campagne_libelle
    ON core.campagne_inventaire (upper(btrim(libelle)));

CREATE TABLE IF NOT EXISTS core.constat_inventaire (
    campagne_id   uuid NOT NULL REFERENCES core.campagne_inventaire(id) ON DELETE CASCADE,
    equipement_id uuid NOT NULL REFERENCES core.equipement(id) ON DELETE CASCADE,
    -- BON | REBUT | CASSE : ce que le terrain constate. NON_RETROUVE est posé à la clôture
    -- pour tout matériel actif jamais recensé — c'est le résultat le plus précieux de l'exercice.
    etat          text NOT NULL CHECK (etat IN ('BON', 'REBUT', 'CASSE', 'NON_RETROUVE')),
    constate_le   timestamptz NOT NULL DEFAULT now(),
    constate_par  uuid REFERENCES core.utilisateur(id) ON DELETE SET NULL,
    -- Un seul constat par équipement et par campagne : re-constater remplace, sans doublon.
    PRIMARY KEY (campagne_id, equipement_id)
);

CREATE INDEX IF NOT EXISTS idx_constat_equipement ON core.constat_inventaire (equipement_id);
