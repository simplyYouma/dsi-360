-- Détenteur hors système : tout le matériel n'est pas détenu par un agent de la DSI.
--
-- Un GAB est « détenu » par une agence, un poste par un prestataire, un matériel prêté par une
-- personne sans compte. Jusqu'ici la fiche n'acceptait qu'un compte : ces cas restaient « non
-- attribué », et le parc paraissait moins suivi qu'il ne l'est.
--
-- On garde les deux chemins distincts : `detenteur_id` quand c'est un compte (le nom suit
-- l'annuaire, on peut demander « quel matériel détient X ? »), `detenteur_externe` quand c'est
-- un nom libre. Jamais les deux à la fois — un détenteur, c'est une personne, pas deux.

ALTER TABLE core.equipement ADD COLUMN IF NOT EXISTS detenteur_externe text;

COMMENT ON COLUMN core.equipement.detenteur_externe IS
    'Détenteur sans compte dans DSI 360 (agence, prestataire, personne extérieure), saisi '
    'librement. Exclusif avec detenteur_id.';

ALTER TABLE core.equipement DROP CONSTRAINT IF EXISTS equipement_un_seul_detenteur;
ALTER TABLE core.equipement ADD CONSTRAINT equipement_un_seul_detenteur
    CHECK (detenteur_id IS NULL OR detenteur_externe IS NULL);
