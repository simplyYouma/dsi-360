-- L'import quotidien devient un accès module comme un autre (« import »), visible dans la
-- matrice de l'administration — il était jusqu'ici réservé aux profils transverses, donc
-- invisible et non distribuable.
--
-- Migration one-shot, PAS le seed : maj-prod ne rejoue jamais le seed, et le seed écraserait le
-- paramétrage fait par l'administrateur (même règle qu'à l'arrivée du module inventaire).
-- On l'accorde à tout profil existant : c'est l'état que ces profils connaissaient de fait via
-- le statut transverse, et l'administrateur peut le retirer ensuite depuis la matrice.

INSERT INTO core.acces_role (profil_code, acces)
SELECT DISTINCT ar.profil_code, 'import'
FROM core.acces_role ar
ON CONFLICT DO NOTHING;
