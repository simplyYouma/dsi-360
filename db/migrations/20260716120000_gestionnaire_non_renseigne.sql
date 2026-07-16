-- Les fichiers importés écrivent souvent l'absence de gestionnaire en toutes lettres :
-- « None », « N/A », « - », « inconnu »… Ce ne sont pas des noms. Tant qu'ils sont pris pour
-- des noms, le ticket passe pour traité par quelqu'un et se retrouve compté chez DBS (N3),
-- alors que personne n'a été désigné.
--
-- On efface donc ces fausses valeurs : la clé `gestionnaire` disparaît des données du ticket,
-- qui devient « non renseigné » — ni chez nous, ni chez DBS. L'import normalise désormais à la
-- source (domain/texte.nom_significatif) ; un import ultérieur qui renseigne le vrai nom
-- corrigera le ticket de lui-même.
--
-- Rien n'est perdu : ces valeurs ne portaient aucune information.

UPDATE core.activite
SET donnees = donnees - 'gestionnaire'
WHERE source = 'IMPORT_SD'
  AND donnees ? 'gestionnaire'
  AND lower(
        translate(
          btrim(donnees->>'gestionnaire'),
          'àâäéèêëîïôöùûüçÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ',
          'aaaeeeeiioouuucAAAEEEEIIOOUUUC'
        )
      ) IN (
        '', '-', '--', '?', '0', 'inconnu', 'n/a', 'na', 'nan', 'nil',
        'non affecte', 'non assigne', 'non renseigne', 'non renseignee',
        'none', 'null', 'sans', 'sans objet', 'unknown', 'vide'
      );
