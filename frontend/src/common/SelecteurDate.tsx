import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { Calendar, ChevronLeft, ChevronRight } from 'lucide-react';
import { cx } from './cx';
import styles from './SelecteurDate.module.css';

interface Props {
  valeur: string | null; // ISO yyyy-mm-dd
  onChange: (iso: string | null) => void;
  placeholder?: string;
}

const MOIS = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
];
const JOURS = ['Lu', 'Ma', 'Me', 'Je', 'Ve', 'Sa', 'Di'];

const deuxChiffres = (n: number): string => String(n).padStart(2, '0');
const enIso = (d: Date): string => `${d.getFullYear()}-${deuxChiffres(d.getMonth() + 1)}-${deuxChiffres(d.getDate())}`;

function depuisIso(s: string | null): Date | null {
  if (s === null || s === '') return null;
  const [y, m, j] = s.split('-').map(Number);
  if (!y || !m || !j) return null;
  return new Date(y, m - 1, j);
}

function formatFr(s: string): string {
  const d = depuisIso(s);
  if (d === null) return s;
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'long', year: 'numeric' });
}

/** Sélecteur de date maison (calendrier en popover) — aucun composant natif navigateur. */
export function SelecteurDate({ valeur, onChange, placeholder = 'Choisir une date' }: Props): JSX.Element {
  const [ouvert, setOuvert] = useState(false);
  const [pos, setPos] = useState<CSSProperties | null>(null);
  const [curseur, setCurseur] = useState<Date>(() => depuisIso(valeur) ?? new Date());
  const ref = useRef<HTMLDivElement>(null);
  const declencheur = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const surClic = (e: MouseEvent): void => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOuvert(false);
    };
    document.addEventListener('mousedown', surClic);
    return () => document.removeEventListener('mousedown', surClic);
  }, []);

  // Popover en position fixe (calcul au clic) : bascule vers le haut si peu de place en bas.
  const basculer = (): void => {
    const r = declencheur.current?.getBoundingClientRect();
    if (r) {
      const dessous = window.innerHeight - r.bottom;
      setPos(
        dessous < 340 && r.top > dessous
          ? { position: 'fixed', bottom: window.innerHeight - r.top + 4, left: r.left }
          : { position: 'fixed', top: r.bottom + 4, left: r.left },
      );
    }
    setOuvert((o) => !o);
  };

  const annee = curseur.getFullYear();
  const mois = curseur.getMonth();
  const premier = new Date(annee, mois, 1);
  const decalage = (premier.getDay() + 6) % 7; // lundi en première colonne
  const nbJours = new Date(annee, mois + 1, 0).getDate();
  const cellules: (number | null)[] = [];
  for (let i = 0; i < decalage; i += 1) cellules.push(null);
  for (let j = 1; j <= nbJours; j += 1) cellules.push(j);

  const aujourdhui = enIso(new Date());

  const choisir = (j: number): void => {
    onChange(enIso(new Date(annee, mois, j)));
    setOuvert(false);
  };

  return (
    <div className={styles.conteneur} ref={ref}>
      <button ref={declencheur} type="button" className={styles.champ} onClick={basculer}>
        <Calendar size={16} />
        <span className={valeur ? styles.valeur : styles.placeholder}>
          {valeur ? formatFr(valeur) : placeholder}
        </span>
      </button>

      {ouvert && pos !== null && (
        <div className={styles.popover} style={pos}>
          <div className={styles.tete}>
            <button type="button" className={styles.nav} onClick={() => setCurseur(new Date(annee, mois - 1, 1))} aria-label="Mois précédent">
              <ChevronLeft size={16} />
            </button>
            <span className={styles.moisTitre}>
              {MOIS[mois]} {annee}
            </span>
            <button type="button" className={styles.nav} onClick={() => setCurseur(new Date(annee, mois + 1, 1))} aria-label="Mois suivant">
              <ChevronRight size={16} />
            </button>
          </div>
          <div className={styles.semaine}>
            {JOURS.map((j) => (
              <span key={j} className={styles.jourEntete}>{j}</span>
            ))}
          </div>
          <div className={styles.grille}>
            {cellules.map((j, idx) => {
              if (j === null) return <span key={`v-${idx}`} />;
              const dIso = enIso(new Date(annee, mois, j));
              const estSel = valeur === dIso;
              const estAuj = aujourdhui === dIso;
              return (
                <button
                  key={dIso}
                  type="button"
                  className={cx(styles.jour, estSel && styles.jourSel, !estSel && estAuj && styles.jourAuj)}
                  onClick={() => choisir(j)}
                >
                  {j}
                </button>
              );
            })}
          </div>
          {valeur && (
            <button
              type="button"
              className={styles.effacer}
              onClick={() => {
                onChange(null);
                setOuvert(false);
              }}
            >
              Effacer
            </button>
          )}
        </div>
      )}
    </div>
  );
}
