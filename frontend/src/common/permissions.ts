/** Ce que l'utilisateur peut faire sur *une* activité, calculé par le serveur.
 *
 *  L'écran obéit à ces booléens ; il ne rejoue pas la règle. Sinon elle vivrait à deux endroits
 *  et finirait par diverger : on laisserait cliquer là où le serveur refuse, ou l'on masquerait ce
 *  qu'il permet. Source : `application/autorisations.capacites` (cf. docs/adr/0003).
 */
export interface Permissions {
  /** Assigner le gestionnaire ou le chef de projet. */
  peut_assigner: boolean;
  /** Fixer impact et urgence, ou le Type d'un changement. */
  peut_evaluer: boolean;
  /** Désigner contributeurs et valideurs. */
  peut_gerer_acteurs: boolean;
  /** Faire avancer le sujet : transitions, tâches, notes, documents, liens. */
  peut_travailler: boolean;
  /** Approuver ou rejeter. */
  peut_decider: boolean;
}

/** Aucune capacité : ce qu'on affiche tant que le détail n'est pas chargé. */
export const AUCUNE_PERMISSION: Permissions = {
  peut_assigner: false,
  peut_evaluer: false,
  peut_gerer_acteurs: false,
  peut_travailler: false,
  peut_decider: false,
};
