import { Inbox, AlertTriangle, Clock, History } from 'lucide-react';
import { AvatarPersonnage } from '@/common/AvatarPersonnage';
import styles from './MesTickets.module.css';
import type { MesStats } from './mesTicketsApi';

function couleurTaux(taux: number): string {
  return taux >= 90
    ? 'var(--status-ok)'
    : taux >= 75
      ? 'var(--status-warn)'
      : 'var(--status-danger)';
}

/** Petit anneau SVG (respect SLA), version compacte pour la bande. */
function MiniAnneau({ taux }: { taux: number }): JSX.Element {
  const r = 9;
  const circ = 2 * Math.PI * r;
  return (
    <svg viewBox="0 0 24 24" className={styles.miniAnneau} aria-hidden="true">
      <circle cx="12" cy="12" r={r} fill="none" stroke="var(--bg-subtle)" strokeWidth="3" />
      <circle
        cx="12"
        cy="12"
        r={r}
        fill="none"
        stroke={couleurTaux(taux)}
        strokeWidth="3"
        strokeLinecap="round"
        strokeDasharray={circ}
        strokeDashoffset={circ * (1 - taux / 100)}
        transform="rotate(-90 12 12)"
        style={{ transition: 'stroke-dashoffset 0.6s ease' }}
      />
    </svg>
  );
}

interface Pastille {
  cle: string;
  icone: JSX.Element;
  valeur: string;
  libelle: string;
  couleur: string;
  attenue?: boolean;
}

/** Bande profil compacte : identité de l'agent + état de la file en un coup d'œil.
 *  Volontairement sur une seule ligne fine — l'analyse détaillée vit dans l'onglet « Analyse ». */
export function BandeauAgent({ stats }: { stats: MesStats }): JSX.Element {
  const pastilles: Pastille[] = [
    {
      cle: 'ouverts',
      icone: <Inbox size={15} />,
      valeur: String(stats.ouverts),
      libelle: 'à traiter',
      couleur: 'var(--text)',
    },
    {
      cle: 'retard',
      icone: <AlertTriangle size={15} />,
      valeur: String(stats.en_retard),
      libelle: 'SLA dépassé',
      couleur: 'var(--status-danger)',
      attenue: stats.en_retard === 0,
    },
    {
      cle: 'proche',
      icone: <Clock size={15} />,
      valeur: String(stats.approche),
      libelle: 'échéance proche',
      couleur: 'var(--status-warn)',
      attenue: stats.approche === 0,
    },
    {
      cle: 'sla',
      icone: <MiniAnneau taux={stats.respect_sla} />,
      valeur: `${stats.respect_sla} %`,
      libelle: 'respect SLA',
      couleur: couleurTaux(stats.respect_sla),
    },
  ];
  if (stats.plus_ancien_jours !== null) {
    pastilles.push({
      cle: 'ancien',
      icone: <History size={15} />,
      valeur: `${stats.plus_ancien_jours} j`,
      libelle: 'ticket le plus ancien',
      couleur: 'var(--cat-4)',
    });
  }

  return (
    <section className={styles.bandeau}>
      <div className={styles.bandeauProfil}>
        <AvatarPersonnage seed={stats.agent.nom} taille={44} />
        <div className={styles.profilTxt}>
          <span className={styles.bandeauNom}>{stats.agent.nom}</span>
          <span className={styles.profilMeta}>
            {stats.agent.profil}
            {stats.agent.direction !== null && ` · ${stats.agent.direction}`}
          </span>
        </div>
      </div>
      <ul className={styles.bandeauStats}>
        {pastilles.map((p) => (
          <li
            key={p.cle}
            className={styles.statPastille}
            data-attenue={p.attenue ? 'oui' : undefined}
          >
            <span className={styles.statIcone} style={{ color: p.couleur }}>
              {p.icone}
            </span>
            <span className={styles.statValeur} style={{ color: p.couleur }}>
              {p.valeur}
            </span>
            <span className={styles.statLibelle}>{p.libelle}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
