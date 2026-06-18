import { useEffect, useState } from 'react';
import { BarChart, Bar, Cell, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts';
import { Card } from '@/design-system/primitives';
import incidents from '@/features/incidents/IncidentsPage.module.css';
import styles from './Analyses.module.css';
import { analysesApi, type AnalyseItem, type Analyses } from './analysesApi';

const MODULE_LABEL: Record<string, string> = {
  incident: 'Incidents',
  demande: 'Demandes',
  projet: 'Projets',
  changement: 'Changements',
  audit: 'Audit',
  risque: 'Risques',
  cybersecurite: 'Cybersécurité',
  gouvernance: 'Gouvernance',
};
const MODULE_COULEUR: Record<string, string> = {
  incident: '#4f6bed',
  demande: '#15a394',
  projet: '#e0a341',
  changement: '#e2557b',
  audit: '#8a5cf6',
  risque: '#2fa363',
  cybersecurite: '#3aa0c9',
  gouvernance: '#e07a3c',
};
const PALETTE = ['#4f6bed', '#15a394', '#e0a341', '#e2557b', '#8a5cf6', '#2fa363', '#3aa0c9', '#e07a3c'];

interface Barre extends AnalyseItem {
  couleur: string;
}

function Barres({ data }: { data: Barre[] }): JSX.Element {
  if (data.length === 0) return <p className={styles.vide}>Aucune donnée.</p>;
  return (
    <ResponsiveContainer width="100%" height={Math.max(140, data.length * 44)}>
      <BarChart layout="vertical" data={data} margin={{ top: 0, right: 16, left: 8, bottom: 0 }}>
        <XAxis type="number" hide allowDecimals={false} />
        <YAxis
          type="category"
          dataKey="libelle"
          width={140}
          tickLine={false}
          axisLine={false}
          tick={{ fontSize: 13, fill: 'var(--text-muted)' }}
        />
        <Tooltip
          cursor={{ fill: 'var(--bg-subtle)' }}
          contentStyle={{
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 10,
            fontSize: 13,
          }}
        />
        <Bar dataKey="valeur" radius={[0, 8, 8, 0]} barSize={18}>
          {data.map((d) => (
            <Cell key={d.libelle} fill={d.couleur} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function AnalysesPage(): JSX.Element {
  const [a, setA] = useState<Analyses | null>(null);

  useEffect(() => {
    void analysesApi.charger().then(setA);
  }, []);

  const modules: Barre[] = (a?.par_module ?? []).map((m) => ({
    libelle: MODULE_LABEL[m.libelle] ?? m.libelle,
    valeur: m.valeur,
    couleur: MODULE_COULEUR[m.libelle] ?? '#94a3b8',
  }));
  const responsables: Barre[] = (a?.par_responsable ?? []).map((r, i) => ({
    ...r,
    couleur: PALETTE[i % PALETTE.length] ?? '#4f6bed',
  }));
  const directions: Barre[] = (a?.par_direction ?? []).map((d, i) => ({
    ...d,
    couleur: PALETTE[i % PALETTE.length] ?? '#4f6bed',
  }));

  return (
    <div className={incidents.page}>
      <header className={incidents.entete}>
        <div>
          <h1 className={incidents.titre}>Analyses</h1>
          <p className={incidents.sous}>Répartition et charge des activités en cours.</p>
        </div>
      </header>

      <Card>
        <div className={styles.totalCarte}>
          <span className={styles.totalValeur}>{a ? a.total : '—'}</span>
          <span className={styles.totalLibelle}>activités en cours (hors clôturées)</span>
        </div>
      </Card>

      <section className={styles.grille}>
        <Card>
          <h2 className={styles.chartTitre}>Activités par module</h2>
          <Barres data={modules} />
        </Card>
        <Card>
          <h2 className={styles.chartTitre}>Charge par responsable</h2>
          <Barres data={responsables} />
        </Card>
        <Card>
          <h2 className={styles.chartTitre}>Par direction</h2>
          <Barres data={directions} />
        </Card>
        <Card>
          <h2 className={styles.chartTitre}>Échéances SLA</h2>
          <div className={styles.sla}>
            <div className={styles.slaStat}>
              <span className={styles.slaValeur} style={{ color: 'var(--status-ok)' }}>
                {a ? a.sla.a_lheure : '—'}
              </span>
              <span className={styles.slaLibelle}>À l'heure</span>
            </div>
            <div className={styles.slaStat}>
              <span className={styles.slaValeur} style={{ color: 'var(--status-warn)' }}>
                {a ? a.sla.approche : '—'}
              </span>
              <span className={styles.slaLibelle}>En approche</span>
            </div>
            <div className={styles.slaStat}>
              <span className={styles.slaValeur} style={{ color: 'var(--status-danger)' }}>
                {a ? a.sla.depasse : '—'}
              </span>
              <span className={styles.slaLibelle}>Dépassé</span>
            </div>
          </div>
        </Card>
      </section>
    </div>
  );
}
