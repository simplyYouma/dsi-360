import { TriangleAlert, Inbox, Timer, FolderKanban, ShieldAlert } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { Card, StatusBadge } from '@/design-system/primitives';
import styles from './DashboardPage.module.css';

interface Kpi {
  libelle: string;
  valeur: string;
  icone: LucideIcon;
  couleur: string; // palette catégorielle (touche de couleur)
  badge: JSX.Element;
}

// Données de DÉMONSTRATION (le calcul réel arrive avec le moteur d'indicateurs, lot P1).
const KPIS: Kpi[] = [
  {
    libelle: 'Incidents ouverts',
    valeur: '12',
    icone: TriangleAlert,
    couleur: 'var(--cat-1)',
    badge: <StatusBadge statut="warn">3 en approche SLA</StatusBadge>,
  },
  {
    libelle: 'Incidents critiques',
    valeur: '3',
    icone: ShieldAlert,
    couleur: 'var(--cat-4)',
    badge: <StatusBadge statut="danger">P1</StatusBadge>,
  },
  {
    libelle: 'Respect SLA',
    valeur: '92 %',
    icone: Timer,
    couleur: 'var(--cat-2)',
    badge: <StatusBadge statut="ok">objectif tenu</StatusBadge>,
  },
  {
    libelle: 'Demandes en cours',
    valeur: '27',
    icone: Inbox,
    couleur: 'var(--cat-7)',
    badge: <StatusBadge couleur="var(--cat-7)">8 à valider</StatusBadge>,
  },
  {
    libelle: 'Projets en retard',
    valeur: '2',
    icone: FolderKanban,
    couleur: 'var(--cat-3)',
    badge: <StatusBadge statut="warn">à surveiller</StatusBadge>,
  },
];

export function DashboardPage(): JSX.Element {
  return (
    <div className={styles.page}>
      <header className={styles.entete}>
        <h1 className={styles.titre}>Tableau de bord</h1>
        <p className={styles.sous}>
          Vue d'ensemble des activités de la DSI — AFG Bank Mali.
          <span className={styles.demo}> Données de démonstration.</span>
        </p>
      </header>

      <section className={styles.grilleKpi}>
        {KPIS.map(({ libelle, valeur, icone: Icone, couleur, badge }) => (
          <Card key={libelle}>
            <div className={styles.kpiTete}>
              <span
                className={styles.kpiIcone}
                style={{ color: couleur, background: `color-mix(in srgb, ${couleur} 12%, transparent)` }}
              >
                <Icone size={20} />
              </span>
              {badge}
            </div>
            <div className={styles.kpiValeur}>{valeur}</div>
            <div className={styles.kpiLibelle}>{libelle}</div>
          </Card>
        ))}
      </section>

      <Card className={styles.placeholderGraph}>
        <span className={styles.placeholderTexte}>
          Graphiques (composition des statuts, donut de répartition, échéances SLA) — lot P1.
        </span>
      </Card>
    </div>
  );
}
