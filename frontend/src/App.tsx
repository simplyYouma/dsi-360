import { Moon, Sun, ShieldCheck } from 'lucide-react';
import { Button } from '@/design-system/primitives';
import { useTheme } from '@/design-system/ThemeProvider';

/**
 * Écran d'amorçage du squelette : valide que le design system (tokens, thème, primitives) tourne.
 * Sera remplacé par le shell applicatif (sidebar + topbar) au lot P1-0 (cf. docs/07-ROADMAP.md).
 */
export function App(): JSX.Element {
  const { theme, basculer } = useTheme();
  return (
    <main
      style={{
        minHeight: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 'var(--space-4)',
        padding: 'var(--space-6)',
        textAlign: 'center',
      }}
    >
      <ShieldCheck size={40} color="var(--accent)" aria-hidden="true" />
      <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 600 }}>DSI 360</h1>
      <p style={{ color: 'var(--text-muted)', maxWidth: '52ch' }}>
        Plateforme de gouvernance et de pilotage de la DSI — AFG Bank Mali. Squelette en place ;
        le tableau de bord et les modules arrivent au fil de la roadmap.
      </p>
      <Button variante="secondaire" onClick={basculer}>
        {theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}
        Thème {theme === 'light' ? 'sombre' : 'clair'}
      </Button>
    </main>
  );
}
