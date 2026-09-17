import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Building2, CalendarClock, Plus, TriangleAlert } from 'lucide-react';
import {
  Button,
  Modale,
  StatusBadge,
  Table,
  useToast,
  type Colonne,
} from '@/design-system/primitives';
import { BandeauStats } from '@/common/BandeauStats';
import { BoutonsExport } from '@/common/BoutonsExport';
import { BarreAvancement } from '@/common/BarreAvancement';
import { CelluleReference } from '@/common/CelluleReference';
import { FiltreTickets } from '@/common/FiltreTickets';
import { SelecteurDate } from '@/common/SelecteurDate';
import { cx } from '@/common/cx';
import { BadgeStatut } from '@/common/statuts';
import { ErreurApi } from '@/lib/api';
import type { FiltresListe } from '@/features/incidents/incidentsApi';
import styles from '@/features/incidents/IncidentsPage.module.css';
import { eodApi, heure, jour, type CategorieEod, type SoireeEod } from './eodApi';
import propres from './EodPage.module.css';

/** La veille : une soirée ouverte le 16 au matin clôt la journée du 15. */
function journeeParDefaut(): string {
  const d = new Date();
  d.setHours(12, 0, 0, 0);
  return new Date(d.getTime() - 86_400_000).toISOString().slice(0, 10);
}

/** Ce que chaque type de soirée veut dire, sous son nom de trois lettres. Le core banking dit
 *  « EOD », « EOM », « EOY » ; la première fois qu'on ouvre l'écran, on a besoin de la phrase. */
const SENS_TYPE: Record<string, string> = {
  QUOTIDIEN: 'Soirée ordinaire',
  FIN_DE_MOIS: 'Arrêté mensuel — traitements de fin de mois en plus',
  FIN_ANNEE: 'Arrêté annuel — la nuit la plus longue de l’année',
};

/** Le type que la DATE commande. Le 31 décembre porte les traitements annuels, le dernier jour du
 *  mois les mensuels : le déduire évite d'ouvrir un EOD ordinaire un soir d'arrêté, erreur qui ne
 *  se voit qu'au moment où les batchs manquent. L'opérateur garde la main — il reste juge. */
function typeAttendu(iso: string): string {
  const [a, m, j] = iso.split('-').map(Number);
  if (a === undefined || m === undefined || j === undefined) return 'QUOTIDIEN';
  if (m === 12 && j === 31) return 'FIN_ANNEE';
  const dernierJour = new Date(a, m, 0).getDate();
  return j === dernierJour ? 'FIN_DE_MOIS' : 'QUOTIDIEN';
}

const COLONNES: Colonne<SoireeEod>[] = [
  {
    cle: 'reference',
    entete: 'Référence',
    valeur: (s) => s.reference,
    largeur: '170px',
    rendu: (s) => (
      <CelluleReference reference={s.reference} nombre={s.nb_commentaires} nonVus={s.nb_non_vus} />
    ),
  },
  {
    cle: 'journee',
    entete: 'Journée close',
    valeur: (s) => s.journee ?? '',
    largeur: '130px',
    rendu: (s) => <strong>{jour(s.journee)}</strong>,
  },
  {
    cle: 'categorie',
    entete: 'Type',
    valeur: (s) => s.categorie ?? '',
    rendu: (s) =>
      s.categorie !== null ? <StatusBadge couleur="var(--cat-6)">{s.categorie}</StatusBadge> : '—',
  },
  {
    cle: 'statut',
    entete: 'Statut',
    valeur: (s) => s.statut,
    rendu: (s) => <BadgeStatut statut={s.statut} module="eod" />,
  },
  {
    cle: 'avancement',
    entete: 'Déroulé',
    valeur: (s) => s.avancement,
    largeur: '190px',
    // Le pourcentage seul ne dit pas si la nuit est longue : « 24/28 » situe l'étape où l'on est.
    rendu: (s) => (
      <div className={propres.deroule}>
        <BarreAvancement valeur={s.avancement} compact />
        <span className={propres.etapes}>
          {s.nb_etapes - s.reste}/{s.nb_etapes}
        </span>
      </div>
    ),
  },
  {
    cle: 'anomalies',
    entete: 'Anomalies',
    aligne: 'centre',
    valeur: (s) => s.anomalies,
    // Le chiffre que la DSI cherche d'abord. Zéro reste discret : signaler une nuit normale
    // ferait perdre de vue celles qui ne le sont pas.
    rendu: (s) =>
      s.anomalies > 0 ? (
        <StatusBadge statut="danger">
          <TriangleAlert size={12} /> {s.anomalies}
        </StatusBadge>
      ) : (
        <span className={propres.muet}>—</span>
      ),
  },
  {
    cle: 'incidents',
    entete: 'Relances',
    aligne: 'centre',
    valeur: (s) => s.incidents,
    // Distincte des anomalies, et pas déductible d'elles : une agence peut être relancée sans que
    // l'étape finisse en anomalie. C'est la colonne qui répond à « quelles nuits ont coûté au
    // réseau ». Zéro reste discret, pour la même raison qu'à côté.
    rendu: (s) =>
      s.incidents > 0 ? (
        <StatusBadge couleur="var(--status-warn)">
          <Building2 size={12} /> {s.incidents}
        </StatusBadge>
      ) : (
        <span className={propres.muet}>—</span>
      ),
  },
  {
    cle: 'plage',
    entete: 'Début → fin',
    valeur: (s) => s.debut_effectif ?? '',
    largeur: '150px',
    rendu: (s) =>
      s.debut_effectif === null ? (
        <span className={propres.muet}>—</span>
      ) : (
        <span className={propres.plage}>
          {heure(s.debut_effectif)} → {s.fin_effective === null ? '…' : heure(s.fin_effective)}
        </span>
      ),
  },
  {
    cle: 'responsable',
    entete: 'Opérateur',
    valeur: (s) => (s.responsable !== null ? `${s.responsable.prenom} ${s.responsable.nom}` : ''),
    rendu: (s) => (s.responsable !== null ? `${s.responsable.prenom} ${s.responsable.nom}` : '—'),
  },
];

export function EodPage(): JSX.Element {
  const navigate = useNavigate();
  const { notifier } = useToast();
  const [soirees, setSoirees] = useState<SoireeEod[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [chargement, setChargement] = useState(true);
  const [filtres, setFiltres] = useState<FiltresListe>({ etat: 'en_cours' });

  const [modale, setModale] = useState(false);
  const [journee, setJournee] = useState<string | null>(journeeParDefaut());
  const [categories, setCategories] = useState<CategorieEod[]>([]);
  const [categorie, setCategorie] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);

  const charger = useCallback(
    async (p: number): Promise<void> => {
      setChargement(true);
      try {
        const data = await eodApi.lister(p, filtres);
        setSoirees(data.elements);
        setTotal(data.total);
      } finally {
        setChargement(false);
      }
    },
    [filtres],
  );

  useEffect(() => {
    void charger(page);
  }, [charger, page]);

  useEffect(() => {
    if (!modale) return;
    void eodApi.categories().then(setCategories);
  }, [modale]);

  // Le type suit la date : la changer reprend la main sur un choix précédent, parce que c'est bien
  // la date qui décide si la nuit porte un arrêté. Un clic sur un type le fixe jusqu'à la prochaine
  // date choisie.
  useEffect(() => {
    if (journee === null || categories.length === 0) return;
    const voulu = categories.find((c) => c.code === typeAttendu(journee));
    setCategorie(voulu?.id ?? null);
  }, [journee, categories]);

  const ouvrir = async (): Promise<void> => {
    if (journee === null) return;
    setEnvoi(true);
    try {
      const { id } = await eodApi.ouvrir({ journee, categorie_id: categorie });
      setModale(false);
      navigate(`/eod/${id}`);
    } catch (e) {
      // Le serveur nomme la soirée déjà ouverte (« EOD-2026-00042 couvre déjà cette journée ») :
      // on relaie son message tel quel plutôt que d'en inventer un plus vague.
      notifier(e instanceof ErreurApi ? e.message : "La soirée n'a pas pu être ouverte.", 'erreur');
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <div className={styles.page}>
      <header className={styles.entete}>
        <div>
          <h1 className={styles.titre}>EOD</h1>
          <p className={styles.sous}>
            Le traitement de clôture quotidien du core banking : déroulé pointé, anomalies, rapport
            du soir.
          </p>
        </div>
        <div className={propres.actions}>
          <BoutonsExport base="/eod" />
          <Button onClick={() => setModale(true)}>
            <Plus size={16} />
            Ouvrir une soirée
          </Button>
        </div>
      </header>

      <BandeauStats base="/eod" signal={total} />

      <FiltreTickets
        module="eod"
        valeur={filtres}
        onChange={(f) => {
          setPage(1);
          setFiltres(f);
        }}
      />

      <Table
        colonnes={COLONNES}
        lignes={soirees}
        cleLigne={(s) => s.id}
        chargement={chargement}
        vide="Aucune soirée EOD enregistrée."
        onLigne={(s) => navigate(`/eod/${s.id}`)}
        pagination={{ page, total, taille: 15, onPage: setPage }}
      />

      <Modale
        ouverte={modale}
        onFermer={() => setModale(false)}
        titre="Ouvrir une soirée EOD"
        pied={
          <>
            <Button variante="secondaire" onClick={() => setModale(false)}>
              Annuler
            </Button>
            <Button onClick={() => void ouvrir()} disabled={journee === null || envoi}>
              {envoi ? 'Ouverture…' : 'Ouvrir la soirée'}
            </Button>
          </>
        }
      >
        <div className={propres.contexte}>
          <CalendarClock size={18} className={propres.contexteIcone} />
          <div>
            <div className={propres.contexteQuoi}>Une seule soirée par journée comptable.</div>
            <div className={propres.contexteOu}>
              Le déroulé de référence — vingt-huit étapes — est posé d’emblée : il n’y a rien
              d’autre à saisir avant de pointer la première.
            </div>
          </div>
        </div>

        <label className={styles.champ}>
          <span>Journée comptable à clore</span>
          <SelecteurDate valeur={journee} onChange={setJournee} placeholder="jj/mm/aaaa" />
          <span className={propres.indice}>
            La date de la journée qu’on <strong>clôt</strong>, et non celle de la saisie : une
            soirée commencée le 15 au soir se termine le 16 au matin.
          </span>
        </label>

        {categories.length > 0 && (
          <div className={styles.champ}>
            <span>Type de soirée</span>
            {/* Trois lettres, et ce qu'elles veulent dire : le type se lit d'un coup d'œil, et
                celui que la date commande est proposé d'avance. */}
            <div className={propres.types}>
              {categories.map((c) => (
                <button
                  type="button"
                  key={c.id}
                  className={cx(propres.type, categorie === c.id && propres.typeChoisi)}
                  aria-pressed={categorie === c.id}
                  onClick={() => setCategorie(c.id)}
                >
                  <span className={propres.typeNom}>{c.libelle}</span>
                  <span className={propres.typeSens}>{SENS_TYPE[c.code] ?? ''}</span>
                </button>
              ))}
            </div>
            {journee !== null &&
              categories.find((c) => c.id === categorie)?.code === typeAttendu(journee) &&
              typeAttendu(journee) !== 'QUOTIDIEN' && (
                <span className={propres.indice}>
                  Proposé d’après la date : c’est un soir d’arrêté.
                </span>
              )}
          </div>
        )}
      </Modale>
    </div>
  );
}
