import { SelecteurDate } from './SelecteurDate';
import { estPerso, type Periode } from './periode';
import styles from './FiltrePeriode.module.css';

const PRESETS: { libelle: string; jours: number | null }[] = [
  { libelle: '7 j', jours: 7 },
  { libelle: '30 j', jours: 30 },
  { libelle: '90 j', jours: 90 },
  { libelle: 'Tout', jours: null },
];

interface Props {
  valeur: Periode;
  onChange: (p: Periode) => void;
}

/** Filtre de période réutilisable : presets (7/30/90/Tout) + plage de dates au calendrier. */
export function FiltrePeriode({ valeur, onChange }: Props): JSX.Element {
  const perso = estPerso(valeur);
  return (
    <div className={styles.filtre}>
      <div className={styles.presets}>
        {PRESETS.map((p) => (
          <button
            key={p.libelle}
            className={!perso && valeur.jours === p.jours ? styles.presetOn : styles.preset}
            onClick={() => onChange({ jours: p.jours, du: null, au: null })}
          >
            {p.libelle}
          </button>
        ))}
      </div>
      <div className={styles.dates}>
        <SelecteurDate
          valeur={valeur.du}
          onChange={(du) => onChange({ jours: null, du, au: valeur.au })}
          placeholder="Du…"
        />
        <span className={styles.tiret} aria-hidden="true">
          →
        </span>
        <SelecteurDate
          valeur={valeur.au}
          onChange={(au) => onChange({ jours: null, du: valeur.du, au })}
          placeholder="Au…"
        />
      </div>
    </div>
  );
}
