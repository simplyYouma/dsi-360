-- EOD — le type d'une soirée se nomme comme le core banking le nomme.
--
-- « EOD quotidien » et « EOD de fin de mois » étaient des périphrases : l'opérateur, lui, lit
-- EOD, EOM, EOY sur ses écrans et dans ses procédures. Une étiquette qu'il faut traduire de tête à
-- 2 h du matin n'aide personne — et la colonne « Type » de la liste devenait deux fois plus large
-- que son contenu utile.
--
-- Seuls les LIBELLÉS changent : les codes restent, donc les soirées déjà enregistrées gardent leur
-- type sans qu'une seule ligne d'activité soit touchée.

UPDATE core.categorie SET libelle = 'EOD' WHERE module = 'eod' AND code = 'QUOTIDIEN';
UPDATE core.categorie SET libelle = 'EOM' WHERE module = 'eod' AND code = 'FIN_DE_MOIS';

-- La fin d'année manquait. Elle ne se déduit pas de la fin de mois : le 31 décembre porte les
-- traitements annuels EN PLUS des mensuels, et c'est la nuit la plus longue de l'année — la
-- confondre avec un EOM ordinaire effacerait justement ce qu'on veut pouvoir relire.
INSERT INTO core.categorie (module, code, libelle) VALUES
    ('eod', 'FIN_ANNEE', 'EOY')
ON CONFLICT (module, code) DO NOTHING;
