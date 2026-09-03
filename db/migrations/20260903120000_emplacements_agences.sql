-- Emplacements de départ : le réseau d'agences d'AFG Bank Mali.
--
-- Le référentiel des emplacements se remplissait jusqu'ici tout seul, au fil des imports : chaque
-- orthographe rencontrée créait une entrée, et « AGENCE KAYES », « Agence 11 Kayes » et « Kayes »
-- finissaient par coexister. On pose donc la liste officielle une bonne fois, pour que le modèle
-- d'import la propose et que la saisie converge vers un nom unique par site.
--
-- Idempotent : l'unicité est insensible à la casse et aux espaces, un emplacement déjà présent
-- sous le même nom est laissé tel quel. Les libellés déjà saisis autrement ne sont pas touchés —
-- les fusionner relève de l'écran d'administration, pas d'une migration qui déciderait à la place
-- de la DSI quel équipement va où.

INSERT INTO core.emplacement (libelle) VALUES
    ('Agence 02 Prestige'),
    ('Agence 03 Fleuve'),
    ('Agence 04 ZI'),
    ('Agence 05 Suguba'),
    ('Agence 06 Dabanani'),
    ('Agence 07 Médine'),
    ('Agence 08 Titibougou'),
    ('Agence 09 Yirimadio'),
    ('Agence 10 GMM'),
    ('Agence 11 Kayes'),
    ('Agence 12 Badala'),
    ('Agence 14 Sebenikoro'),
    ('Agence 15 Segou'),
    ('Agence 16 Fourou'),
    ('Agence 17 Sikasso'),
    ('Agence 18 Bougouni'),
    ('Caisse Centrale Siège'),
    ('Siège')
ON CONFLICT DO NOTHING;
