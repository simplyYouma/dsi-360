import { api } from '@/lib/api';

/** Phase d'un statut : l'axe des filtres et des compteurs, commun aux huit modules. */
export type Phase = 'en_cours' | 'termine' | 'abandonne';
/** Nuance visuelle d'un statut, déclarée avec lui côté domaine. */
export type Ton = 'nouveau' | 'actif' | 'attente' | 'recul' | 'succes' | 'echec';

export interface EtatCycle {
  cle: string;
  libelle: string;
  phase: Phase;
  ton: Ton;
  /** État sans suite : le dossier ne bouge plus, il passe en lecture seule. */
  verrou: boolean;
}

/**
 * Cycles de vie chargés une fois depuis le serveur (`/referentiels/cycles-de-vie`).
 *
 * Le sens d'un statut — sa phase, son ton, son verrou — est déclaré dans `domain/etats` côté
 * backend. L'écran le **lit** au lieu de le redeviner : c'est ce qui empêche les couleurs et les
 * filtres de diverger, comme c'était le cas quand chaque fichier tenait sa propre liste.
 */
let parModule: Record<string, EtatCycle[]> = {};
// Repli quand l'appelant ne connaît pas le module (listes mêlées, « Ses tickets », journal…).
// Sûr : un test du domaine garantit qu'un même libellé a partout la même phase et le même ton.
let parStatut = new Map<string, EtatCycle>();

/** Charge les cycles de vie. Appelé au démarrage, avant le premier écran. */
export async function chargerCycles(): Promise<void> {
  const data = await api.get<Record<string, EtatCycle[]>>('/referentiels/cycles-de-vie');
  parModule = data;
  const index = new Map<string, EtatCycle>();
  for (const etats of Object.values(data)) {
    for (const e of etats) {
      // Le premier module gagne ; les homonymes ont le même sens, le test du domaine l'impose.
      if (!index.has(e.cle)) index.set(e.cle, e);
    }
  }
  parStatut = index;
}

/** Le cycle de vie d'un module (statuts ordonnés), ou une liste vide s'il est inconnu. */
export function cycleDuModule(module: string): EtatCycle[] {
  return parModule[module] ?? [];
}

/** Un statut, avec tout son sens. `module` affine la recherche quand il est connu. */
export function etatCycle(statut: string, module?: string): EtatCycle | undefined {
  if (module !== undefined) {
    const trouve = parModule[module]?.find((e) => e.cle === statut);
    if (trouve !== undefined) return trouve;
  }
  return parStatut.get(statut);
}

/** Libellé lisible d'un statut (« CAB » → « Attente comité »). Identité si inconnu. */
export function libelleStatut(statut: string, module?: string): string {
  return etatCycle(statut, module)?.libelle ?? statut;
}

/** Ton d'un statut. Repli « actif » : un statut inconnu est réputé en cours, jamais abouti. */
export function tonStatut(statut: string, module?: string): Ton {
  return etatCycle(statut, module)?.ton ?? 'actif';
}

/** Phase d'un statut. Repli « en cours » : on ne range jamais d'office un dossier parmi les réglés. */
export function phaseStatut(statut: string, module?: string): Phase {
  return etatCycle(statut, module)?.phase ?? 'en_cours';
}

/** Passer à cet état verrouille-t-il le dossier (plus aucune suite) ? Sert aux confirmations. */
export function verrouilleLeDossier(statut: string, module?: string): boolean {
  return etatCycle(statut, module)?.verrou ?? false;
}
