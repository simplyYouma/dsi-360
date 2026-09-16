-- EOD — les observations d'une étape s'historisent au lieu de s'écraser.
--
-- L'étape portait une colonne `notes` : un texte libre, réécrit à chaque saisie. Or une soirée ne
-- se raconte pas en une phrase. Sur « PART 3 — EOD till Post MARKBOD for all branches », une
-- agence bloque à 01H12, on relance ; une autre bloque à 01H40, on relance encore. Chaque geste
-- écrasait le précédent : au matin, il restait la dernière phrase tapée, sans heure, sans auteur,
-- sans l'agence. Personne ne pouvait plus dire ce qui s'était passé, ni combien de temps la
-- banque avait attendu.
--
-- Une observation devient donc une ligne de journal : horodatée, signée, définitive. Et quand
-- c'est un incident d'agence, elle porte les trois informations que la hiérarchie réclame —
-- **quelle agence**, **à quelle heure on a relancé**, **ce qui a été fait**. La contrainte le
-- garantit en base : espérer ces trois champs depuis le code seulement, c'est les voir manquer
-- la nuit où ils comptent.

CREATE TABLE core.eod_observation (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    etape_id     uuid NOT NULL REFERENCES core.eod_etape(id) ON DELETE CASCADE,
    -- Redondant avec `etape_id`, et volontairement : le détail d'une soirée charge le journal de
    -- ses vingt-huit étapes d'un coup, et la liste compte les relances de quinze nuits. Repasser
    -- par la jointure à chaque fois ferait payer ce confort à toutes les lectures.
    activite_id  uuid NOT NULL REFERENCES core.activite(id) ON DELETE CASCADE,
    -- « note » : ce qu'on relève en passant. « incident » : une agence a bloqué, on l'a relancée.
    -- Deux natures et non un booléen : le rapport, les compteurs et le formulaire s'y accrochent.
    nature       text NOT NULL DEFAULT 'note' CHECK (nature IN ('note', 'incident')),
    -- Texte libre et non référence vers core.emplacement : le core banking désigne ses agences
    -- par des codes qui lui sont propres (« 000 BAM », « 000 BHO ») et que le référentiel du parc
    -- ne connaît pas. L'écran propose malgré tout la liste des agences de la banque, pour que la
    -- saisie converge — proposer n'est pas imposer.
    agence       text,
    -- Horodatage complet et non une simple heure : l'EOD franchit minuit, c'est son objet même.
    -- « 01H12 » sans le jour ne se compare à rien.
    relance_le   timestamptz,
    texte        text NOT NULL,
    auteur_id    uuid REFERENCES core.utilisateur(id),
    auteur_email text NOT NULL,                 -- figé à l'écriture (survit à la suppression du compte)
    -- `clock_timestamp()` et non `now()` : `now()` rend l'heure d'OUVERTURE de la transaction,
    -- identique pour deux lignes écrites dans la même. Le journal se lit dans l'ordre où la nuit
    -- s'est vécue — deux observations ex æquo se rangeraient au hasard, et le récit se mélangerait.
    cree_le      timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT ck_eod_observation_texte CHECK (btrim(texte) <> ''),
    CONSTRAINT ck_eod_observation_incident CHECK (
        nature <> 'incident'
        OR (agence IS NOT NULL AND btrim(agence) <> '' AND relance_le IS NOT NULL)
    )
);
CREATE INDEX idx_eod_observation_etape ON core.eod_observation (etape_id, cree_le);
CREATE INDEX idx_eod_observation_activite ON core.eod_observation (activite_id, cree_le);

COMMENT ON TABLE core.eod_observation IS
    'Journal append-only des observations d''une étape EOD. Une observation de nature '
    '« incident » porte l''agence, l''heure de relance et ce qui a été fait.';

-- Ce qui était déjà écrit devient la première ligne du journal : on déplace, on ne perd rien.
-- L'auteur est inconnu (la colonne n'en gardait aucun) et l'heure est celle de la dernière
-- retouche de l'étape — c'est tout ce que l'ancienne forme savait dire.
INSERT INTO core.eod_observation (etape_id, activite_id, nature, texte, auteur_email, cree_le)
SELECT e.id, e.activite_id, 'note', btrim(e.notes), 'import@dsi360', coalesce(e.maj_le, e.cree_le)
FROM core.eod_etape e
WHERE e.notes IS NOT NULL AND btrim(e.notes) <> '';

-- La colonne disparaît : la laisser en place donnerait deux endroits où écrire la même chose, et
-- l'un des deux finirait par mentir.
ALTER TABLE core.eod_etape DROP COLUMN notes;
