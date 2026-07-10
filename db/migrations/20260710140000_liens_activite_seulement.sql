-- Les liens utiles remontent au niveau de l'activité : une tâche n'a plus les siens.
--
-- Un lien (espace documentaire, wiki, dossier réseau) sert le sujet, pas une étape de sa
-- réalisation. Les éparpiller sur les tâches les rendait introuvables une fois la tâche terminée.
--
-- Zéro perte : les liens de tâche rejoignent leur activité, préfixés du titre de la tâche pour
-- qu'on sache d'où ils viennent. Puis la colonne disparaît.

UPDATE core.lien l
SET libelle = left(t.titre || ' — ' || l.libelle, 200),
    tache_id = NULL
FROM core.tache t
WHERE l.tache_id = t.id;

-- Filet : une tâche supprimée entre-temps aurait laissé un lien orphelin (la contrainte est
-- ON DELETE CASCADE, donc improbable) — on le rattache quand même à son activité.
UPDATE core.lien SET tache_id = NULL WHERE tache_id IS NOT NULL;

ALTER TABLE core.lien DROP COLUMN tache_id;
