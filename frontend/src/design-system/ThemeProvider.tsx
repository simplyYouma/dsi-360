import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

type Theme = 'light' | 'dark';
interface ThemeCtx {
  theme: Theme;
  basculer: () => void;
}
const CLE = 'dsi360.theme';
const Contexte = createContext<ThemeCtx | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }): JSX.Element {
  const [theme, setTheme] = useState<Theme>(
    () => (localStorage.getItem(CLE) as Theme | null) ?? 'light',
  );
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(CLE, theme);
  }, [theme]);
  const basculer = useCallback(() => setTheme((t) => (t === 'light' ? 'dark' : 'light')), []);
  const valeur = useMemo(() => ({ theme, basculer }), [theme, basculer]);
  return <Contexte.Provider value={valeur}>{children}</Contexte.Provider>;
}

export function useTheme(): ThemeCtx {
  const ctx = useContext(Contexte);
  if (ctx === null) throw new Error('useTheme doit être utilisé dans un ThemeProvider.');
  return ctx;
}
