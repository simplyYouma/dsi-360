import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { api, aUnJeton, definirJetons, effacerJetons } from './api';

export interface Moi {
  id: string;
  email: string;
  nom: string;
  prenom: string;
  profil: string;
  profil_libelle: string;
  transverse: boolean;
  direction: string | null;
  doit_changer_mdp: boolean;
  acces: string[];
}

type Statut = 'chargement' | 'pret';

interface AuthCtx {
  statut: Statut;
  moi: Moi | null;
  connecter: (email: string, motDePasse: string) => Promise<void>;
  deconnecter: () => Promise<void>;
  rafraichir: () => Promise<void>;
}

const Contexte = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }): JSX.Element {
  const [statut, setStatut] = useState<Statut>('chargement');
  const [moi, setMoi] = useState<Moi | null>(null);

  useEffect(() => {
    let actif = true;
    const init = async (): Promise<void> => {
      if (!aUnJeton()) {
        if (actif) setStatut('pret');
        return;
      }
      try {
        const profil = await api.get<Moi>('/moi');
        if (actif) setMoi(profil);
      } catch {
        effacerJetons();
      } finally {
        if (actif) setStatut('pret');
      }
    };
    void init();
    return () => {
      actif = false;
    };
  }, []);

  const connecter = useCallback(async (email: string, motDePasse: string): Promise<void> => {
    const jetons = await api.post<{ acces: string; refresh: string }>('/auth/login', {
      email,
      mot_de_passe: motDePasse,
    });
    definirJetons(jetons.acces, jetons.refresh);
    const profil = await api.get<Moi>('/moi');
    setMoi(profil);
  }, []);

  const deconnecter = useCallback(async (): Promise<void> => {
    try {
      await api.post('/auth/logout');
    } catch {
      /* sans état : on ignore */
    }
    effacerJetons();
    setMoi(null);
  }, []);

  const rafraichir = useCallback(async (): Promise<void> => {
    setMoi(await api.get<Moi>('/moi'));
  }, []);

  const valeur = useMemo(
    () => ({ statut, moi, connecter, deconnecter, rafraichir }),
    [statut, moi, connecter, deconnecter, rafraichir],
  );
  return <Contexte.Provider value={valeur}>{children}</Contexte.Provider>;
}

export function useAuth(): AuthCtx {
  const ctx = useContext(Contexte);
  if (ctx === null) throw new Error('useAuth doit être utilisé dans un AuthProvider.');
  return ctx;
}
