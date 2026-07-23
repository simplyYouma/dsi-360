import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { createPortal } from 'react-dom';
import { Calendar, ChevronLeft, ChevronRight } from 'lucide-react';
import { cx } from './cx';
import styles from './SelecteurDate.module.css';

interface Props {
  valeur: string | null; // ISO yyyy-mm-dd
  onChange: (iso: string | null) => void;
  placeholder?: string;
  /** Jauge d'urgence : le champ se remplit de rouge à l'approche de l'échéance (plein si dépassée). */
  remplissageEcheance?: boolean;
  /** Date de départ (création) pour calculer la proportion. Sinon fenêtre de 14 jours. */
  depuis?: string | null;
  /** Grisé : la date reste lisible, le calendrier ne s'ouvre pas. */
  desactive?: boolean;
  /** Raison du grisage, en infobulle. */
  titreDesactive?: string;
  /** Verdict figé d'une échéance close : « tenue » (vert) ou « depassee » (rouge).
   *  Le décompte s'arrête, le résultat reste — prime sur `remplissageEcheance`. */
  verdict?: 'tenue' | 'depassee' | null;
}

/** Proportion 0→1 de « temps consommé » avant l'échéance (1 = atteinte ou dépassée). */
function proportionEcheance(echeance: string, depuis?: string | null): number {
  const fin = new Date(echeance);
  fin.setHours(23, 59, 59, 999);
  const finMs = fin.getTime();
  const maintenant = Date.now();
  if (maintenant >= finMs) return 1;
  const depuisMs =
    depuis != null && depuis !== '' ? new Date(depuis).getTime() : finMs - 14 * 86_400_000; // fenêtre par défaut : 14 jours
  if (maintenant <= depuisMs || finMs <= depuisMs) return 0;
  return (maintenant - depuisMs) / (finMs - depuisMs);
}

const MOIS = [
  'Janvier',
  'Février',
  'Mars',
  'Avril',
  'Mai',
  'Juin',
  'Juillet',
  'Août',
  'Septembre',
  'Octobre',
  'Novembre',
  'Décembre',
];
const JOURS = ['Lu', 'Ma', 'Me', 'Je', 'Ve', 'Sa', 'Di'];

const deuxChiffres = (n: number): string => String(n).padStart(2, '0');
const enIso = (d: Date): string =>
  `${d.getFullYear()}-${deuxChiffres(d.getMonth() + 1)}-${deuxChiffres(d.getDate())}`;

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
export function SelecteurDate({
  valeur,
  onChange,
  placeholder = 'Choisir une date',
  remplissageEcheance = false,
  depuis,
  desactive = false,
  titreDesactive,
  verdict = null,
}: Props): JSX.Element {
  const [ouvert, setOuvert] = useState(false);
  const [pos, setPos] = useState<CSSProperties | null>(null);
  const [curseur, setCurseur] = useState<Date>(() => depuisIso(valeur) ?? new Date());
  const ref = useRef<HTMLDivElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const declencheur = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    // Le calendrier est rendu en portal (hors `ref`) : on l'inclut dans le test de clic intérieur.
    const surClic = (e: MouseEvent): void => {
      const n = e.target as Node;
      const dedans =
        (ref.current?.contains(n) ?? false) || (popoverRef.current?.contains(n) ?? false);
      if (!dedans) setOuvert(false);
    };
    document.addEventListener('mousedown', surClic);
    return () => document.removeEventListener('mousedown', surClic);
  }, []);

  // Popover en position fixe (calcul au clic) : bascule vers le haut si peu de place en bas ;
  // on garde le calendrier (268 px) dans la fenêtre pour éviter tout débordement horizontal.
  const LARGEUR = 268;
  const basculer = (): void => {
    const r = declencheur.current?.getBoundingClientRect();
    if (r) {
      const dessous = window.innerHeight - r.bottom;
      const left = Math.max(4, Math.min(r.left, window.innerWidth - LARGEUR - 4));
      setPos(
        dessous < 340 && r.top > dessous
          ? { position: 'fixed', bottom: window.innerHeight - r.top + 4, left }
          : { position: 'fixed', top: r.bottom + 4, left },
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

  // Un verdict rendu fige la jauge à plein : elle ne mesure plus un délai qui court, elle
  // rapporte comment il s'est terminé.
  const jauge =
    verdict !== null && valeur
      ? 1
      : remplissageEcheance && valeur
        ? proportionEcheance(valeur, depuis)
        : null;

  return (
    <div className={styles.conteneur} ref={ref}>
      <button
        ref={declencheur}
        type="button"
        className={cx(styles.champ, jauge !== null && styles.champJauge)}
        onClick={basculer}
        disabled={desactive}
        title={desactive ? titreDesactive : undefined}
      >
        {jauge !== null && (
          <span
            className={cx(
              styles.jauge,
              jauge >= 1 && (verdict === 'tenue' ? styles.jaugeTenue : styles.jaugePleine),
            )}
            style={{ width: `${Math.round(jauge * 100)}%` }}
            aria-hidden="true"
          />
        )}
        <Calendar size={16} className={styles.icone} />
        <span className={cx(styles.contenu, valeur ? styles.valeur : styles.placeholder)}>
          {valeur ? formatFr(valeur) : placeholder}
        </span>
      </button>

      {ouvert &&
        pos !== null &&
        createPortal(
          <div ref={popoverRef} className={styles.popover} style={pos}>
            <div className={styles.tete}>
              <button
                type="button"
                className={styles.nav}
                onClick={() => setCurseur(new Date(annee, mois - 1, 1))}
                aria-label="Mois précédent"
              >
                <ChevronLeft size={16} />
              </button>
              <span className={styles.moisTitre}>
                {MOIS[mois]} {annee}
              </span>
              <button
                type="button"
                className={styles.nav}
                onClick={() => setCurseur(new Date(annee, mois + 1, 1))}
                aria-label="Mois suivant"
              >
                <ChevronRight size={16} />
              </button>
            </div>
            <div className={styles.semaine}>
              {JOURS.map((j) => (
                <span key={j} className={styles.jourEntete}>
                  {j}
                </span>
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
                    className={cx(
                      styles.jour,
                      estSel && styles.jourSel,
                      !estSel && estAuj && styles.jourAuj,
                    )}
                    onClick={() => choisir(j)}
                  >
                    {j}
                  </button>
                );
              })}
            </div>
            <div className={styles.pied}>
              <button
                type="button"
                className={styles.aujourdhui}
                onClick={() => {
                  onChange(aujourdhui);
                  setOuvert(false);
                }}
              >
                Aujourd’hui
              </button>
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
          </div>,
          document.body,
        )}
    </div>
  );
}
