import { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ChevronDown, MoonStar, Timer, TriangleAlert, X } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { cleAcces } from '@/features/shell/navigation';
import { eodApi, heure, jour, type DetailEod } from './eodApi';
import styles from './VeilleEod.module.css';

/** Toutes les 45 s : une soirée se pointe à la main, rien n'y bouge à la seconde. Assez souvent
 *  pour qu'un collègue qui pointe depuis son poste se voie ici, assez rarement pour ne pas
 *  entretenir une conversation permanente avec le serveur. */
const RAFRAICHISSEMENT_MS = 45_000;

const CLE_REPLI = 'dsi360.eod.veille.replie';
/** La soirée que l'on a explicitement écartée. On garde son identifiant, et non un simple
 *  « masqué » : la veilleuse doit revenir d'elle-même la nuit suivante — c'est une autre soirée,
 *  et personne ne pensera à la rallumer. */
const CLE_ECARTEE = 'dsi360.eod.veille.ecartee';

function lire(cle: string): string | null {
  try {
    return localStorage.getItem(cle);
  } catch {
    return null;
  }
}

function ecrire(cle: string, valeur: string | null): void {
  try {
    if (valeur === null) localStorage.removeItem(cle);
    else localStorage.setItem(cle, valeur);
  } catch {
    /* Navigation privée, stockage refusé : la veilleuse fonctionne, elle oublie juste ses réglages. */
  }
}

/** Temps écoulé « 04:21 » / « 1:12:40 ». Recopié court plutôt que partagé : la page de pointage a
 *  le même besoin, mais la veilleuse doit pouvoir vivre sans elle. */
function ecoule(debut: string, maintenant: number): string {
  const total = Math.max(0, Math.floor((maintenant - new Date(debut).getTime()) / 1000));
  const h = Math.floor(total / 3600);
  const mm = String(Math.floor((total % 3600) / 60)).padStart(2, '0');
  const ss = String(total % 60).padStart(2, '0');
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

/**
 * LA VEILLEUSE — la soirée EOD en cours, gardée sous les yeux où qu'on aille dans l'application.
 *
 * Une nuit d'exploitation ne tient pas l'opérateur devant un seul écran : il ouvre un incident,
 * consulte un équipement, répond à un ticket. Pendant ce temps, une étape tourne — et c'est
 * précisément le temps qu'elle prend qui décide de relancer une agence. Sans ce rappel, il fallait
 * revenir sur la page pour savoir où l'on en était, ou garder un onglet à part et le perdre.
 *
 * Elle ne s'affiche que quand elle a quelque chose à dire : une soirée ouverte, et l'accès au
 * module. Sur la page EOD elle s'efface — répéter à côté ce que l'écran montre déjà serait du
 * bruit. Elle se replie en pastille, et s'écarte d'un geste pour la nuit en cours.
 */
export function VeilleEod(): JSX.Element | null {
  const { moi } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [soiree, setSoiree] = useState<DetailEod | null>(null);
  const [replie, setReplie] = useState(() => lire(CLE_REPLI) === '1');
  const [ecartee, setEcartee] = useState<string | null>(() => lire(CLE_ECARTEE));
  const [instant, setInstant] = useState(() => Date.now());

  const autorise = moi !== null && (moi.transverse || moi.acces.includes(cleAcces('/eod')));
  // Sur la page EOD, la veilleuse n'a rien à ajouter : tout y est déjà, en plus grand.
  const surLaPage = pathname.startsWith('/eod');
  const actif = autorise && !surLaPage;

  const rafraichir = useCallback(async (): Promise<void> => {
    try {
      const { elements } = await eodApi.lister(1, { etat: 'en_cours' });
      const ouverte = elements[0];
      // La liste dit qu'une soirée est ouverte ; le détail seul porte les étapes, donc l'étape en
      // cours et l'heure à laquelle elle a démarré — c'est tout l'objet de la veilleuse.
      setSoiree(ouverte === undefined ? null : await eodApi.detail(ouverte.id));
    } catch {
      // Un rappel qui tombe en panne ne doit pas emporter la page qu'on est en train de lire, ni
      // faire surgir une alerte : on garde le dernier état connu et l'on retentera dans 45 s.
    }
  }, []);

  useEffect(() => {
    if (!actif) return undefined;
    void rafraichir();
    const minuterie = window.setInterval(() => void rafraichir(), RAFRAICHISSEMENT_MS);
    return () => window.clearInterval(minuterie);
  }, [actif, rafraichir]);

  const etape = soiree?.etapes.find(
    (e) => e.nature !== 'valeur' && e.debut !== null && e.fin === null,
  );

  useEffect(() => {
    if (etape === undefined) return undefined;
    const minuterie = window.setInterval(() => setInstant(Date.now()), 1000);
    return () => window.clearInterval(minuterie);
  }, [etape]);

  if (!actif || soiree === null || soiree.id === ecartee) return null;

  const basculer = (): void => {
    setReplie((r) => {
      ecrire(CLE_REPLI, r ? null : '1');
      return !r;
    });
  };

  const ouvrir = (): void => {
    navigate(`/eod/${soiree.id}`);
  };

  if (replie) {
    return (
      <button
        type="button"
        className={styles.pastille}
        onClick={basculer}
        title={`EOD du ${jour(soiree.journee)} — ${soiree.avancement}%`}
        aria-label="Rouvrir la veilleuse EOD"
      >
        <MoonStar size={16} />
        <span className={styles.pastilleValeur}>{soiree.avancement}%</span>
      </button>
    );
  }

  return (
    <aside className={styles.veille} aria-label="Soirée EOD en cours">
      <header className={styles.tete}>
        <MoonStar size={14} className={styles.lune} />
        <span className={styles.journee}>EOD — {jour(soiree.journee)}</span>
        <button
          type="button"
          className={styles.commande}
          onClick={basculer}
          title="Replier"
          aria-label="Replier la veilleuse"
        >
          <ChevronDown size={14} />
        </button>
        <button
          type="button"
          className={styles.commande}
          onClick={() => {
            ecrire(CLE_ECARTEE, soiree.id);
            setEcartee(soiree.id);
          }}
          title="Écarter pour cette soirée"
          aria-label="Écarter la veilleuse pour cette soirée"
        >
          <X size={14} />
        </button>
      </header>

      <button type="button" className={styles.corps} onClick={ouvrir}>
        {etape === undefined ? (
          <span className={styles.attente}>
            {soiree.reste === 0
              ? 'Toutes les étapes sont réglées — la soirée attend sa clôture.'
              : 'Aucune étape démarrée pour le moment.'}
          </span>
        ) : (
          <>
            <span className={styles.section}>{etape.section}</span>
            <span className={styles.etape}>{etape.libelle}</span>
            <span className={styles.chrono}>
              <Timer size={13} className={styles.pouls} aria-hidden="true" />
              {ecoule(etape.debut ?? '', instant)}
              <span className={styles.depuis}>depuis {heure(etape.debut)}</span>
            </span>
          </>
        )}

        <span className={styles.rail}>
          <span className={styles.railRempli} style={{ width: `${soiree.avancement}%` }} />
        </span>
        <span className={styles.pied}>
          <span>
            {soiree.nb_etapes - soiree.reste}/{soiree.nb_etapes} réglées
          </span>
          {soiree.anomalies > 0 && (
            <span className={styles.anomalies}>
              <TriangleAlert size={12} />
              {soiree.anomalies}
            </span>
          )}
        </span>
      </button>
    </aside>
  );
}
