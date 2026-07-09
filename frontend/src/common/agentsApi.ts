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
export function chargerAgents(module?: string): Promise<Agent[]> {
  const suffixe = module === undefined ? '' : `?module=${encodeURIComponent(module)}`;
  return api.get<Agent[]>(`/referentiels/agents${suffixe}`);
}

/** Clé d'accès déduite du préfixe d'un module (« /changements » → « changements »). */
export function moduleDeLaBase(base: string): string {
  return base.replace(/^\//, '');
}
