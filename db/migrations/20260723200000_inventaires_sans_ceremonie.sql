-- L'inventaire physique se lance, il ne s'« ouvre » ni ne se « clôture ».
--
-- Le cahier ne demandait qu'une chose : relever l'état du parc. La machinerie d'ouverture et de
-- clôture (une seule campagne à la fois, verrou des constats, non-retrouvés posés d'office) était
-- une couche de cérémonie au-dessus du besoin. On la retire : on crée un inventaire, on y pose
-- ses constats, et l'on garde les précédents pour comparer.
--
-- Ce que devient l'ancien verrou : l'index qui n'autorisait qu'une campagne ouverte interdirait
-- d'en créer une seconde dès lors que plus rien ne se clôture. Il saute.

DROP INDEX IF EXISTS core.uq_campagne_ouverte;

-- `statut` n'a plus de rôle dans les règles ; il reste pour lire l'historique des campagnes
-- déjà clôturées, et le plus récent inventaire est simplement celui du haut de la liste.
COMMENT ON COLUMN core.campagne_inventaire.statut IS
    'Héritage : les campagnes closes avant la simplification portent CLOTUREE. Aucune règle ne '
    's''y appuie plus — un inventaire se crée, se remplit, et cohabite avec les précédents.';
