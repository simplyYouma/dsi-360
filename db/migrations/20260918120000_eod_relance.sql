-- EOD — une relance d'agence est une ÉTAPE du déroulé, pas une note en marge.
--
-- Le rapport réel le montre sans ambiguïté : sous « Post EOFI_1 for all branch » en anomalie
-- (agence 018, erreur AE-VALS-053), la ligne suivante est « RELANCE | 20H15 | 20H20 | Complete ».
-- La relance a son propre début, sa propre fin, son propre verdict — on l'a rejouée et pointée
-- comme n'importe quelle étape. Nous l'avions réduite à une observation (une agence, une heure,
-- un texte) : on savait qu'elle avait eu lieu et quand elle avait démarré, jamais combien de temps
-- elle avait pris ni comment elle s'était terminée. Cinq minutes de travail réel sans trace.
--
-- Une relance devient donc une étape ordinaire, rattachée à l'étape qu'elle rejoue : même section,
-- même rang (elle se range juste après), pointée avec les mêmes gestes, comptée dans le même
-- avancement, exportée sur la même ligne de rapport. Rien de nouveau à apprendre à l'opérateur.
-- L'observation « incident » reste ce qu'elle est — la trace signée de ce qui a été fait — et
-- c'est elle qui, à sa création, pose la ligne RELANCE.

ALTER TABLE core.eod_etape
    ADD COLUMN IF NOT EXISTS relance_de uuid REFERENCES core.eod_etape(id) ON DELETE CASCADE,
    -- L'agence relancée, en clair sur l'étape : le libellé la porte déjà, mais un libellé se
    -- retouche et ne se compte pas.
    ADD COLUMN IF NOT EXISTS agence text;

CREATE INDEX IF NOT EXISTS idx_eod_etape_relance
    ON core.eod_etape (relance_de) WHERE relance_de IS NOT NULL;

COMMENT ON COLUMN core.eod_etape.relance_de IS
    'L''étape que celle-ci rejoue (une relance d''agence). NULL pour une étape du déroulé.';
