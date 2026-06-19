import { useRef, useState } from 'react';
import { UploadCloud, FileSpreadsheet, CheckCircle2, AlertTriangle, Loader2 } from 'lucide-react';
import { Card, Button } from '@/design-system/primitives';
import { ErreurApi } from '@/lib/api';
import incidents from '@/features/incidents/IncidentsPage.module.css';
import styles from './ImportPage.module.css';
import { importApi, type RapportImport } from './importApi';

export function ImportPage(): JSX.Element {
  const [enCours, setEnCours] = useState(false);
  const [rapport, setRapport] = useState<RapportImport | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [nomFichier, setNomFichier] = useState<string | null>(null);
  const champ = useRef<HTMLInputElement>(null);

  const traiter = async (fichier: File): Promise<void> => {
    setErreur(null);
    setRapport(null);
    setNomFichier(fichier.name);
    setEnCours(true);
    try {
      setRapport(await importApi.tickets(fichier));
    } catch (err) {
      setErreur(err instanceof ErreurApi ? err.message : "Import impossible : vérifiez le fichier.");
    } finally {
      setEnCours(false);
    }
  };

  const surFichier = (e: React.ChangeEvent<HTMLInputElement>): void => {
    const f = e.target.files?.[0];
    if (f) void traiter(f);
    e.target.value = ''; // permet de recharger le même fichier
  };

  const tuiles = rapport
    ? [
        { libelle: 'Tickets traités', valeur: rapport.total, couleur: '#4f6bed' },
        { libelle: 'Créés', valeur: rapport.crees, couleur: '#1f9d55' },
        { libelle: 'Mis à jour', valeur: rapport.mis_a_jour, couleur: '#c77700' },
        { libelle: 'Inchangés', valeur: rapport.inchanges, couleur: '#8a93a6' },
      ]
    : [];

  return (
    <div className={incidents.page}>
      <header className={incidents.entete}>
        <div>
          <h1 className={incidents.titre}>Import quotidien</h1>
          <p className={incidents.sous}>
            Chargez le rapport de tickets (.xlsx). Incidents et demandes sont alimentés et mis à
            jour automatiquement — recharger le même fichier ne crée jamais de doublon.
          </p>
        </div>
      </header>

      <Card>
        <div
          className={styles.zone}
          onClick={() => {
            if (!enCours) champ.current?.click();
          }}
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
            {enCours ? 'Import en cours…' : 'Déposer ou choisir le rapport'}
          </span>
          <span className={styles.zoneSous}>
            {nomFichier ? (
              <span className={styles.fichier}>
                <FileSpreadsheet size={14} /> {nomFichier}
              </span>
            ) : (
              'Format Excel (.xlsx) exporté de l’outil de ticketing'
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
                modifiés, <strong>{rapport.inchanges}</strong> inchangés.{' '}
                <strong>{rapport.demandeurs_crees}</strong> demandeur(s) et{' '}
                <strong>{rapport.gestionnaires_crees}</strong> agent(s) DSI créé(s).
              </span>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
