-- EOD — une soirée annulée ne réserve plus sa journée comptable.
--
-- L'unicité portait sur toutes les soirées du module : une fois la nuit du 15/09 ouverte, elle
-- occupait cette date pour toujours. Or « Annulé » dit précisément que **la soirée n'a pas eu
-- lieu** — maintenance, arrêt décidé, ouverture sur la mauvaise date. Elle ne compte dans aucun
-- taux (phase `abandonne`), mais elle interdisait de repointer la nuit quand l'EOD finissait par
-- tourner. Il fallait alors supprimer la soirée annulée pour récupérer sa date : on effaçait
-- l'histoire pour contourner un index.
--
-- Deux choses deviennent donc vraies ensemble : la trace de l'annulation reste (avec sa note de
-- justification, son journal d'audit, ses étapes), et la journée redevient ouvrable.
--
-- La garantie qui comptait ne faiblit pas : il reste au plus **une soirée vivante** par journée
-- comptable. C'est ce que dit le prédicat — et c'est sûr, parce que « Annulé » est un état
-- **terminal** du cycle EOD (`domain/etats.py` : aucune suite). Une soirée annulée ne peut pas
-- revenir à la vie et entrer en collision avec celle qui l'a remplacée ; si on lui ouvrait un
-- jour une porte de retour, cet index devrait être revu — et un test le rappellera
-- (`test_eod.py::test_l_index_d_unicite_suit_la_definition_du_domaine`).

DROP INDEX IF EXISTS core.uq_eod_journee;

CREATE UNIQUE INDEX uq_eod_journee
    ON core.activite ((donnees ->> 'journee'))
    WHERE module = 'eod' AND statut <> 'Annulé';

COMMENT ON INDEX core.uq_eod_journee IS
    'Au plus une soirée EOD VIVANTE par journée comptable. Les soirées annulées sont hors '
    'contrainte : elles n''ont pas eu lieu, et leur date doit pouvoir être repointée.';
