-- Le niveau de support d'un ticket importé se déduit de son gestionnaire (cf. docs/adr/0005).
--
-- Il n'est plus une décision prise dans la plateforme : le gestionnaire vient du fichier importé,
-- et le niveau en découle. Rapproché d'un compte DSI, le ticket est à son niveau (N1 ou N2) ;
-- sinon c'est DBS, et le ticket est au niveau 3.
--
-- Les clés `niveau_support` et `transfere_dbs` que l'escalade manuelle écrivait dans `donnees`
-- n'ont plus de lecteur : elles mentiraient. On les retire.
--
-- Elles étaient d'ailleurs déjà fragiles : l'import remplace intégralement le bloc `donnees`, donc
-- un import survenant après une escalade les effaçait sans bruit.

-- `jsonb_exists` plutôt que l'opérateur `?` : les migrations passent par le protocole simple
-- d'asyncpg, où un point d'interrogation prête à confusion.
UPDATE core.activite
SET donnees = donnees - 'niveau_support' - 'transfere_dbs'
WHERE jsonb_exists(donnees, 'niveau_support') OR jsonb_exists(donnees, 'transfere_dbs');
