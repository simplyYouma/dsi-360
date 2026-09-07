-- Risques et impacts d'un sujet de gouvernance : des LISTES, plus un pavé de texte.
--
-- Un sujet de COPIL porte rarement UN risque : il en porte trois ou quatre, distincts, qu'on ajoute
-- au fil des comités. Les écrire dans un seul champ obligeait à les séparer soi-même, à la virgule
-- ou au tiret, et rendait impossible d'en retirer un sans réécrire le reste. On ne saurait pas non
-- plus combien il y en a.
--
-- Le stockage reste `donnees` (jsonb) : c'est un champ de module, comme les analyses RFC d'un
-- changement. Seule la forme change — de `"texte"` à `["texte", "autre"]`.
--
-- Idempotent, et prudent : on ne convertit que ce qui est encore une CHAÎNE. Rejouer la migration
-- sur une base déjà convertie ne toucherait à rien, et une valeur vide devient une liste vide
-- plutôt qu'une liste contenant du vide.

UPDATE core.activite
   SET donnees = donnees || jsonb_build_object(
           'risques',
           CASE WHEN btrim(donnees->>'risques') = '' THEN '[]'::jsonb
                ELSE jsonb_build_array(donnees->>'risques') END
       )
 WHERE module = 'gouvernance'
   AND jsonb_typeof(donnees->'risques') = 'string';

UPDATE core.activite
   SET donnees = donnees || jsonb_build_object(
           'impacts',
           CASE WHEN btrim(donnees->>'impacts') = '' THEN '[]'::jsonb
                ELSE jsonb_build_array(donnees->>'impacts') END
       )
 WHERE module = 'gouvernance'
   AND jsonb_typeof(donnees->'impacts') = 'string';
