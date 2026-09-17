-- EOD — « Backup before EOM » n'a plus besoin qu'on lui explique quand elle s'applique.
--
-- Son aide (« Seulement les soirs de fin de mois — "Non applicable" les autres jours ») redisait
-- ce que le verdict montre déjà : un soir ordinaire, l'étape porte la marque « Non applicable »
-- et cela suffit. Une phrase de plus sous chaque libellé, vingt-huit fois par nuit, se lit une
-- fois puis encombre.

UPDATE core.eod_modele_etape SET aide = NULL WHERE libelle = 'Backup before EOM';
UPDATE core.eod_etape SET aide = NULL WHERE libelle = 'Backup before EOM';
