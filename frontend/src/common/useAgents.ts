import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

export interface AgentRef {
  id: string;
  nom: string;
  profil?: string;
}

// Cache au niveau module : les agents changent rarement — un seul appel réseau, partagé par tous
// les champs de mention (discussions), même s'il y en a beaucoup à l'écran.
let cache: Promise<AgentRef[]> | null = null;

/** Liste des agents DSI (pour l'autocomplétion @). Mise en cache le temps de la session. */
export function useAgents(): AgentRef[] {
  const [agents, setAgents] = useState<AgentRef[]>([]);
  useEffect(() => {
    cache ??= api.get<AgentRef[]>('/referentiels/agents');
    let vivant = true;
    void cache.then((liste) => {
      if (vivant) setAgents(liste);
    });
    return () => {
      vivant = false;
    };
  }, []);
  return agents;
}

/** Identifiants des agents mentionnés (« @Nom ») réellement présents dans le texte. */
export function extraireMentions(texte: string, agents: AgentRef[]): string[] {
  return agents.filter((a) => texte.includes(`@${a.nom}`)).map((a) => a.id);
}
