import { useState } from 'react';
import { Moon, Sun, ShieldCheck, Search, Users } from 'lucide-react';
import { Button, Modale, LigneListe } from '@/design-system/primitives';
import { useTheme } from '@/design-system/ThemeProvider';

/**
 * Écran d'amorçage du squelette : valide que le design system (tokens, thème, primitives, modale)
 * tourne. Sera remplacé par le shell applicatif (sidebar + topbar) au lot P1-0 (cf. docs/07).
 */
export function App(): JSX.Element {
  const { theme, basculer } = useTheme();
  const [modale, setModale] = useState(false);

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
        Plateforme de gouvernance et de pilotage de la DSI — AFG Bank Mali. Squelette en place ; le
        tableau de bord et les modules arrivent au fil de la roadmap.
      </p>

      <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
        <Button variante="secondaire" onClick={basculer}>
          {theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}
          Thème {theme === 'light' ? 'sombre' : 'clair'}
        </Button>
        <Button onClick={() => setModale(true)}>Aperçu modale</Button>
      </div>

      <Modale
        ouverte={modale}
        onFermer={() => setModale(false)}
        titre="Choisir un design"
        largeur={620}
        pied={
          <Button variante="secondaire" disabled>
            Déplacer
          </Button>
        }
      >
        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-3)',
            padding: '0 var(--space-4)',
            height: 52,
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-pill)',
            color: 'var(--text-muted)',
          }}
        >
          <Search size={20} />
          <input
            placeholder="Rechercher dans tous les dossiers"
            style={{
              border: 'none',
              outline: 'none',
              background: 'transparent',
              color: 'var(--text)',
              fontSize: 'var(--text-base)',
              width: '100%',
            }}
          />
        </label>

        <div style={{ marginTop: 'var(--space-2)' }}>
          <LigneListe
            pastille={<span style={{ color: 'var(--on-accent)' }}>FY</span>}
            fondPastille="var(--accent)"
            libelle="Vos projets"
          />
          <LigneListe
            pastille={<Users size={20} />}
            libelle="Partagés avec vous"
          />
        </div>
      </Modale>
    </main>
  );
}
