import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileSpreadsheet, TriangleAlert, Upload } from 'lucide-react';
import { Button, Modale, useToast } from '@/design-system/primitives';
import { cx } from '@/common/cx';
import { ErreurApi, televerser } from '@/lib/api';
import styles from './ImportClasseur.module.css';

/** Ce que le serveur rend après un dépôt — le compte rendu, jamais un simple « importé ». */
interface RapportImport {
  journee: string;
  reference: string;
  soiree_id: string;
  creee: boolean;
  etapes_renseignees: number;
  etapes_conservees: number;
  observations_ajoutees: number;
  lignes_non_reconnues: string[];
}

interface Props {
  /** Rafraîchit la liste : la soirée vient peut-être d'être ouverte par le dépôt. */
  onImporte: () => void;
}

function jourFrancais(iso: string): string {
  const [a, m, j] = iso.split('-');
  return `${j}/${m}/${a}`;
}

/**
 * Charger une soirée depuis le classeur du soir.
 *
 * La nuit se pointe à l'écran quand la plateforme est sous la main, et dans le tableur de la banque
 * quand elle ne l'est pas. Retaper vingt-huit lignes au matin n'apporte rien et introduit des
 * fautes : on dépose le fichier, le pointage s'en déduit.
 *
 * L'écran ne demande **ni la date ni la soirée** : le classeur porte la sienne, relevée sur sa
 * ligne « System Date ». Demander une date que le fichier connaît déjà, c'est ouvrir la porte à
 * un désaccord entre les deux — et c'est le fichier qui aurait raison.
 *
 * Le compte rendu est montré avant toute chose, et il dit ce que le dépôt **n'a pas** fait :
 * combien d'étapes étaient déjà pointées et ont donc été laissées telles quelles, quelles lignes
 * le déroulé de référence ne connaît pas. Un import qui n'annoncerait que ses réussites laisserait
 * croire que le reste a été repris.
 */
export function ImportClasseur({ onImporte }: Props): JSX.Element {
  const navigate = useNavigate();
  const { notifier } = useToast();
  const [ouverte, setOuverte] = useState(false);
  const [envoi, setEnvoi] = useState(false);
  const [survole, setSurvole] = useState(false);
  const [rapport, setRapport] = useState<RapportImport | null>(null);
  const input = useRef<HTMLInputElement>(null);

  const deposer = async (fichier: File | undefined): Promise<void> => {
    if (fichier === undefined) return;
    setEnvoi(true);
    try {
      setRapport(await televerser<RapportImport>('/import/eod', fichier));
      onImporte();
    } catch (e) {
      // Le serveur dit ce qui manque au fichier (« les colonnes Start, End et Notes sont
      // introuvables ») : on relaie son message plutôt que d'en inventer un plus vague.
      notifier(e instanceof ErreurApi ? e.message : 'Le classeur n’a pas pu être lu.', 'erreur');
    } finally {
      setEnvoi(false);
      if (input.current !== null) input.current.value = '';
    }
  };

  const fermer = (): void => {
    setOuverte(false);
    setRapport(null);
  };

  return (
    <>
      <Button variante="secondaire" onClick={() => setOuverte(true)}>
        <Upload size={16} />
        Charger un classeur
      </Button>

      <Modale
        ouverte={ouverte}
        onFermer={fermer}
        titre="Charger une soirée depuis le classeur"
        pied={
          rapport === null ? (
            <Button variante="secondaire" onClick={fermer}>
              Annuler
            </Button>
          ) : (
            <>
              <Button variante="secondaire" onClick={fermer}>
                Fermer
              </Button>
              <Button
                onClick={() => {
                  fermer();
                  navigate(`/eod/${rapport.soiree_id}`);
                }}
              >
                Ouvrir {rapport.reference}
              </Button>
            </>
          )
        }
      >
        {rapport === null ? (
          <>
            <p className={styles.explication}>
              Déposez le rapport du soir au format Excel, tel qu’il est rempli par la Production. La
              journée comptable est lue sur sa ligne «&nbsp;System&nbsp;Date&nbsp;» : rien d’autre
              n’est à saisir. Une étape déjà pointée à l’écran ne sera pas récrite.
            </p>
            <div
              className={cx(styles.zone, survole && styles.zoneSurvolee)}
              onDragOver={(e) => {
                e.preventDefault();
                setSurvole(true);
              }}
              onDragLeave={() => setSurvole(false)}
              onDrop={(e) => {
                e.preventDefault();
                setSurvole(false);
                void deposer(e.dataTransfer.files[0]);
              }}
            >
              <FileSpreadsheet size={28} className={styles.icone} />
              <span className={styles.zoneTitre}>
                {envoi ? 'Lecture du classeur…' : 'Glissez le classeur ici'}
              </span>
              <Button variante="secondaire" disabled={envoi} onClick={() => input.current?.click()}>
                Choisir un fichier
              </Button>
              <input
                ref={input}
                type="file"
                accept=".xlsx,.xlsm"
                hidden
                onChange={(e) => void deposer(e.target.files?.[0])}
              />
            </div>
          </>
        ) : (
          <div className={styles.rapport}>
            <p className={styles.resume}>
              {rapport.creee
                ? `Soirée ouverte pour la journée du ${jourFrancais(rapport.journee)}.`
                : `Soirée du ${jourFrancais(rapport.journee)} complétée.`}
            </p>
            <dl className={styles.comptes}>
              <div>
                <dt>Étapes renseignées</dt>
                <dd>{rapport.etapes_renseignees}</dd>
              </div>
              <div>
                <dt>Déjà pointées, conservées</dt>
                <dd>{rapport.etapes_conservees}</dd>
              </div>
              <div>
                <dt>Observations ajoutées</dt>
                <dd>{rapport.observations_ajoutees}</dd>
              </div>
            </dl>
            {rapport.lignes_non_reconnues.length > 0 && (
              <div className={styles.inconnues}>
                <span className={styles.inconnuesTitre}>
                  <TriangleAlert size={14} />
                  {rapport.lignes_non_reconnues.length} ligne(s) hors du déroulé de référence
                </span>
                <ul>
                  {rapport.lignes_non_reconnues.map((l) => (
                    <li key={l}>{l}</li>
                  ))}
                </ul>
                <p className={styles.inconnuesAide}>
                  Elles n’ont pas été importées. Ajoutez-les au déroulé depuis l’administration, ou
                  à cette soirée seule depuis sa fiche.
                </p>
              </div>
            )}
          </div>
        )}
      </Modale>
    </>
  );
}
