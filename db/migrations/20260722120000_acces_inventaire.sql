-- Le module Inventaire s'ouvre aux profils existants.
--
-- Les accès par défaut d'un nouveau module vivent dans le seed — que la production n'exécute
-- jamais : `maj-prod` n'applique que les migrations (le seed écraserait ce que l'administrateur
-- a paramétré depuis). Résultat : après déploiement, aucun profil ne portait l'accès
-- « inventaire », et la page restait invisible pour tout le monde.
--
-- Un nouveau module se déploie donc par migration : une passe UNIQUE qui accorde l'accès par
-- défaut, puis plus jamais — si l'administrateur le retire ensuite à un profil, rien ne le
-- réintroduira. On l'accorde à tout profil déjà opérationnel (au moins un accès existant),
-- ce qui couvre les profils créés depuis l'administration comme ceux du seed.

INSERT INTO core.acces_role (profil_code, acces)
SELECT DISTINCT ar.profil_code, 'inventaire'
FROM core.acces_role ar
ON CONFLICT DO NOTHING;
