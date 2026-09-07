import { api } from '@/lib/api';

export interface Agent {
  id: string;
  nom: string;
  profil: string;
}

/** Comptes désignables comme gestionnaire, contributeur, valideur ou assigné d'une tâche.
 *
 *  `module` est la clé d'accès (« incidents », « projets », « changements »…). Le serveur ne
 *  renvoie alors que les comptes actifs dont le profil y a accès : on ne désigne pas quelqu'un à
 *  qui la page resterait fermée, et le serveur refuserait la désignation.
 *
 *  Sans `module`, tous les comptes actifs — pour l'autocomplétion des mentions @. */
export function chargerAgents(module?: string, departement?: string | null): Promise<Agent[]> {
  const p = new URLSearchParams();
  if (module !== undefined) p.set('module', module);
  // Le département d'un agent se déduit de son profil : le serveur tranche, l'écran demande.
  // Les profils transverses restent proposés — ils travaillent partout.
  if (departement) p.set('departement', departement);
  const suffixe = p.toString() === '' ? '' : `?${p.toString()}`;
  return api.get<Agent[]>(`/referentiels/agents${suffixe}`);
}

/** Clé d'accès déduite du préfixe d'un module (« /changements » → « changements »). */
export function moduleDeLaBase(base: string): string {
  return base.replace(/^\//, '');
}
