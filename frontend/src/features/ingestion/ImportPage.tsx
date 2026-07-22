import { useCallback, useEffect, useRef, useState } from 'react';
import {
  UploadCloud,
  FileSpreadsheet,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  CalendarClock,
} from 'lucide-react';
import { Card, Button, useToast } from '@/design-system/primitives';
import { ErreurApi } from '@/lib/api';
import incidents from '@/features/incidents/IncidentsPage.module.css';
import styles from './ImportPage.module.css';
import filtres from '@/common/FiltreTickets.module.css';
import {
  etatImports,
  importApi,
  type DernierImport,
  type RapportImport,
  type RapportImportEquipements,
} from './importApi';

/** Les deux fichiers que reçoit la DSI. Chacun a sa clé d'idempotence et son compte-rendu. */
type Nature = 'tickets' | 'equipements';
const NATURES: { cle: Nature; libelle: string }[] = [
  { cle: 'tickets', libelle: 'Tickets du jour' },
  { cle: 'equipements', libelle: 'Inventaire' },
];
const LIBELLE_DETAIL: Record<string, string> = {
  total: 'lus',
  crees: 'créés',
  mis_a_jour: 'mis à jour',
  inchanges: 'inchangés',
  ignores: 'sans code immo',
  detenteurs_non_rapproches: 'détenteurs à rattacher',
  demandeurs_crees: 'demandeurs créés',
  incidents: 'incidents',
  demandes: 'demandes',
  lus: 'lus',
};

function horodatageImport(iso: string): string {
  return new Date(iso).toLocaleString('fr-FR', {
    weekday: 'long',
    day: '2-digit',
    month: 'long',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** Le dernier dépôt date d'aujourd'hui ? La couleur répond avant la lecture. */
function importFrais(iso: string): boolean {
  return new Date(iso).toDateString() === new Date().toDateString();
}

const TEXTES: Record<Nature, { sous: string; zone: string; bouton: string }> = {
  tickets: {
    sous: 'Chargez le rapport de tickets (.xlsx). Incidents et demandes sont alimentés et mis à jour automatiquement — recharger le même fichier ne crée jamais de doublon.',
    zone: 'Format Excel (.xlsx) exporté de l’outil de ticketing',
    bouton: 'Déposer ou choisir le rapport',
  },
  equipements: {
    sous: "Chargez l'inventaire des immobilisations (.xlsx). Les colonnes comptables sont reprises du fichier ; ce que la DSI a saisi à l'écran (n° de série, modèle, emplacement, détenteur) n'est jamais écrasé.",
    zone: 'Format Excel (.xlsx) — le code d’immobilisation identifie chaque équipement',
    bouton: 'Déposer ou choisir l’inventaire',
  },
};

export function ImportPage(): JSX.Element {
  const [enCours, setEnCours] = useState(false);
  const [nature, setNature] = useState<Nature>('tickets');
  const [rapport, setRapport] = useState<RapportImport | null>(null);
  const [rapportEqp, setRapportEqp] = useState<RapportImportEquipements | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [nomFichier, setNomFichier] = useState<string | null>(null);
  const [survol, setSurvol] = useState(false);
  const champ = useRef<HTMLInputElement>(null);
  const { notifier } = useToast();
  // La mémoire des dépôts : sait-on si l'import du jour a été fait ? Persistant (journal d'audit).
  const [derniers, setDerniers] = useState<DernierImport[]>([]);
  const chargerEtat = useCallback((): void => {
    void etatImports()
      .then((r) => setDerniers(r.derniers))
      .catch(() => undefined);
  }, []);
  useEffect(() => chargerEtat(), [chargerEtat]);

  const traiter = async (fichier: File): Promise<void> => {
    setErreur(null);
    setRapport(null);
    setRapportEqp(null);
    setNomFichier(fichier.name);
    setEnCours(true);
    try {
      if (nature === 'equipements') {
        const r = await importApi.equipements(fichier);
        setRapportEqp(r);
        notifier(
          `Import réussi : ${r.total} équipement(s) — ${r.crees} créé(s), ${r.mis_a_jour} mis à jour.`,
          'succes',
        );
        chargerEtat();
      } else {
        const r = await importApi.tickets(fichier);
        setRapport(r);
        notifier(
          `Import réussi : ${r.total} ticket(s) — ${r.crees} créé(s), ${r.mis_a_jour} mis à jour.`,
          'succes',
        );
        chargerEtat();
      }
    } catch (err) {
      const msg =
        err instanceof ErreurApi ? err.message : 'Import impossible : vérifiez le fichier.';
      setErreur(msg);
      notifier(`Échec de l’import : ${msg}`, 'erreur');
    } finally {
      setEnCours(false);
    }
  };

  const surFichier = (e: React.ChangeEvent<HTMLInputElement>): void => {
    const f = e.target.files?.[0];
    if (f) void traiter(f);
    e.target.value = ''; // permet de recharger le même fichier
  };

  // Un fichier lâché sur la zone : sans preventDefault, le navigateur l'ouvrirait à la place.
  const surDepot = (e: React.DragEvent<HTMLDivElement>): void => {
    e.preventDefault();
    setSurvol(false);
    if (enCours) return;
    const f = e.dataTransfer.files?.[0];
    if (!f) return;
    if (!f.name.toLowerCase().endsWith('.xlsx')) {
      setErreur('Format attendu : un fichier Excel (.xlsx).');
      notifier('Format attendu : un fichier Excel (.xlsx).', 'erreur');
      return;
    }
    void traiter(f);
  };

  const tuiles = rapport
    ? [
        { libelle: 'Tickets traités', valeur: rapport.total, couleur: '#4f6bed' },
        { libelle: 'Créés', valeur: rapport.crees, couleur: '#1f9d55' },
        { libelle: 'Mis à jour', valeur: rapport.mis_a_jour, couleur: '#c77700' },
        { libelle: 'Inchangés', valeur: rapport.inchanges, couleur: '#8a93a6' },
      ]
    : rapportEqp
      ? [
          { libelle: 'Lignes lues', valeur: rapportEqp.total, couleur: '#4f6bed' },
          { libelle: 'Créés', valeur: rapportEqp.crees, couleur: '#1f9d55' },
          { libelle: 'Mis à jour', valeur: rapportEqp.mis_a_jour, couleur: '#c77700' },
          // Ces deux-là appellent une action : on les montre même à zéro.
          { libelle: 'Sans code immo', valeur: rapportEqp.ignores, couleur: '#8a93a6' },
          {
            libelle: 'Détenteurs à rattacher',
            valeur: rapportEqp.detenteurs_non_rapproches,
            couleur: '#c77700',
          },
        ]
      : [];

  return (
    <div className={incidents.page}>
      <header className={incidents.entete}>
        <div>
          <h1 className={incidents.titre}>Import quotidien</h1>
          <p className={incidents.sous}>{TEXTES[nature].sous}</p>
        </div>
        <div className={filtres.segments}>
          {NATURES.map((n) => (
            <button
              key={n.cle}
              type="button"
              className={nature === n.cle ? filtres.segmentOn : filtres.segment}
              onClick={() => {
                setNature(n.cle);
                setRapport(null);
                setRapportEqp(null);
                setErreur(null);
                setNomFichier(null);
              }}
            >
              {n.libelle}
            </button>
          ))}
        </div>
      </header>

      {derniers.length > 0 && (
        <div className={styles.etatImports}>
          {derniers.map((d) => (
            <div
              key={d.nature}
              className={importFrais(d.horodatage) ? styles.etatFrais : styles.etatAncien}
            >
              <span className={styles.etatIcone}>
                <CalendarClock size={16} />
              </span>
              <div className={styles.etatCorps}>
                <span className={styles.etatNature}>
                  {d.nature === 'tickets' ? 'Tickets du jour' : 'Inventaire'}
                  <em>{importFrais(d.horodatage) ? "importé aujourd'hui" : 'dernier import'}</em>
                </span>
                <span className={styles.etatQuand}>
                  {horodatageImport(d.horodatage)}
                  {d.acteur ? ` · par ${d.acteur}` : ''}
                </span>
                <span className={styles.etatDetails}>
                  {Object.entries(d.details)
                    .filter(([cle, v]) => v > 0 && LIBELLE_DETAIL[cle])
                    .map(([cle, v]) => `${v} ${LIBELLE_DETAIL[cle]}`)
                    .join(' · ')}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      <Card>
        <div
          className={survol ? `${styles.zone} ${styles.zoneSurvol}` : styles.zone}
          onClick={() => {
            if (!enCours) champ.current?.click();
          }}
          onDragOver={(e) => {
            e.preventDefault();
            if (!enCours) setSurvol(true);
          }}
          onDragLeave={() => setSurvol(false)}
          onDrop={surDepot}
        >
          <input
            ref={champ}
            type="file"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            onChange={surFichier}
            hidden
            disabled={enCours}
          />
          <span className={styles.zoneIcone}>
            {enCours ? <Loader2 size={30} className={styles.tourne} /> : <UploadCloud size={30} />}
          </span>
          <span className={styles.zoneTitre}>
            {enCours ? 'Import en cours…' : TEXTES[nature].bouton}
          </span>
          <span className={styles.zoneSous}>
            {nomFichier ? (
              <span className={styles.fichier}>
                <FileSpreadsheet size={14} /> {nomFichier}
              </span>
            ) : (
              TEXTES[nature].zone
            )}
          </span>
          <span className={styles.zoneBtn}>
            <Button
              type="button"
              disabled={enCours}
              onClick={(e) => {
                e.stopPropagation();
                champ.current?.click();
              }}
            >
              Choisir un fichier
            </Button>
          </span>
        </div>
        {erreur !== null && (
          <p className={styles.erreur}>
            <AlertTriangle size={15} /> {erreur}
          </p>
        )}
      </Card>

      {rapport !== null && (
        <>
          <section className={styles.tuiles}>
            {tuiles.map((t) => (
              <Card key={t.libelle} className={styles.tuile}>
                <span className={styles.tuileValeur} style={{ color: t.couleur }}>
                  {t.valeur}
                </span>
                <span className={styles.tuileLibelle}>{t.libelle}</span>
              </Card>
            ))}
          </section>

          <Card>
            <div className={styles.resume}>
              <CheckCircle2 size={18} className={styles.ok} />
              <span>
                <strong>{rapport.incidents}</strong> incidents et{' '}
                <strong>{rapport.demandes}</strong> demandes traités —{' '}
                <strong>{rapport.crees}</strong> nouveaux, <strong>{rapport.mis_a_jour}</strong>{' '}
                modifiés, <strong>{rapport.inchanges}</strong> inchangés. Les gestionnaires du
                fichier sont rattachés aux comptes DSI existants ; aucun compte n’est créé
                automatiquement.
              </span>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
