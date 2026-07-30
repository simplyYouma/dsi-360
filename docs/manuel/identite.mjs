/**
 * Identité du manuel — le seul endroit à toucher pour décliner le document.
 *
 * Le corps du manuel ne nomme jamais un métier, un secteur ni une entreprise :
 * il parle d'« organisation », d'« entité », d'« activités ». Servir un autre
 * déploiement ne demande donc que de changer ces quelques lignes — pas de
 * relire le texte.
 */
export const IDENTITE = {
    produit: 'DSI 360',
    titreManuel: 'Manuel de la plateforme',
    fichier: 'MANUEL.html',
    version: '1.0',
    edition: 'Première édition',
    diffusion: 'Interne',

    titreCouverture:
        'Piloter et gouverner<br>les activités<br>d\'une organisation.',
    sousTitre:
        'Manuel complet de la plateforme : concepts, prise en main, modules, '
        + 'administration, sécurité et exploitation. Destiné aux utilisateurs, '
        + 'aux administrateurs fonctionnels et aux équipes techniques.',

    /* Tokens repris du design system de l'application
       (frontend/src/design-system) : le manuel ressemble au produit. */
    accent: '#16181d',
    accentDoux: '#f0f1f3',
    secondaire: '#7fc81f',
};
