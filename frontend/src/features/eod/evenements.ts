/** Le nom de l'évènement qu'une écriture sur une soirée envoie à la fenêtre.
 *
 * La veilleuse vit dans le shell applicatif, la page de pointage dans la zone de contenu : deux
 * arbres React qui ne se croisent jamais. Plutôt qu'un magasin partagé pour un unique signal —
 * « quelque chose vient de changer sur l'EOD » — la page le crie, la veilleuse l'entend. Sans
 * cela, elle gardait son compteur en marche pendant les quarante-cinq secondes qui la séparaient
 * de son prochain rafraîchissement, sur une étape déjà close.
 */
export const EVENEMENT_EOD = 'dsi360:eod-maj';
