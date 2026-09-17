import { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ChevronDown, MoonStar, Timer, TriangleAlert, X } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { cleAcces } from '@/features/shell/navigation';
import { cx } from '@/common/cx';
import { eodApi, heure, jour, type DetailEod, type EtapeEod } from './eodApi';
import { EVENEMENT_EOD } from './evenements';
import styles from './VeilleEod.module.css';

/** Toutes les 45 s : une soirée se pointe à la main, rien n'y bouge à la seconde. Assez souvent
 *  pour qu'un collègue qui pointe depuis son poste se voie ici, assez rarement pour ne pas
 *  entretenir une conversation permanente avec le serveur. */
const RAFRAICHISSEMENT_MS = 45_000;

/** Combien d'étapes en cours la veilleuse montre avant de compter le reste. Trois tiennent dans
 *  un coin d'écran ; au-delà, le rappel deviendrait une seconde page. */
const MONTREES = 3;

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

/** Les étapes qui tournent : démarrées, pas encore closes. Il y en a couramment plusieurs — les
 *  PART se lancent souvent à la suite sans attendre la fin de la précédente. */
function etapesEnCours(soiree: DetailEod): EtapeEod[] {
  return soiree.etapes.filter((e) => e.nature !== 'valeur' && e.debut !== null && e.fin === null);
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

  const rafraichir = useCallback(async (): Promise<void> => {
    try {
      const { elements } = await eodApi.lister(1, { etat: 'en_cours' });
      if (elements.length === 0) {
        setSoiree(null);
        return;
      }
      // La liste dit QUELLES soirées sont ouvertes ; le détail seul porte les étapes, donc celles
      // qui tournent et depuis quand — c'est tout l'objet de la veilleuse. Quand plusieurs nuits
      // sont ouvertes (une reprise de la veille, un rattrapage), on suit celle où le travail se
      // passe, et non la première venue : c'est là qu'un compteur court.
      const details = await Promise.all(elements.slice(0, 3).map((e) => eodApi.detail(e.id)));
      setSoiree(details.find((d) => etapesEnCours(d).length > 0) ?? details[0] ?? null);
    } catch {
      // Un rappel qui tombe en panne ne doit pas emporter la page qu'on est en train de lire, ni
      // faire surgir une alerte : on garde le dernier état connu et l'on retentera dans 45 s.
    }
  }, []);

  useEffect(() => {
    if (!autorise) return undefined;
    void rafraichir();
    const minuterie = window.setInterval(() => void rafraichir(), RAFRAICHISSEMENT_MS);
    // Le pointage se fait ailleurs dans l'application : on se met à jour dès qu'il crie, sans
    // attendre le tour de l'horloge. On se rafraîchit aussi en changeant de page — c'est le moment
    // où l'on quitte l'écran de pointage, donc celui où la veilleuse redevient utile.
    const surEcriture = (): void => void rafraichir();
    window.addEventListener(EVENEMENT_EOD, surEcriture);
    return () => {
      window.clearInterval(minuterie);
      window.removeEventListener(EVENEMENT_EOD, surEcriture);
    };
  }, [autorise, rafraichir, pathname]);

  const enCours = soiree === null ? [] : etapesEnCours(soiree);
  const compte = enCours.length;

  useEffect(() => {
    if (compte === 0) return undefined;
    const minuterie = window.setInterval(() => setInstant(Date.now()), 1000);
    return () => window.clearInterval(minuterie);
  }, [compte]);

  if (!autorise || soiree === null || soiree.id === ecartee) return null;
  // Aucune étape ne tourne : la veilleuse n'a plus rien à veiller, elle s'efface. Elle ne sert pas
  // à rappeler qu'une soirée existe — la liste EOD le dit — mais à garder un COMPTEUR sous les
  // yeux. Sans compteur, elle ne serait qu'un bandeau de plus. Elle reviendra d'elle-même au
  // prochain « Démarrer », aussitôt : la page la prévient à chaque écriture.
  if (compte === 0) return null;
  // Elle s'efface sur la fiche de la soirée qu'elle suit — y répéter l'écran serait du bruit — mais
  // reste sur la LISTE des soirées, qui ne dit ni quelle étape tourne ni depuis quand. La faire
  // disparaître dès l'URL « /eod » la rendait insaisissable.
  if (pathname === `/eod/${soiree.id}`) return null;

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
        {enCours.slice(0, MONTREES).map((e) => {
          const depart = new Date(e.debut ?? '').getTime();
          const aVenir = depart > instant;
          return (
            <span key={e.id} className={styles.ligne}>
              <span className={styles.section}>{e.section}</span>
              <span className={styles.etape}>{e.libelle}</span>
              <span className={cx(styles.chrono, compte > 1 && styles.chronoSerre)}>
                <Timer size={13} className={styles.pouls} aria-hidden="true" />
                {/* Un départ situé dans le futur — une soirée préparée d'avance — ne se compte
                      pas : afficher « 00:00 » laisserait croire qu'elle vient de démarrer. */}
                {aVenir ? '—' : ecoule(e.debut ?? '', instant)}
                <span className={styles.depuis}>
                  {aVenir ? `prévue ${heure(e.debut)}` : `depuis ${heure(e.debut)}`}
                </span>
              </span>
            </span>
          );
        })}
        {compte > MONTREES && (
          <span className={styles.autres}>+ {compte - MONTREES} autre(s) en cours</span>
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
