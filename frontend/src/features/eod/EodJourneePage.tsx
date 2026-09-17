import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  Check,
  CheckCircle2,
  Circle,
  CircleDot,
  Clock,
  CornerDownRight,
  FileDown,
  FileSpreadsheet,
  FileText,
  MessageSquare,
  MessageSquarePlus,
  Play,
  Plus,
  RotateCcw,
  SlashSquare,
  Table2,
  Timer,
  TriangleAlert,
  X,
  type LucideIcon,
} from 'lucide-react';
import { Button, Modale, StatusBadge, useToast } from '@/design-system/primitives';
import { SelecteurDate } from '@/common/SelecteurDate';
import { ModaleConfirmation } from '@/common/ModaleConfirmation';
import { SelecteurListe } from '@/common/SelecteurListe';
import { BadgeStatut } from '@/common/statuts';
import { cx } from '@/common/cx';
import { ErreurApi, telecharger } from '@/lib/api';
import {
  eodApi,
  estReglee,
  formatHeure,
  grouperParSection,
  heure,
  heureCourante,
  heureObservation,
  jour,
  resoudreHeure,
  type DetailEod,
  type EtapeEod,
  type NatureObservation,
  type NouvelleObservation,
  type StatutEtape,
} from './eodApi';
import { EVENEMENT_EOD } from './evenements';
import { exporterRapportEodPdf } from './rapportPdf';
import { SelecteurHeureEod } from './SelecteurHeureEod';
import styles from './EodJourneePage.module.css';

/** Verdict d'une étape : une couleur ET une forme. Le vert est réservé à ce qui a abouti, le gris
 *  à ce qui ne s'appliquait pas ce soir-là — les confondre ferait passer une étape sautée pour une
 *  étape faite. L'icône dit la même chose sans la couleur : vingt-huit pastilles se parcourent du
 *  regard, et tout le monde ne distingue pas le rouge du vert. */
const VERDICT: Record<StatutEtape, { couleur: string; icone: LucideIcon; mot: string }> = {
  'À faire': { couleur: 'var(--text-muted)', icone: Circle, mot: 'À faire' },
  'En cours': { couleur: 'var(--cat-1)', icone: CircleDot, mot: 'En cours' },
  Complété: { couleur: 'var(--status-ok)', icone: Check, mot: 'Complété' },
  Anomalie: { couleur: 'var(--status-danger)', icone: TriangleAlert, mot: 'Anomalie' },
  'Non applicable': { couleur: 'var(--text-muted)', icone: SlashSquare, mot: 'Non applicable' },
};

/** Verdicts qu'on peut poser à la main, hors pointage. Chacun porte AU SURVOL la couleur de ce
 *  qu'il fait : cinq boutons gris côte à côte n'annoncent rien, et l'on lisait l'infobulle avant
 *  d'oser cliquer. */
const VERDICTS: {
  statut: StatutEtape;
  libelle: string;
  icone: LucideIcon;
  classe: string | undefined;
}[] = [
  {
    statut: 'Anomalie',
    libelle: 'Signaler une anomalie',
    icone: TriangleAlert,
    classe: styles.verdictAnomalie,
  },
  {
    statut: 'Non applicable',
    libelle: 'Sans objet ce soir',
    icone: SlashSquare,
    classe: styles.verdictSansObjet,
  },
];

/** Ce que la modale annonce, selon le geste qui l'a ouverte. Sans cela, « Anomalie » et
 *  « Consigner » ouvraient le même écran : on ne savait plus lequel des deux on avait déclenché. */
const ANNONCE: Record<string, { titre: string; quoi: string }> = {
  Anomalie: {
    titre: 'Signaler une anomalie',
    quoi: 'L’étape passe en « Anomalie » — dites ce qui a coincé.',
  },
  'Non applicable': {
    titre: 'Marquer l’étape sans objet',
    quoi: 'L’étape ne s’applique pas ce soir — dites pourquoi.',
  },
};

/** Au-delà, une étape qui tourne encore n'est plus dans les clous et son compteur vire à l'ambre :
 *  c'est le moment où, dans la vraie nuit, on relance l'agence. */
const ETAPE_LONGUE_MS = 45 * 60_000;

/** Pourquoi une étape ne s'applique pas ce soir. Quatre raisons couvrent la quasi-totalité des
 *  cas, et ce sont toujours les mêmes mots : les retaper chaque nuit produisait « pas EOM », « pas
 *  de fin de mois », « EOM non » — trois formulations pour un seul fait, qu'aucun compte ne peut
 *  plus rapprocher. On les propose donc, sans les imposer : le champ reste libre, une soirée ne
 *  doit pas s'arrêter faute de vocabulaire. */
const MOTIFS_SANS_OBJET = [
  { court: 'EOM', texte: 'Pas une fin de mois (EOM) : la sauvegarde EOM est sans objet ce soir.' },
  { court: 'EOY', texte: 'Pas une fin d’année (EOY) : le traitement annuel ne s’applique pas.' },
  {
    court: 'EOQ',
    texte: 'Pas une fin de trimestre (EOQ) : le traitement trimestriel est sans objet.',
  },
  { court: 'Hors EOD', texte: 'Traitement déjà exécuté hors de la soirée EOD.' },
];

/** La couleur d'une issue de soirée. « Clôturé avec réserves » n'est pas « Clôturé » et « Annulé »
 *  n'est ni l'un ni l'autre : ce sont trois verdicts, et l'écran doit le dire avant le clic. */
const ISSUE: Record<string, string | undefined> = {
  Clôturé: styles.issueSuccès,
  'Clôturé avec réserves': styles.issueReserves,
  Annulé: styles.issueAnnule,
  'En cours': styles.issueDemarrage,
};

/** Pourquoi un champ ne s'ouvre pas : on n'interdit jamais sans le dire. */
const TITRE_LECTURE = 'Le pointage revient aux acteurs de la soirée.';

/** Les trois verdicts qui ne vont pas de soi portent leur mot en clair, à côté du libellé. */
const MARQUES: Record<string, string | undefined> = {
  Anomalie: styles.marqueAnomalie,
  'Non applicable': styles.marqueSansObjet,
  'En cours': styles.marqueEnCours,
};

/** Ce que la modale d'observation est en train de consigner : sur quelle étape, et le cas échéant
 *  le verdict qui l'a déclenchée (posé dans le même appel que l'observation). */
interface Consigne {
  etape: EtapeEod;
  verdict: StatutEtape | null;
}

/** La date relevée, telle qu'elle est stockée (« 17/09/2026 »), ramenée à l'ISO du calendrier.
 *
 * On continue d'ÉCRIRE le format français : c'est celui que le rapport du soir remet à la
 * hiérarchie, et le changer pour l'ISO obligerait à retoucher l'export pour un confort d'écran.
 * Une valeur tapée autrefois à la main et illisible ne casse rien : le calendrier s'ouvre vierge. */
function isoDepuisValeur(valeur: string | null): string | null {
  if (valeur === null) return null;
  const texte = valeur.trim();
  const fr = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(texte);
  if (fr !== null) return `${fr[3]}-${fr[2]}-${fr[1]}`;
  return /^\d{4}-\d{2}-\d{2}$/.test(texte) ? texte : null;
}

/** « 01H12 » → { h: 1, m: 12 }, ou `null` si la saisie ne se lit pas (le champ démarre alors sur
 *  l'instant présent, comme avant). Lecture seule : la résolution de la journée reste au serveur
 *  (`resoudre_relance`), ceci ne sert qu'à préremplir le sélecteur sur ce qui est déjà écrit. */
function heureSaisie(valeur: string): { h: number; m: number } | null {
  const trouve = /^(\d{1,2})\s*[:hH]?\s*(\d{2})$/.exec(valeur.trim());
  if (trouve === null) return null;
  const h = Number(trouve[1]);
  const m = Number(trouve[2]);
  return h <= 23 && m <= 59 ? { h, m } : null;
}

/** Le temps écoulé depuis le démarrage — « 04:21 », « 1:12:40 ».
 *
 * « 09H01 » ne répond pas à « ça fait combien de temps que ça tourne ? », qui est LA question de
 * la nuit : c'est elle qui décide de relancer une agence, et on la posait montre en main. */
function chrono(debut: string, maintenant: number): string {
  const total = Math.max(0, Math.floor((maintenant - new Date(debut).getTime()) / 1000));
  const h = Math.floor(total / 3600);
  const mm = String(Math.floor((total % 3600) / 60)).padStart(2, '0');
  const ss = String(total % 60).padStart(2, '0');
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

/** Combien de temps l'étape a duré — « 12 min », « 1 h 05 ».
 *
 * C'est ce que la DSI relit pour savoir quelle étape retarde les autres ; le rapport papier ne le
 * donnait qu'en soustrayant deux heures de tête, la nuit, ce que personne ne faisait. */
function duree(debut: string, fin: string): string {
  const minutes = Math.round((new Date(fin).getTime() - new Date(debut).getTime()) / 60_000);
  if (minutes < 0) return '';
  if (minutes < 60) return `${minutes} min`;
  return `${Math.floor(minutes / 60)} h ${String(minutes % 60).padStart(2, '0')}`;
}

/** LA BANDE DE LA NUIT — le journal d'une étape, réduit à sa ligne de temps.
 *
 * Empilées en paragraphes, trois observations occupaient plus de place que l'étape elle-même : sur
 * vingt-huit lignes, le déroulé disparaissait sous ses commentaires, et une nuit bavarde devenait
 * illisible. Or ce qu'on cherche d'abord n'est pas le texte : c'est **combien de fois ça a coincé,
 * et à quelle heure**. Chaque observation devient donc un jeton horodaté, tous sur une seule ligne.
 * Le texte, lui, s'ouvre au clic — sous la bande, sans quitter l'étape ni ouvrir de modale, comme
 * les justifications d'avancement ailleurs dans l'application.
 *
 * Les lignes ne se corrigent pas et ne s'effacent pas — l'API n'offre pas le geste. Une erreur se
 * rattrape par l'observation suivante, qui la date et la signe (principe n° 4). */
function Journal({ etape }: { etape: EtapeEod }): JSX.Element | null {
  const [ouverte, setOuverte] = useState<string | null>(null);
  if (etape.observations.length === 0) return null;
  const lue = etape.observations.find((o) => o.id === ouverte) ?? null;

  return (
    <div className={styles.trace}>
      <div className={styles.traceRang}>
        {etape.observations.map((o) => (
          <button
            type="button"
            key={o.id}
            className={cx(
              styles.jeton,
              o.nature === 'incident' && styles.jetonIncident,
              o.id === ouverte && styles.jetonOuvert,
            )}
            onClick={() => setOuverte(o.id === ouverte ? null : o.id)}
            aria-expanded={o.id === ouverte}
            title={o.texte}
          >
            {o.nature === 'incident' ? <Building2 size={11} /> : <MessageSquare size={11} />}
            {heureObservation(o)}
            {o.nature === 'incident' && o.agence !== null && (
              <span className={styles.jetonAgence}>{o.agence}</span>
            )}
          </button>
        ))}
      </div>
      {lue !== null && (
        <div
          className={cx(styles.traceCarte, lue.nature === 'incident' && styles.traceCarteIncident)}
        >
          <span className={styles.traceTexte}>{lue.texte}</span>
          <span className={styles.traceSignature}>
            {heureObservation(lue)}
            {lue.agence !== null && ` · ${lue.agence}`}
            {lue.auteur !== null && ` · ${lue.auteur}`}
          </span>
        </div>
      )}
    </div>
  );
}

export function EodJourneePage(): JSX.Element {
  const { id = '' } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { notifier } = useToast();
  const [soiree, setSoiree] = useState<DetailEod | null>(null);
  const [chargement, setChargement] = useState(true);
  const [occupe, setOccupe] = useState<string | null>(null);
  const [ajout, setAjout] = useState(false);
  const [libelleNouveau, setLibelleNouveau] = useState('');
  const [sectionNouvelle, setSectionNouvelle] = useState('Tâches additionnelles');
  const [aSupprimer, setASupprimer] = useState<EtapeEod | null>(null);
  const [transitionVisee, setTransitionVisee] = useState<string | null>(null);
  const [noteTransition, setNoteTransition] = useState('');
  const [exportOuvert, setExportOuvert] = useState(false);
  const [exportEnCours, setExportEnCours] = useState(false);

  // --- Consigner une observation ---------------------------------------------------------------
  const [consigne, setConsigne] = useState<Consigne | null>(null);
  const [natureObs, setNatureObs] = useState<NatureObservation>('note');
  const [agence, setAgence] = useState<string | null>(null);
  const [relance, setRelance] = useState('');
  const [texteObs, setTexteObs] = useState('');
  const [agences, setAgences] = useState<string[]>([]);
  // L'étape dont on s'apprête à reprendre le pointage. Le geste efface une heure : il se confirme.
  const [aReprendre, setAReprendre] = useState<EtapeEod | null>(null);
  // L'instant courant, pour le compteur des étapes démarrées.
  const [instant, setInstant] = useState(() => Date.now());

  const charger = useCallback(async (): Promise<void> => {
    setChargement(true);
    try {
      setSoiree(await eodApi.detail(id));
    } finally {
      setChargement(false);
    }
  }, [id]);

  useEffect(() => {
    void charger();
  }, [charger]);

  /** La minuterie ne bat que s'il y a quelque chose à compter : une soirée close n'entretient
   *  aucun compteur, et un écran laissé ouvert au bureau ne réveille rien. */
  const compteurEnCours =
    soiree?.etapes.some((e) => e.nature !== 'valeur' && e.debut !== null && e.fin === null) ===
    true;

  useEffect(() => {
    if (!compteurEnCours) return undefined;
    setInstant(Date.now());
    const minuterie = window.setInterval(() => setInstant(Date.now()), 1000);
    return () => window.clearInterval(minuterie);
  }, [compteurEnCours]);

  // Le réseau d'agences n'est chargé qu'à la première ouverture de la modale : c'est un référentiel
  // stable, et l'écran de pointage n'en a pas besoin pour s'afficher.
  useEffect(() => {
    if (consigne === null || agences.length > 0) return;
    void eodApi.agences().then(setAgences);
  }, [consigne, agences.length]);

  // L'agence choisie librement doit figurer parmi les options, sinon le champ afficherait de
  // nouveau son indication après l'avoir enregistrée.
  const optionsAgences = useMemo(
    () =>
      [...new Set(agence === null ? agences : [...agences, agence])].map((a) => ({
        valeur: a,
        libelle: a,
      })),
    [agences, agence],
  );

  /** Le déroulé par section, avec de quoi nourrir le sommaire : combien d'étapes sont réglées, et
   *  si la section porte une anomalie. C'est la vue d'ensemble que vingt-huit lignes ne donnent
   *  pas — à 2 h du matin, « où en suis-je » se répond par « PART 3 à moitié faite ». */
  const sections = useMemo(() => {
    if (soiree === null) return [];
    return grouperParSection(soiree.etapes).map((groupe, rang) => ({
      ...groupe,
      ancre: `eod-section-${rang}`,
      reglees: groupe.etapes.filter(estReglee).length,
      anomalie: groupe.etapes.some((e) => e.statut === 'Anomalie'),
      // La section où le travail se joue : celle qui porte l'étape en cours, à défaut la première
      // qui n'est pas finie.
      active:
        groupe.etapes.some((e) => e.statut === 'En cours') ||
        groupe.etapes.some((e) => !estReglee(e)),
    }));
  }, [soiree]);

  /** Une seule section porte la marque « ici » : la première inachevée. Les marquer toutes ferait
   *  du repère un décor. */
  const sectionCourante = sections.find((s) => s.active)?.ancre ?? null;

  /** Toute écriture renvoie la soirée entière : avancement, anomalies et clôture conseillée
   *  changent à chaque geste, et les recalculer à l'écran les ferait diverger du serveur. */
  const agir = async (cle: string, action: () => Promise<DetailEod>): Promise<void> => {
    setOccupe(cle);
    try {
      setSoiree(await action());
      // La veilleuse vit dans le shell, hors de cet arbre : sans un mot d'elle à elle, elle
      // gardait son compteur en marche jusqu'à son prochain rafraîchissement — quarante-cinq
      // secondes à afficher une étape qu'on vient de clore. Un évènement de fenêtre plutôt qu'un
      // état global : deux écrans qui ne se connaissent pas n'ont pas à partager un magasin.
      window.dispatchEvent(new Event(EVENEMENT_EOD));
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Action impossible.', 'erreur');
    } finally {
      setOccupe(null);
    }
  };

  if (chargement && soiree === null) {
    return <div className={styles.etatVide}>Chargement…</div>;
  }
  if (soiree === null) {
    return <div className={styles.etatVide}>Soirée introuvable.</div>;
  }

  const peutEcrire = soiree.permissions.peut_travailler;
  const pointee = soiree.nb_etapes - soiree.reste;

  /** Le PDF se compose dans le navigateur, à partir de la soirée déjà chargée : aucun aller-retour
   *  serveur, et le document sort même si le réseau vient de lâcher — la nuit, ça compte. */
  const exporterPdf = async (): Promise<void> => {
    setExportEnCours(true);
    try {
      await exporterRapportEodPdf(soiree);
      setExportOuvert(false);
    } catch {
      notifier("Le rapport n'a pas pu être composé.", 'erreur');
    } finally {
      setExportEnCours(false);
    }
  };

  const telechargerTableur = (format: 'xlsx' | 'csv'): void => {
    void telecharger(`/eod/${id}/rapport?format=${format}`);
    setExportOuvert(false);
  };

  /** Ouvre la modale d'observation. Un verdict la pré-règle en « incident » : une anomalie pendant
   *  les PART vient presque toujours d'une agence qui bloque — et c'est d'elle que le rapport
   *  parlera. Un clic suffit pour repasser en simple observation. */
  const consigner = (etape: EtapeEod, verdict: StatutEtape | null): void => {
    setConsigne({ etape, verdict });
    setNatureObs(verdict === 'Anomalie' ? 'incident' : 'note');
    setAgence(null);
    setRelance(heureCourante());
    setTexteObs('');
  };

  const fermerConsigne = (): void => setConsigne(null);

  /** Pose le verdict et l'observation en un seul appel quand les deux vont ensemble — et le
   *  verdict seul quand l'étape porte déjà son explication. */
  const envoyerObservation = async (): Promise<void> => {
    if (consigne === null) return;
    const { etape, verdict } = consigne;
    const texte = texteObs.trim();
    if (verdict !== null && texte === '') {
      await agir(`statut:${etape.id}`, () => eodApi.majEtape(id, etape.id, { statut: verdict }));
      fermerConsigne();
      return;
    }
    const observation: NouvelleObservation = {
      nature: natureObs,
      texte,
      agence: natureObs === 'incident' ? agence : null,
      relance: natureObs === 'incident' ? relance.trim() : null,
    };
    await agir(`observation:${etape.id}`, () =>
      verdict === null
        ? eodApi.observer(id, etape.id, observation)
        : eodApi.majEtape(id, etape.id, { statut: verdict, observation }),
    );
    fermerConsigne();
  };

  /** Pose un verdict.
   *
   * « Anomalie » et « Non applicable » ouvrent TOUJOURS la modale. Le même bouton, auparavant,
   * tantôt l'ouvrait, tantôt basculait l'étape sans rien demander — selon qu'une observation
   * existait déjà, ce que rien à l'écran ne disait. Un geste qui change de nature au gré d'un état
   * invisible ne s'apprivoise pas : on finit par cliquer en espérant.
   *
   * Quand l'explication est déjà au journal, la modale s'ouvre quand même mais n'exige plus rien —
   * elle le dit, et son bouton devient « Poser le verdict ». */
  const poserVerdict = (etape: EtapeEod, statut: StatutEtape): void => {
    if (statut === 'Anomalie' || statut === 'Non applicable') {
      consigner(etape, statut);
      return;
    }
    void agir(`statut:${etape.id}`, () => eodApi.majEtape(id, etape.id, { statut }));
  };

  /** REPRENDRE une étape : on s'est trompé de verdict, ou l'étape a été close trop tôt et le
   *  traitement repart.
   *
   *  Ce que ça fait, et pourquoi : l'étape repasse « En cours », son heure de FIN est effacée, son
   *  heure de DÉBUT est conservée. Le compteur repart donc de l'heure de départ d'origine et
   *  continue de courir — c'est la même étape qui se poursuit, pas une nouvelle. Remettre le
   *  compteur à zéro ferait disparaître le temps déjà passé, qui est précisément ce que la DSI
   *  relit au matin. Le journal, lui, ne bouge pas : ce qui a été consigné reste.
   *
   *  Une étape jamais démarrée n'a rien à reprendre : elle retombe simplement « À faire ». */
  const reprendre = (etape: EtapeEod): Promise<void> =>
    agir(`reprise:${etape.id}`, () =>
      eodApi.majEtape(
        id,
        etape.id,
        etape.debut === null
          ? { statut: 'À faire' }
          : etape.fin === null
            ? // Étape en cours : on annule le démarrage. Le compteur s'arrête et l'heure de départ
              // s'efface — c'est un clic de trop sur une liste de vingt-huit lignes, pas un travail
              // qui a eu lieu.
              { statut: 'À faire', vider_debut: true }
            : { statut: 'En cours', vider_fin: true },
      ),
    );

  // Ce que la modale d'observation annonce, et ce qu'elle exige. L'explication n'est obligatoire
  // que si l'étape n'en porte pas déjà une : corriger un verdict ne doit pas obliger à retaper ce
  // qui est écrit deux lignes plus bas.
  const annonce = consigne?.verdict != null ? ANNONCE[consigne.verdict] : undefined;
  const expliqueDeja = consigne !== null && consigne.etape.observations.length > 0;
  const texteVide = texteObs.trim().length === 0;
  const verdictSeul = consigne?.verdict != null && texteVide;
  const observationComplete =
    texteObs.trim().length >= 2 &&
    (natureObs !== 'incident' || ((agence ?? '').trim() !== '' && relance.trim() !== ''));
  const posePossible = verdictSeul ? expliqueDeja : observationComplete;
  // « Sans objet » ne se raconte pas comme un incident d'agence : le choix de nature n'aurait ici
  // qu'une réponse. On ne montre pas un aiguillage à une seule voie.
  const naturesOffertes = consigne?.verdict !== 'Non applicable';
  const IconeAnnonce =
    consigne?.verdict === 'Anomalie'
      ? TriangleAlert
      : consigne?.verdict === 'Non applicable'
        ? SlashSquare
        : MessageSquarePlus;

  const allerA = (ancre: string): void =>
    document.getElementById(ancre)?.scrollIntoView({ behavior: 'smooth', block: 'start' });

  const transitionner = async (vers: string): Promise<void> => {
    // Clore une nuit inachevée reste possible — une soirée peut être arrêtée pour de bonnes
    // raisons — mais le serveur exige alors une note. On la demande avant d'envoyer, plutôt que
    // de laisser l'opérateur se heurter à un refus.
    const clot = ['Clôturé', 'Clôturé avec réserves', 'Annulé'].includes(vers);
    if (clot && soiree.cloture_conseillee === null && noteTransition.trim() === '') {
      setTransitionVisee(vers);
      return;
    }
    await agir(`transition:${vers}`, () =>
      eodApi.transition(id, vers, noteTransition || undefined),
    );
    setTransitionVisee(null);
    setNoteTransition('');
  };

  return (
    <div className={styles.page}>
      <header className={styles.entete}>
        <div className={styles.identite}>
          <button
            type="button"
            className={styles.retour}
            onClick={() => navigate('/eod')}
            aria-label="Retour à la liste des soirées"
          >
            <ArrowLeft size={18} />
          </button>
          <div>
            <div className={styles.reference}>{soiree.reference}</div>
            <h1 className={styles.titre}>
              EOD — {jour(soiree.journee)}
              <BadgeStatut statut={soiree.statut} module="eod" />
              {soiree.categorie !== null && (
                <StatusBadge couleur="var(--cat-6)">{soiree.categorie}</StatusBadge>
              )}
            </h1>
          </div>
        </div>
        <div className={styles.actions}>
          {/* Une fois la soirée close, il ne reste qu'un geste : rendre compte. Le bouton passe
              alors au premier plan — tant qu'il y a des étapes à pointer, il ne doit pas
              concurrencer la clôture. */}
          <Button
            variante={soiree.transitions_possibles.length === 0 ? 'primaire' : 'secondaire'}
            onClick={() => setExportOuvert(true)}
          >
            <FileDown size={16} />
            Rapport du soir
          </Button>
          {/* Chaque issue porte sa couleur : la nuit s'est bien passée (vert), elle laisse des
              réserves (ambre), elle n'a pas eu lieu (rouge). Quatre boutons blancs alignés
              donnaient trois décisions de portées très différentes pour un même geste — et la plus
              lourde, « Annulé », ne se distinguait en rien de la plus banale. Celle que les étapes
              justifient est en outre soulignée : le serveur conseille, l'écran le montre. */}
          {peutEcrire &&
            soiree.transitions_possibles.map((vers) => (
              <Button
                key={vers}
                variante="secondaire"
                className={cx(
                  styles.issue,
                  ISSUE[vers],
                  vers === soiree.cloture_conseillee && styles.issueConseillee,
                )}
                disabled={occupe !== null}
                onClick={() => void transitionner(vers)}
              >
                {vers}
              </Button>
            ))}
        </div>
      </header>

      {/* La nuit en un regard. L'avancement tient la place d'honneur : c'est la question qu'on pose
          en entrant. Les trois compteurs suivent — en quatre cartes de même poids, aucun des quatre
          chiffres ne primait, et l'on cherchait le sien à chaque fois. */}
      <section className={styles.sommet}>
        <div className={styles.progression}>
          <div className={styles.progressionTete}>
            <span className={cx(styles.pourcent, soiree.avancement === 100 && styles.pourcentFini)}>
              {soiree.avancement}%
            </span>
            <span className={styles.progressionQuoi}>
              {pointee}/{soiree.nb_etapes} étapes réglées
            </span>
          </div>
          <div
            className={styles.rail}
            role="progressbar"
            aria-valuenow={soiree.avancement}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Avancement du déroulé"
          >
            <div
              className={cx(styles.railRempli, soiree.avancement === 100 && styles.railComplet)}
              style={{ width: `${soiree.avancement}%` }}
            />
          </div>
          <div className={styles.plage}>
            <Clock size={14} />
            <span className={styles.plageHeures}>
              {soiree.debut_effectif === null ? '—' : heure(soiree.debut_effectif)}
              {' → '}
              {soiree.fin_effective === null ? '…' : heure(soiree.fin_effective)}
            </span>
            <span>
              {soiree.responsable === null
                ? 'aucun opérateur désigné'
                : `${soiree.responsable.prenom} ${soiree.responsable.nom}`}
            </span>
          </div>
        </div>

        <div className={styles.compteurs}>
          <div className={styles.compteur}>
            <span className={styles.compteurTitre}>
              <TriangleAlert size={12} />
              Anomalies
            </span>
            <strong
              className={cx(
                styles.compteurValeur,
                soiree.anomalies > 0 ? styles.compteurAlerte : styles.compteurCalme,
              )}
            >
              {soiree.anomalies}
            </strong>
            <span className={styles.compteurQuoi}>
              {soiree.anomalies > 0 ? 'à expliquer au rapport' : 'aucune anomalie relevée'}
            </span>
          </div>

          {/* Distincte des anomalies, et pas déductible d'elles : une agence peut être relancée
              sans que l'étape finisse en anomalie, et une anomalie de batch ne touche parfois
              aucune agence. C'est le chiffre qui dit ce que nos nuits coûtent au réseau. */}
          <div className={styles.compteur}>
            <span className={styles.compteurTitre}>
              <Building2 size={12} />
              Relances d’agence
            </span>
            <strong
              className={cx(
                styles.compteurValeur,
                soiree.incidents > 0 ? styles.compteurAttention : styles.compteurCalme,
              )}
            >
              {soiree.incidents}
            </strong>
            <span className={styles.compteurQuoi}>
              {soiree.incidents > 0 ? 'agences relancées cette nuit' : 'aucune agence n’a bloqué'}
            </span>
          </div>

          <div className={styles.compteur}>
            <span className={styles.compteurTitre}>
              <Circle size={12} />
              Reste à pointer
            </span>
            <strong
              className={cx(styles.compteurValeur, soiree.reste === 0 && styles.compteurCalme)}
            >
              {soiree.reste}
            </strong>
            <span className={styles.compteurQuoi}>
              {soiree.reste === 0 ? 'le déroulé est complet' : 'étapes sans verdict'}
            </span>
          </div>
        </div>
      </section>

      {soiree.cloture_conseillee !== null && soiree.transitions_possibles.length > 0 && (
        <p className={styles.conseil}>
          <CheckCircle2 size={16} className={styles.conseilIcone} />
          Toutes les étapes sont réglées : la soirée peut être close en «&nbsp;
          {soiree.cloture_conseillee}&nbsp;».
        </p>
      )}

      <div className={styles.corps}>
        {/* Le sommaire : la vue d'ensemble que vingt-huit lignes ne donnent pas, et la navigation
            qui évite de faire défiler pour retrouver une section. */}
        <nav className={styles.sommaire} aria-label="Sections du déroulé">
          <span className={styles.sommaireTitre}>Déroulé</span>
          {sections.map((s) => (
            <button
              type="button"
              key={s.ancre}
              className={cx(styles.lien, s.ancre === sectionCourante && styles.lienCourant)}
              onClick={() => allerA(s.ancre)}
              aria-current={s.ancre === sectionCourante ? 'true' : undefined}
            >
              <span className={styles.lienNom}>{s.titre}</span>
              <span
                className={cx(
                  styles.lienCompte,
                  s.reglees === s.etapes.length && !s.anomalie && styles.lienFait,
                )}
              >
                {s.reglees}/{s.etapes.length}
              </span>
              <span className={styles.lienRail}>
                <span
                  className={cx(styles.lienRailRempli, s.anomalie && styles.lienRailAnomalie)}
                  style={{ width: `${(s.reglees / s.etapes.length) * 100}%` }}
                />
              </span>
            </button>
          ))}
        </nav>

        <div className={styles.deroule}>
          {sections.map((groupe) => (
            <section key={groupe.ancre} id={groupe.ancre} className={styles.section}>
              <div className={styles.sectionEntete}>
                <h2 className={styles.sectionTitre}>{groupe.titre}</h2>
                <span
                  className={cx(
                    styles.sectionCompte,
                    groupe.reglees === groupe.etapes.length && styles.sectionFaite,
                  )}
                >
                  {groupe.reglees === groupe.etapes.length && <Check size={12} />}
                  {groupe.reglees}/{groupe.etapes.length} réglées
                </span>
              </div>

              {groupe.etapes.map((e) => {
                const verdict = VERDICT[e.statut];
                const Pastille = verdict.icone;
                const marque = MARQUES[e.statut];
                return (
                  <div
                    key={e.id}
                    className={cx(
                      styles.etape,
                      e.statut === 'En cours' && styles.etapeActive,
                      e.statut === 'Anomalie' && styles.etapeAnomalie,
                      e.statut === 'Non applicable' && styles.etapeSansObjet,
                      // Une relance se range sous l'étape qu'elle rejoue, en retrait : on lit
                      // d'un coup d'œil qu'elle n'est pas une étape du déroulé mais sa reprise.
                      e.relance_de !== null && styles.etapeRelance,
                    )}
                  >
                    <span
                      className={cx(styles.pastille, estReglee(e) && styles.pastilleReglee)}
                      style={{ color: verdict.couleur }}
                      title={verdict.mot}
                      /* `role="img"` et non un simple aria-label : sur un span neutre, le nom
                         accessible serait ignoré, et la pastille ne dirait rien au lecteur
                         d'écran — elle porte pourtant le verdict de l'étape. */
                      role="img"
                      aria-label={`Verdict : ${verdict.mot}`}
                    >
                      <Pastille size={12} />
                    </span>

                    <div className={styles.intitule}>
                      <span className={styles.libelle}>
                        {e.relance_de !== null && (
                          <CornerDownRight
                            size={13}
                            className={styles.coude}
                            aria-label="Relance de l’étape précédente"
                          />
                        )}
                        {e.libelle}
                      </span>
                      {marque !== undefined && (
                        <span className={cx(styles.marque, marque)}>{verdict.mot}</span>
                      )}
                      {e.aide !== null && <span className={styles.aide}>{e.aide}</span>}
                    </div>

                    <div className={styles.pointage}>
                      {e.nature === 'valeur' ? (
                        // « System Date » : ce qui compte n'est pas quand on a regardé, mais ce
                        // qu'on a lu.
                        <span className={styles.colValeur}>
                          {/* Un calendrier, et non un champ libre : on relève une DATE, à 2 h du
                              matin, et « 17/9/26 », « 17-09-2026 » ou une coquille à un chiffre
                              près partaient droit dans le rapport du soir. Le mois s'y lit en
                              toutes lettres, en français. */}
                          <SelecteurDate
                            valeur={isoDepuisValeur(e.valeur)}
                            onChange={(iso) =>
                              void agir(`valeur:${e.id}`, () =>
                                eodApi.majEtape(id, e.id, {
                                  valeur: iso === null ? '' : jour(iso),
                                  statut: iso === null ? 'À faire' : 'Complété',
                                }),
                              )
                            }
                            placeholder="jj/mm/aaaa"
                            desactive={!peutEcrire}
                            titreDesactive={TITRE_LECTURE}
                            /* Ici, choisir la date EST le travail : une fois relevée, le champ
                               passe au vert comme une étape complétée — on voit d'un coup d'œil,
                               en descendant le déroulé, si la bascule a bien été constatée. */
                            acquise
                          />
                        </span>
                      ) : (
                        <>
                          <span className={styles.colDebut}>
                            {e.debut !== null ? (
                              <span className={styles.horodate}>{heure(e.debut)}</span>
                            ) : /* Une étape réglée ne se démarre pas : « Non applicable » gardait
                                   un « Démarrer » qui invitait à pointer ce qu'on venait de
                                   déclarer sans objet. Pour la rouvrir, on la reprend — c'est le
                                   geste prévu pour ça, et il se confirme. */
                            peutEcrire && !estReglee(e) ? (
                              <SelecteurHeureEod
                                desactive={occupe !== null}
                                onChoisir={(hh, mm) => {
                                  const debut = resoudreHeure(hh, mm);
                                  void agir(`debut:${e.id}`, () =>
                                    // « Maintenant » retombe pile sur le geste d'avant (un clic,
                                    // l'instant présent) ; choisir une heure passe par le même
                                    // PATCH que « Reprendre », pour rattraper une ligne oubliée
                                    // sans redémarrer l'étape de zéro.
                                    eodApi.majEtape(id, e.id, {
                                      statut: 'En cours',
                                      debut: debut.toISOString(),
                                    }),
                                  );
                                }}
                                trigger={({ onClick, ref }) => (
                                  <button
                                    ref={ref}
                                    type="button"
                                    className={styles.pointer}
                                    disabled={occupe !== null}
                                    onClick={onClick}
                                  >
                                    <Play size={12} /> Démarrer
                                  </button>
                                )}
                              />
                            ) : (
                              <span className={styles.vide}>—</span>
                            )}
                          </span>

                          <span className={styles.colFin}>
                            {e.fin !== null ? (
                              <span className={styles.horodate}>
                                <ArrowRight size={12} className={styles.fleche} />
                                {heure(e.fin)}
                              </span>
                            ) : /* « Terminer » reste offert même sur une étape réglée qui a
                                   démarré : ce qu'on a commencé doit pouvoir se clore, et une
                                   anomalie constatée en cours de route n'y change rien. */
                            e.debut !== null && peutEcrire ? (
                              <SelecteurHeureEod
                                desactive={occupe !== null}
                                onChoisir={(hh, mm) => {
                                  const fin = resoudreHeure(hh, mm);
                                  void agir(`fin:${e.id}`, () =>
                                    // Même chemin que le rattrapage d'un début : le PATCH
                                    // générique, jamais une seconde route pour la même heure.
                                    eodApi.majEtape(id, e.id, {
                                      statut: 'Complété',
                                      fin: fin.toISOString(),
                                    }),
                                  );
                                }}
                                trigger={({ onClick, ref }) => (
                                  <button
                                    ref={ref}
                                    type="button"
                                    className={styles.pointer}
                                    disabled={occupe !== null}
                                    onClick={onClick}
                                  >
                                    <Check size={12} /> Terminer
                                  </button>
                                )}
                              />
                            ) : (
                              <span className={styles.vide}>—</span>
                            )}
                          </span>

                          {/* La même colonne répond toujours à « combien de temps » : le temps
                              écoulé tant que ça tourne, la durée une fois l'étape close. */}
                          <span className={styles.colDuree}>
                            {e.debut !== null && e.fin !== null ? (
                              <span className={styles.duree}>{duree(e.debut, e.fin)}</span>
                            ) : e.debut !== null ? (
                              <span
                                className={cx(
                                  styles.chrono,
                                  instant - new Date(e.debut).getTime() > ETAPE_LONGUE_MS &&
                                    styles.chronoLong,
                                )}
                                title="Temps écoulé depuis le démarrage"
                              >
                                <Timer size={12} className={styles.pouls} aria-hidden="true" />
                                {chrono(e.debut, instant)}
                              </span>
                            ) : null}
                          </span>
                        </>
                      )}

                      {peutEcrire &&
                        (() => {
                          // Signaler une anomalie ou consigner une observation suppose que
                          // quelque chose s'est passé — donc que l'étape a démarré. « Sans objet »
                          // fait exception : décider qu'une étape ne s'applique pas ce soir-là ne
                          // demande pas de l'avoir pointée d'abord (« Backup before EOM » un soir
                          // ordinaire, par exemple). Les étapes « à valeur » (System Date) n'ont
                          // pas de démarrage : la règle ne les concerne pas.
                          const nonDemarree = e.nature === 'horaire' && e.debut === null;
                          const raisonGel = 'Démarrez l’étape avant d’agir sur elle.';
                          return (
                            <div className={styles.verdicts}>
                              {/* Reprendre : seulement là où il y a quelque chose à reprendre —
                                  une étape qui n'a jamais démarré n'a pas de pointage à défaire. */}
                              {(estReglee(e) || e.debut !== null) && (
                                <button
                                  type="button"
                                  className={cx(styles.verdict, styles.verdictReprise)}
                                  title={
                                    e.debut !== null && e.fin === null
                                      ? 'Annuler le démarrage'
                                      : 'Reprendre l’étape (le pointage repart)'
                                  }
                                  aria-label={`Reprendre l’étape « ${e.libelle} »`}
                                  disabled={occupe !== null}
                                  onClick={() => setAReprendre(e)}
                                >
                                  <RotateCcw size={13} />
                                </button>
                              )}
                              {VERDICTS.filter((v) => v.statut !== e.statut).map((v) => {
                                const gele = nonDemarree && v.statut === 'Anomalie';
                                return (
                                  <button
                                    type="button"
                                    key={v.statut}
                                    className={cx(
                                      styles.verdict,
                                      v.classe,
                                      gele && styles.verdictGele,
                                    )}
                                    title={gele ? raisonGel : v.libelle}
                                    aria-label={`${v.libelle} — ${e.libelle}`}
                                    disabled={occupe !== null || gele}
                                    onClick={() => poserVerdict(e, v.statut)}
                                  >
                                    <v.icone size={13} />
                                  </button>
                                );
                              })}
                              <button
                                type="button"
                                className={cx(
                                  styles.verdict,
                                  styles.verdictObservation,
                                  nonDemarree && styles.verdictGele,
                                )}
                                title={nonDemarree ? raisonGel : 'Consigner une observation'}
                                aria-label={`Consigner une observation — ${e.libelle}`}
                                disabled={occupe !== null || nonDemarree}
                                onClick={() => consigner(e, null)}
                              >
                                <MessageSquarePlus size={13} />
                              </button>
                              {/* Retirer l'étape : le geste le plus destructeur de la ligne, donc
                                  le dernier, séparé des verdicts et confirmé avant d'agir. Ni
                                  progression ni observation : jamais gelé par le démarrage. */}
                              <button
                                type="button"
                                className={cx(
                                  styles.verdict,
                                  styles.verdictRetrait,
                                  styles.retrait,
                                )}
                                title="Retirer cette étape de la soirée"
                                aria-label={`Retirer l’étape « ${e.libelle} »`}
                                disabled={occupe !== null}
                                onClick={() => setASupprimer(e)}
                              >
                                <X size={13} />
                              </button>
                            </div>
                          );
                        })()}
                    </div>

                    {e.observations.length > 0 && (
                      <div className={styles.dessous}>
                        <Journal etape={e} />
                      </div>
                    )}
                  </div>
                );
              })}
            </section>
          ))}

          {peutEcrire && (
            <div className={styles.piedDeroule}>
              <Button variante="secondaire" onClick={() => setAjout(true)}>
                <Plus size={16} />
                Ajouter une étape
              </Button>
              <span className={styles.aparte}>
                Une vérification exceptionnelle, un rattrapage : elle n’entre pas dans le déroulé de
                référence.
              </span>
            </div>
          )}
        </div>
      </div>

      <Modale
        ouverte={exportOuvert}
        onFermer={() => setExportOuvert(false)}
        titre="Rapport du soir"
        pied={
          <Button variante="secondaire" onClick={() => setExportOuvert(false)}>
            Fermer
          </Button>
        }
      >
        <div className={cx(styles.contexte, soiree.reste > 0 && styles.contexteClore)}>
          {soiree.reste > 0 ? (
            <TriangleAlert size={18} className={styles.contexteIcone} />
          ) : (
            <CheckCircle2 size={18} className={styles.contexteIcone} />
          )}
          <div className={styles.contexteCorps}>
            <span className={styles.contexteQuoi}>
              {soiree.reste > 0
                ? `${soiree.reste} étape(s) ne sont pas encore réglées`
                : 'La nuit est complète'}
            </span>
            <span className={styles.contexteOu}>
              {soiree.reste > 0
                ? 'Le rapport les montrera « À faire » — il dit la nuit telle qu’elle a été pointée.'
                : 'Le rapport rend compte du déroulé entier, anomalies et relances comprises.'}
            </span>
          </div>
        </div>
        <div className={styles.formats}>
          <button
            type="button"
            className={cx(styles.format, styles.formatPhare)}
            disabled={exportEnCours}
            onClick={() => void exporterPdf()}
          >
            <FileText size={18} />
            <span className={styles.formatNom}>{exportEnCours ? 'Composition…' : 'PDF'}</span>
            <span className={styles.formatMarque}>le document du soir</span>
            <span className={styles.formatQuoi}>
              Le document qui se remet et s’archive : en-tête AFG Bank Mali, synthèse de la nuit,
              déroulé complet et emplacements de visa.
            </span>
          </button>
          <button
            type="button"
            className={styles.format}
            onClick={() => telechargerTableur('xlsx')}
          >
            <FileSpreadsheet size={18} />
            <span className={styles.formatNom}>Excel</span>
            <span className={styles.formatQuoi}>
              Le tableau tel que la Production le lit depuis toujours, pour retraiter les heures.
            </span>
          </button>
          <button type="button" className={styles.format} onClick={() => telechargerTableur('csv')}>
            <Table2 size={18} />
            <span className={styles.formatNom}>CSV</span>
            <span className={styles.formatQuoi}>Les mêmes lignes, sans mise en forme.</span>
          </button>
        </div>
      </Modale>

      {/* Consigner : une observation s'ajoute au journal, elle n'écrase rien — et quand c'est une
          agence qui a bloqué, elle porte les trois informations que la hiérarchie réclame au
          matin : laquelle, à quelle heure on a relancé, ce qui a été fait. */}
      <Modale
        ouverte={consigne !== null}
        onFermer={fermerConsigne}
        titre={annonce?.titre ?? 'Consigner une observation'}
        pied={
          <>
            <Button variante="secondaire" onClick={fermerConsigne}>
              Annuler
            </Button>
            <Button
              disabled={occupe !== null || !posePossible}
              onClick={() => void envoyerObservation()}
            >
              {verdictSeul ? 'Poser le verdict' : 'Consigner'}
            </Button>
          </>
        }
      >
        {/* La bannière nomme le geste et porte sa couleur : « Anomalie » et « Consigner »
            ouvraient le même écran, et l'on ne savait plus lequel des deux on avait déclenché. */}
        {consigne !== null && (
          <div
            className={cx(
              styles.contexte,
              consigne.verdict === 'Anomalie' && styles.contexteAnomalie,
            )}
          >
            <IconeAnnonce size={18} className={styles.contexteIcone} />
            <div className={styles.contexteCorps}>
              <span className={styles.contexteQuoi}>
                {annonce?.quoi ?? 'Une ligne de plus au journal de l’étape.'}
              </span>
              <span className={styles.contexteOu}>
                {consigne.etape.section} · {consigne.etape.libelle}
              </span>
              {/* Ce que l'étape dit déjà. Annoncer « facultatif, l'étape est expliquée » sans
                  montrer l'explication demanderait de fermer la modale pour la vérifier. */}
              {expliqueDeja && consigne.verdict !== null && (
                <span className={styles.contexteDeja}>
                  Dernière observation —{' '}
                  {consigne.etape.observations[consigne.etape.observations.length - 1]?.texte}
                </span>
              )}
            </div>
          </div>
        )}
        {naturesOffertes && (
          <div className={styles.natures}>
            {(
              [
                { valeur: 'note', libelle: 'Observation', icone: MessageSquarePlus },
                { valeur: 'incident', libelle: 'Incident sur une agence', icone: Building2 },
              ] as const
            ).map((n) => (
              <button
                type="button"
                key={n.valeur}
                className={natureObs === n.valeur ? styles.natureActive : styles.nature}
                aria-pressed={natureObs === n.valeur}
                onClick={() => setNatureObs(n.valeur)}
              >
                <n.icone size={14} />
                {n.libelle}
              </button>
            ))}
          </div>
        )}

        {natureObs === 'incident' && (
          <>
            <div className={styles.champ}>
              <span>Agence concernée</span>
              <SelecteurListe
                options={optionsAgences}
                valeur={agence}
                onChange={setAgence}
                placeholder="Choisir ou saisir une agence…"
                // La liste officielle oriente la saisie vers un nom unique par site ; le core
                // banking nomme aussi des agences qui lui sont propres (« 000 BAM »), et une nuit
                // ne doit pas s'arrêter faute de vocabulaire. Ce qu'on tape ici ne crée pas
                // d'entrée au référentiel du parc : ce n'est pas le même objet.
                onCreer={(libelle) => Promise.resolve(libelle)}
              />
            </div>
            <div className={styles.champ}>
              <span>Heure de relance</span>
              <SelecteurHeureEod
                heures={heureSaisie(relance)?.h ?? null}
                minutes={heureSaisie(relance)?.m ?? null}
                onChoisir={(hh, mm) => setRelance(formatHeure(hh, mm))}
                trigger={({ onClick, ref }) => (
                  <button ref={ref} type="button" className={styles.champHeure} onClick={onClick}>
                    <Clock size={15} className={styles.champHeureIcone} />
                    <span className={relance === '' ? styles.vide : undefined}>
                      {relance || '01H12'}
                    </span>
                  </button>
                )}
              />
              <span className={styles.indice}>
                Préremplie sur l’instant : on consigne sur le moment, et l’opérateur ne corrige que
                ce qui compte. La date se déduit — l’EOD franchit minuit.
              </span>
            </div>
          </>
        )}

        {/* « Sans objet » se dit presque toujours de la même façon : on propose ces mots-là, d'un
            clic, plutôt que de les faire retaper chaque nuit sous une forme nouvelle. */}
        {consigne?.verdict === 'Non applicable' && (
          <div className={styles.motifs}>
            {MOTIFS_SANS_OBJET.map((m) => (
              <button
                type="button"
                key={m.court}
                className={cx(styles.motif, texteObs === m.texte && styles.motifChoisi)}
                aria-pressed={texteObs === m.texte}
                onClick={() => setTexteObs(texteObs === m.texte ? '' : m.texte)}
                title={m.texte}
              >
                {m.court}
              </button>
            ))}
          </div>
        )}
        <label className={styles.champ}>
          <span>
            {natureObs === 'incident' ? 'Ce qui a été fait' : 'Observation'}
            {expliqueDeja && consigne?.verdict != null && (
              <span className={styles.facultatif}> — facultatif, l’étape est déjà expliquée</span>
            )}
          </span>
          <textarea
            className={styles.note}
            rows={3}
            value={texteObs}
            onChange={(e) => setTexteObs(e.target.value)}
            placeholder={
              natureObs === 'incident'
                ? // Ce que les vrais rapports contiennent : un code d'erreur, un nom de batch,
                  // collés tels quels depuis l'écran du core banking — pas une phrase racontée.
                  'Ex. Error code AE-VALS-053 sur POSTEOPD3 — batch relancé, reprise OK.'
                : 'Ex. The jobs are started but the date is still 09/09/2026.'
            }
          />
        </label>
        <p className={styles.avertissement}>
          Une fois consignée, une observation ne se corrige ni ne s’efface : elle est signée et
          horodatée. Ce qu’il faut rectifier se dit dans la suivante.
        </p>
      </Modale>

      <Modale
        ouverte={ajout}
        onFermer={() => setAjout(false)}
        titre="Ajouter une étape"
        pied={
          <>
            <Button variante="secondaire" onClick={() => setAjout(false)}>
              Annuler
            </Button>
            <Button
              disabled={libelleNouveau.trim().length < 2}
              onClick={() => {
                void agir('ajout', () =>
                  eodApi.ajouterEtape(id, {
                    section: sectionNouvelle,
                    libelle: libelleNouveau.trim(),
                  }),
                ).then(() => {
                  setAjout(false);
                  setLibelleNouveau('');
                });
              }}
            >
              Ajouter
            </Button>
          </>
        }
      >
        <div className={styles.contexte}>
          <Plus size={18} className={styles.contexteIcone} />
          <div className={styles.contexteCorps}>
            <span className={styles.contexteQuoi}>Une étape pour cette soirée seulement.</span>
            <span className={styles.contexteOu}>
              Le déroulé de référence n’est pas touché : les nuits suivantes ne la verront pas.
            </span>
          </div>
        </div>
        <label className={styles.champ}>
          <span>Section</span>
          <input value={sectionNouvelle} onChange={(e) => setSectionNouvelle(e.target.value)} />
          <span className={styles.indice}>
            Une section inconnue se range en fin de déroulé, jamais au milieu.
          </span>
        </label>
        <label className={styles.champ}>
          <span>Intitulé</span>
          <input
            value={libelleNouveau}
            onChange={(e) => setLibelleNouveau(e.target.value)}
            placeholder="Ex. Relance du batch EMS_OUT"
          />
        </label>
      </Modale>

      <Modale
        ouverte={transitionVisee !== null}
        onFermer={() => {
          setTransitionVisee(null);
          setNoteTransition('');
        }}
        titre={`Clore la soirée en « ${transitionVisee ?? ''} »`}
        pied={
          <>
            <Button
              variante="secondaire"
              onClick={() => {
                setTransitionVisee(null);
                setNoteTransition('');
              }}
            >
              Annuler
            </Button>
            <Button
              variante="danger"
              disabled={noteTransition.trim().length < 3}
              onClick={() => {
                if (transitionVisee !== null) void transitionner(transitionVisee);
              }}
            >
              Clore la soirée
            </Button>
          </>
        }
      >
        <div className={cx(styles.contexte, styles.contexteClore)}>
          <TriangleAlert size={18} className={styles.contexteIcone} />
          <div className={styles.contexteCorps}>
            <span className={styles.contexteQuoi}>
              {soiree.reste} étape(s) ne sont pas réglées.
            </span>
            <span className={styles.contexteOu}>
              Dites pourquoi la soirée s’arrête là : sans cette note, les étapes restées « À faire »
              ne se reliront pas.
            </span>
          </div>
        </div>
        <textarea
          className={styles.note}
          rows={3}
          value={noteTransition}
          onChange={(e) => setNoteTransition(e.target.value)}
          placeholder="Ex. Reprise reportée au matin, batch EMS relancé par l'éditeur."
        />
      </Modale>

      <ModaleConfirmation
        demande={
          aReprendre === null
            ? null
            : {
                titre:
                  aReprendre.debut !== null && aReprendre.fin === null
                    ? 'Annuler le démarrage'
                    : 'Reprendre cette étape',
                message:
                  aReprendre.debut === null
                    ? `« ${aReprendre.libelle} » redevient « À faire ».`
                    : aReprendre.fin === null
                      ? `Le compteur de « ${aReprendre.libelle} » s’arrête et son heure de ` +
                        `démarrage (${heure(aReprendre.debut)}) est effacée. L’étape redevient ` +
                        `« À faire ». Les observations déjà consignées restent.`
                      : `« ${aReprendre.libelle} » repasse « En cours ». L’heure de fin est ` +
                        `effacée ; le compteur repart de ${heure(aReprendre.debut)} et continue ` +
                        `de courir — c’est la même étape qui se poursuit. Les observations déjà ` +
                        `consignées restent.`,
                libelleConfirmer:
                  aReprendre.debut !== null && aReprendre.fin === null
                    ? 'Annuler le démarrage'
                    : 'Reprendre',
                action: () => reprendre(aReprendre),
              }
        }
        onFermer={() => setAReprendre(null)}
      />

      <ModaleConfirmation
        demande={
          aSupprimer === null
            ? null
            : {
                titre: 'Retirer cette étape',
                message: `« ${aSupprimer.libelle} » sera retirée de cette soirée.`,
                libelleConfirmer: 'Retirer',
                variante: 'danger',
                action: () => agir('suppression', () => eodApi.supprimerEtape(id, aSupprimer.id)),
              }
        }
        onFermer={() => setASupprimer(null)}
      />
    </div>
  );
}
