-- EOD — le traitement de fin de journée du core banking, suivi dans DSI 360.
--
-- Jusqu'ici, la soirée se pointait dans un tableau recopié chaque nuit, puis envoyé par courriel.
-- Rien n'en restait d'exploitable : impossible de dire combien de nuits ont dérapé ce trimestre,
-- à quelle heure l'EODM démarre en moyenne, ni quelle étape retarde les autres.
--
-- Deux tables, sur le modèle éprouvé des jalons de projet (cf. 20260724090000_type_projet.sql) :
--   * core.eod_modele_etape : le déroulé de référence, paramétrable ;
--   * core.eod_etape        : les étapes réelles d'une soirée, recopiées du modèle à sa création.
-- Une fois posées, les étapes appartiennent à la soirée : corriger le modèle ne réécrit jamais
-- une nuit passée.
--
-- La soirée elle-même est une activité ordinaire (module « eod ») : elle hérite donc de la fiche,
-- de la discussion, des pièces jointes, du journal d'audit et des indicateurs, sans rien dupliquer.

-- 1. Le déroulé de référence -------------------------------------------------------------------
CREATE TABLE core.eod_modele_etape (
    id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    section text NOT NULL,
    libelle text NOT NULL,
    -- « horaire » : on pointe un début et une fin. « valeur » : on relève ce qui est affiché
    -- (la date système), seule information que l'étape porte.
    nature  text NOT NULL DEFAULT 'horaire' CHECK (nature IN ('horaire', 'valeur')),
    aide    text,
    ordre   integer NOT NULL DEFAULT 0,
    actif   boolean NOT NULL DEFAULT true,
    cree_le timestamptz NOT NULL DEFAULT now(),
    -- « System Date » figure deux fois, avant et après la bascule : c'est la section qui les
    -- distingue. L'unicité porte donc sur le couple, jamais sur le libellé seul.
    UNIQUE (section, libelle)
);
CREATE INDEX idx_eod_modele_ordre ON core.eod_modele_etape (ordre);

COMMENT ON TABLE core.eod_modele_etape IS
    'Déroulé de référence de l''EOD, recopié en étapes à la création de chaque soirée.';

-- 2. Les étapes d'une soirée -------------------------------------------------------------------
CREATE TABLE core.eod_etape (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    activite_id uuid NOT NULL REFERENCES core.activite(id) ON DELETE CASCADE,
    section     text NOT NULL,
    libelle     text NOT NULL,
    nature      text NOT NULL DEFAULT 'horaire' CHECK (nature IN ('horaire', 'valeur')),
    aide        text,
    ordre       integer NOT NULL DEFAULT 0,
    statut      text NOT NULL DEFAULT 'À faire'
                CHECK (statut IN ('À faire', 'En cours', 'Complété', 'Anomalie', 'Non applicable')),
    -- Horodatages complets et non de simples heures : l'EOD franchit minuit (la bascule de date
    -- est son objet même). « 00H12 » sans le jour ne se compare à rien.
    debut       timestamptz,
    fin         timestamptz,
    -- Ce qu'affichait l'écran, pour les étapes de nature « valeur » (date système relevée).
    valeur      text,
    notes       text,
    cree_le     timestamptz NOT NULL DEFAULT now(),
    maj_le      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_eod_etape_activite ON core.eod_etape (activite_id, ordre);

COMMENT ON TABLE core.eod_etape IS
    'Étapes pointées d''une soirée EOD (début, fin, verdict, observations).';

-- 3. Une seule soirée par date d'exploitation ---------------------------------------------------
--
-- La date de la journée comptable close vit dans `donnees->>'journee'` : c'est un champ propre au
-- module, il n'a pas à ajouter une colonne au socle commun (cf. core.activite.donnees). L'index
-- partiel lui donne malgré tout la garantie qui compte — deux rapports pour la même nuit seraient
-- une erreur de saisie, jamais une intention.
CREATE UNIQUE INDEX uq_eod_journee
    ON core.activite ((donnees ->> 'journee'))
    WHERE module = 'eod';

-- 4. Vocabulaire du module ----------------------------------------------------------------------
INSERT INTO core.categorie (module, code, libelle) VALUES
    ('eod', 'QUOTIDIEN',   'EOD quotidien'),
    ('eod', 'FIN_DE_MOIS', 'EOD de fin de mois')
ON CONFLICT (module, code) DO NOTHING;

-- 5. Cadence SLA --------------------------------------------------------------------------------
--
-- Sans règle propre, l'EOD retomberait sur le repli codé, calibré pour un incident. Or la soirée
-- se mesure en heures, pas en jours : la banque doit rouvrir avant l'ouverture des agences. Les
-- valeurs sont en minutes, et restent reparamétrables depuis l'administration.
INSERT INTO core.sla_regle (module, priorite, prise_en_charge_minutes, resolution_minutes) VALUES
    ('eod', 1, 15, 300),   -- soirée critique (fin de mois, arrêté) : close en 5 h
    ('eod', 2, 30, 420),
    ('eod', 3, 60, 600),   -- soirée ordinaire : close dans la nuit
    ('eod', 4, 120, 720),
    ('eod', 5, 240, 900)
ON CONFLICT (module, priorite) DO NOTHING;

-- 6. Accès --------------------------------------------------------------------------------------
--
-- Distribué à tous les profils qui ont déjà un accès, comme pour l'inventaire et les applications :
-- l'administration restreint ensuite si la DSI veut réserver l'écran à la Production. Ouvrir puis
-- restreindre se corrige d'un clic ; fermer par défaut se solde par des appels au support.
INSERT INTO core.acces_role (profil_code, acces)
SELECT DISTINCT ar.profil_code, 'eod'
FROM core.acces_role ar
ON CONFLICT DO NOTHING;

-- 7. Le déroulé réellement suivi à AFG Bank Mali ------------------------------------------------
--
-- Relevé sur le rapport EOD du 15/09/2026. L'ordre est celui de l'exécution : chaque étape suppose
-- la précédente faite. Les libellés restent ceux des écrans du core banking — les traduire
-- obligerait l'opérateur à faire la correspondance de tête, la nuit, sous contrainte.
INSERT INTO core.eod_modele_etape (section, libelle, nature, aide, ordre) VALUES
    ('Préparation', 'Intégration fichier CARTHAGO',            'horaire', NULL, 1),
    ('Préparation', 'Check Pending Transactions',              'horaire', NULL, 2),
    ('Préparation', 'Backup before EOD',                       'horaire', NULL, 3),
    ('Préparation', 'Backup before EOM',                       'horaire',
        'Seulement les soirs de fin de mois — « Non applicable » les autres jours.', 4),
    ('Préparation', 'Stop Bank To Wallet',                     'horaire', NULL, 5),
    ('Préparation', 'Date Check',                              'horaire', NULL, 6),
    ('Préparation', 'System Date',                             'valeur',
        'Date système AVANT la bascule : la journée comptable qu''on s''apprête à clore.', 7),
    ('Préparation', 'EODM',                                    'horaire', NULL, 8),
    ('Préparation', 'Check Batch CSSJOBBR --- AC-DAHOFF',      'horaire', NULL, 9),
    ('Préparation', 'Check Batch SMSJOBBR --- BRNSCH',         'horaire', NULL, 10),
    ('PART 1', 'Post EOFI_1 for all branch including 000 BAM', 'horaire', NULL, 11),
    ('PART 2', 'EOD till Post EOFI_3 for branch 000 BHO',      'horaire', NULL, 12),
    ('PART 3', 'EOD till Post MARKBOD for all branches',       'horaire', NULL, 13),
    ('PART 4', 'EOD till last stage for all branches POSTEOPD3', 'horaire', NULL, 14),
    ('Tâches additionnelles', 'Date Checking',                 'horaire', NULL, 15),
    ('Tâches additionnelles', 'Batch Check : EMS_IN, EMS_OUT, EMS_OUT_PM', 'horaire', NULL, 16),
    ('Tâches additionnelles', 'Batch Check : EXT_ASYNCCALL, NOTIF', 'horaire', NULL, 17),
    ('Tâches additionnelles', 'AC-DAHOFF',                     'horaire', NULL, 18),
    ('Tâches additionnelles', 'BALANCE REPORT',                'horaire', NULL, 19),
    ('Tâches additionnelles', 'INTERIM STATEMENT',             'horaire', NULL, 20),
    ('Tâches additionnelles', 'SWIFT_UPLOAD',                  'horaire', NULL, 21),
    ('Tâches additionnelles', 'FETCHINCOMINGMESSAGES',         'horaire', NULL, 22),
    ('Tâches additionnelles', 'PR_BG_GEN_MSG_OUT',             'horaire', NULL, 23),
    ('Tâches additionnelles', 'BRNRPLI',                       'horaire', NULL, 24),
    ('Tâches additionnelles', 'PMSAJBPR',                      'horaire', NULL, 25),
    ('Tâches additionnelles', 'System Date',                   'valeur',
        'Date système APRÈS la bascule : elle doit afficher le jour suivant.', 26),
    ('Tâches additionnelles', 'Bank To Wallet Activation',     'horaire', NULL, 27),
    ('Tâches additionnelles', 'Backup After EOD',              'horaire', NULL, 28)
ON CONFLICT (section, libelle) DO NOTHING;
