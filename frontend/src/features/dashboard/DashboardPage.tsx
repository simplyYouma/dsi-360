import { TriangleAlert, ShieldAlert, Timer, Inbox, FolderKanban, Flame } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { Card } from '@/design-system/primitives';
import styles from './DashboardPage.module.css';

interface Kpi {
  libelle: string;
  valeur: string;
  icone: LucideIcon;
  couleur: string;
  note: string;
  tonNote?: 'ok' | 'warn' | 'danger';
}

// Données de démonstration (le calcul réel arrive avec le moteur d'indicateurs).
const KPIS: Kpi[] = [
  { libelle: 'Incidents ouverts', valeur: '12', icone: TriangleAlert, couleur: 'var(--cat-1)', note: '3 en approche SLA', tonNote: 'warn' },
  { libelle: 'Incidents critiques', valeur: '3', icone: ShieldAlert, couleur: 'var(--cat-4)', note: 'Priorité P1', tonNote: 'danger' },
  { libelle: 'Respect SLA', valeur: '92 %', icone: Timer, couleur: 'var(--cat-2)', note: 'Objectif tenu', tonNote: 'ok' },
  { libelle: 'Demandes en cours', valeur: '27', icone: Inbox, couleur: 'var(--cat-7)', note: '8 à valider' },
  { libelle: 'Projets en retard', valeur: '2', icone: FolderKanban, couleur: 'var(--cat-3)', note: 'À surveiller', tonNote: 'warn' },
  { libelle: 'Risques critiques', valeur: '4', icone: Flame, couleur: 'var(--cat-5)', note: 'Revue requise' },
];

export function DashboardPage(): JSX.Element {
  return (
    <div className={styles.page}>
      <header className={styles.entete}>
        <h1 className={styles.titre}>Tableau de bord</h1>
        <p className={styles.sous}>Vue d'ensemble des activités de la DSI — AFG Bank Mali.</p>
      </header>

      <section className={styles.grille}>
        {KPIS.map(({ libelle, valeur, icone: Icone, couleur, note, tonNote }) => (
          <Card key={libelle} className={styles.kpi}>
            <div className={styles.kpiTete}>
              <span className={styles.kpiIcone} style={{ color: couleur }}>
                <Icone size={18} />
              </span>
              <span className={styles.kpiLibelle}>{libelle}</span>
            </div>
            <div className={styles.kpiValeur}>{valeur}</div>
            <div className={styles.kpiNote} data-ton={tonNote}>
              {note}
            </div>
          </Card>
        ))}
      </section>

      <Card className={styles.graph}>
        <span className={styles.graphTexte}>
          Graphiques (composition des statuts, donut de répartition, échéances SLA) — à venir.
        </span>
      </Card>
    </div>
  );
}
