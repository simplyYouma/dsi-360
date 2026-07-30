/**
 * Identité du dossier de présentation — le seul endroit à toucher pour le
 * décliner.
 *
 * Le corps du dossier ne nomme ni métier, ni secteur, ni entreprise : il
 * parle d'organisation, de direction, d'entité, d'activités. Servir un autre
 * déploiement ne demande donc que ces quelques lignes — pas de relire le texte.
 */
export const IDENTITE = {
    name: 'DSI 360',
    tagline: 'Pilotage et gouvernance des activités',
    fichier: 'PRESENTATION.html',

    /** Le logo réel, en couleur (aile verte + typographie noire). Sur les
     *  pages sombres, la version blanche prend le relais — un logo dont le
     *  texte est noir disparaîtrait sur l'encre. */
    logoFile: 'frontend/src/assets/brand/logo1.png',
    logoFileSombre: 'frontend/src/assets/brand/logo1-blanc.png',

    /** Le visuel d'accueil de l'application sert de page de garde : un relief
     *  abstrait, sobre, qui ne signale aucun secteur d'activité. */
    cover: { type: 'photo', file: 'frontend/src/assets/fond-login.png' },

    contact: {
        name: 'Fatoumata Youma Sokona',
        phone: '+223 90 04 13 69',
        email: 'fysokona@gmail.com',
    },

    /**
     * Palette reprise des tokens de l'application (frontend/src/design-system).
     *
     * Un ajustement, et un seul : le vert de marque (#7FC81F) est calibré pour
     * des aplats. Posé en petit texte sur du papier, il tombe sous le seuil de
     * lisibilité. On garde la teinte et on change la clarté — le pas foncé
     * (#4F8210, qui est déjà la couleur des liens de l'application) sert sur
     * fond clair, le vert de marque sur fond sombre.
     */
    palette: {
        ink: '#14161A',
        paper: '#F6F7F9', soft: '#F1F3F5',
        body: '#3A3F47', taupe: '#6B7280', hair: '#E6E8EC',
        accent: '#4F8210', accentDark: '#7FC81F', accentSoft: '#EEF7DF',
        onDark: '#EDEEF0', onDarkSoft: '#C3C7CD', onDarkMute: '#9198A1',
    },
};
