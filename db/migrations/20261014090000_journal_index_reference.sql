-- La numérotation des activités lit désormais le journal d'audit en plus des fiches vivantes :
-- lui seul se souvient des références supprimées, et c'est ce qui empêche d'en réattribuer une
-- (cf. `infrastructure/repositories/activite.prochaine_reference`).
--
-- Le journal n'était indexé que par horodatage. Sans celui-ci, chaque création d'activité
-- imposerait un parcours complet d'une table append-only qui ne fait que grossir : le geste le
-- plus courant des modules aurait ralenti en silence, un peu plus chaque mois.
--
-- `text_pattern_ops` est la classe d'opérateurs qu'un `LIKE 'EOD-2026-%'` sait emprunter. Avec la
-- classe par défaut — qui dépend de la collation — l'index serait simplement ignoré par ce LIKE,
-- et l'on croirait l'avoir posé.
CREATE INDEX IF NOT EXISTS idx_journal_module_cible
    ON audit.journal (module, cible_id text_pattern_ops);
