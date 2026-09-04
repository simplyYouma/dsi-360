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
import { etatImports, importApi, type DernierImport, type RapportFichier } from './importApi';

// Libellés lisibles des clés de compte-rendu (les clés varient selon la nature du fichier).
const LIBELLE_DETAIL: Record<string, string> = {
  total: 'lus',
  crees: 'créés',
  mis_a_jour: 'mis à jour',
  inchanges: 'inchangés',
  ignores: 'sans code immo',
  detenteurs_non_rapproches: 'détenteurs à rattacher',
  demandeurs_crees: 'demandeurs créés',
  constats_enregistres: 'constats de campagne',
  statuts_inconnus: 'statuts non reconnus',
  reclasses: 'requalifiés',
  doublons_fusionnes: 'doublons fusionnés',
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

/** Tuiles de compte-rendu selon la nature reconnue par le serveur. */
function tuilesDe(r: RapportFichier): { libelle: string; valeur: number; couleur: string }[] {
  if (r.nature === 'tickets') {
    const tuilesTickets = [
      { libelle: 'Tickets traités', valeur: r.total, couleur: '#4f6bed' },
      { libelle: 'Créés', valeur: r.crees, couleur: '#1f9d55' },
      { libelle: 'Mis à jour', valeur: r.mis_a_jour, couleur: '#c77700' },
      { libelle: 'Inchangés', valeur: r.inchanges, couleur: '#8a93a6' },
    ];
    // Une requalification n'a rien d'anodin : une activité a changé de module. On ne montre la
    // tuile que lorsqu'il s'en est produit — une ligne « 0 » ne dit rien à personne.
    if (r.reclasses > 0) {
      tuilesTickets.push({ libelle: 'Requalifiés', valeur: r.reclasses, couleur: '#7a5af8' });
    }
    if (r.doublons_fusionnes > 0) {
      tuilesTickets.push({
        libelle: 'Doublons fusionnés',
        valeur: r.doublons_fusionnes,
        couleur: '#7a5af8',
      });
    }
    return tuilesTickets;
  }
  const tuiles = [
    { libelle: 'Équipements lus', valeur: r.total, couleur: '#4f6bed' },
    { libelle: 'Créés', valeur: r.crees, couleur: '#1f9d55' },
    { libelle: 'Mis à jour', valeur: r.mis_a_jour, couleur: '#c77700' },
    { libelle: 'Sans code immo', valeur: r.ignores, couleur: '#8a93a6' },
    { libelle: 'Détenteurs à rattacher', valeur: r.detenteurs_non_rapproches, couleur: '#c77700' },
  ];
  // Les croix bon/rebut/casse du fichier ne deviennent des constats que si une campagne est ouverte.
  if (r.constats_enregistres > 0) {
    tuiles.push({ libelle: 'Constats de campagne', valeur: r.constats_enregistres, couleur: '#1f9d55' });
  }
  return tuiles;
}

export function ImportPage(): JSX.Element {
  const [enCours, setEnCours] = useState(false);
  const [rapport, setRapport] = useState<RapportFichier | null>(null);
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
    setNomFichier(fichier.name);
    setEnCours(true);
    try {
      // Un seul point de dépôt : le serveur reconnaît la nature du fichier à ses en-têtes.
      const r = await importApi.fichier(fichier);
      setRapport(r);
      const quoi = r.nature === 'tickets' ? 'ticket(s)' : 'équipement(s)';
      notifier(
        `Import réussi : ${r.total} ${quoi} — ${r.crees} créé(s), ${r.mis_a_jour} mis à jour.`,
        'succes',
      );
      chargerEtat();
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

  const tuiles = rapport ? tuilesDe(rapport) : [];

  return (
    <div className={`${incidents.page} ${styles.pagePleine}`}>
      <header className={incidents.entete}>
        <div>
          <h1 className={incidents.titre}>Imports</h1>
          <p className={incidents.sous}>
            Déposez le rapport de tickets ou l’inventaire des équipements (.xlsx) : le système
            reconnaît le fichier. Recharger le même ne crée jamais de doublon.
          </p>
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

      <Card className={styles.cartePleine}>
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
            {enCours ? 'Import en cours…' : 'Déposer ou choisir un fichier'}
          </span>
          <span className={styles.zoneSous}>
            {nomFichier ? (
              <span className={styles.fichier}>
                <FileSpreadsheet size={14} /> {nomFichier}
              </span>
            ) : (
              'Rapport de tickets ou inventaire — la nature est reconnue automatiquement'
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
            <AlertTriangle size={15} />
            {erreur}
          </p>
        )}

        {rapport !== null && (
          <div className={styles.rapport}>
            <p className={styles.rapportTitre}>
              <CheckCircle2 size={15} />
              {rapport.nature === 'tickets'
                ? 'Rapport de tickets importé'
                : 'Inventaire des équipements importé'}
            </p>
            <div className={styles.tuiles}>
              {tuiles.map((t) => (
                <div key={t.libelle} className={styles.tuile}>
                  <span className={styles.tuileValeur} style={{ color: t.couleur }}>
                    {t.valeur}
                  </span>
                  <span className={styles.tuileLibelle}>{t.libelle}</span>
                </div>
              ))}
            </div>
            {/* Un libellé de statut hors table serait resté « en cours » en silence : on le dit,
                pour qu'il soit ajouté à la correspondance. */}
            {/* Un ticket requalifié à la source change de module chez nous : la fiche est
                déplacée, jamais dupliquée. On le dit — c'est une activité qui a changé de liste. */}
            {rapport.nature === 'tickets' && rapport.reclasses > 0 && (
              <p className={styles.info}>
                <CheckCircle2 size={15} />
                {rapport.reclasses === 1
                  ? '1 ticket a changé de module à la source : sa fiche a été déplacée'
                  : `${rapport.reclasses} tickets ont changé de module à la source : leurs fiches ont été déplacées`}
                {rapport.doublons_fusionnes > 0 &&
                  `, dont ${rapport.doublons_fusionnes} qui existai${
                    rapport.doublons_fusionnes === 1 ? 't' : 'ent'
                  } en double depuis un import précédent`}
                . Commentaires, pièces jointes et historique ont suivi.
              </p>
            )}
            {/* Deux fiches pour un même numéro, et le rapport ne les contient plus : rien ne dit
                lequel des deux modules est le bon. On le signale plutôt que de trancher au hasard. */}
            {rapport.nature === 'tickets' && rapport.doublons_restants > 0 && (
              <p className={styles.erreur}>
                <AlertTriangle size={15} />
                {rapport.doublons_restants} numéro
                {rapport.doublons_restants > 1 ? 's' : ''} de ticket {rapport.doublons_restants > 1 ? 'sont portés' : 'est porté'}{' '}
                par deux fiches que ce rapport ne contenait pas : impossible de savoir lequel des
                deux modules est le bon. À trancher à la source, puis relancer un import.
              </p>
            )}
            {rapport.nature === 'tickets' && rapport.statuts_non_reconnus.length > 0 && (
              <p className={styles.erreur}>
                <AlertTriangle size={15} />
                Statuts du fichier non reconnus, laissés « en cours » :{' '}
                {rapport.statuts_non_reconnus.join(', ')} — à signaler pour qu'ils soient pris en
                compte.
              </p>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
