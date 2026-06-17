import { useLocation } from 'react-router-dom';
import { Construction } from 'lucide-react';
import { NAVIGATION } from './navigation';

const PHASES: Record<string, string> = {
  P1: 'Phase 1 — cœur opérationnel',
  P2: 'Phase 2 — gouvernance & maîtrise',
  P3: 'Phase 3 — sécurité & extension',
};

/** Page d'attente pour les modules non encore implémentés (cf. docs/07-ROADMAP.md). */
export function PagePlaceholder(): JSX.Element {
  const { pathname } = useLocation();
  const entree = NAVIGATION.find((e) => e.chemin === pathname);
  const Icone = entree?.icone ?? Construction;

  return (
    <div
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 'var(--space-4)',
        textAlign: 'center',
        color: 'var(--text-muted)',
      }}
    >
      <Icone size={40} aria-hidden="true" />
      <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 600, color: 'var(--text)' }}>
        {entree?.libelle ?? 'Module'}
      </h1>
      <p style={{ maxWidth: '46ch' }}>
        Module à venir{entree ? ` — ${PHASES[entree.phase]}` : ''}. La structure et le design system
        sont prêts ; l'écran sera construit au lot correspondant.
      </p>
    </div>
  );
}
