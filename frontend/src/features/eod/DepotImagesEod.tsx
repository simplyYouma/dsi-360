import { useCallback, useEffect, useRef, useState } from 'react';
import { ImagePlus, Trash2 } from 'lucide-react';
import { useToast } from '@/design-system/primitives';
import { ModaleConfirmation } from '@/common/ModaleConfirmation';
import { cx } from '@/common/cx';
import { api, ErreurApi, recupererBlob, televerser } from '@/lib/api';
import styles from './DepotImagesEod.module.css';

interface DocumentEod {
  id: string;
  nom: string;
  type_mime: string;
  taille: number;
  depose_par: string | null;
  depose_le: string;
}

interface Props {
  soireeId: string;
  peutEcrire: boolean;
}

/**
 * Les captures d'écran de la nuit — le pied du rapport.
 *
 * Le rapport que la Production remettait se terminait par une capture du core banking : l'état
 * des batchs, la date système, la sortie du planificateur. C'est la preuve que ce qui est pointé
 * au-dessus a bien eu lieu, et la hiérarchie la lit après le tableau. Ici elle se dépose sous le
 * déroulé, s'affiche sur toute sa largeur, et sort en pied du classeur Excel du rapport.
 *
 * Ce sont les pièces jointes ordinaires de la soirée (mêmes routes que les autres modules), dont
 * on ne montre ici que les images : un PDF joint reste consultable, mais n'a pas sa place dans
 * la page comme dans le rapport.
 */
export function DepotImagesEod({ soireeId, peutEcrire }: Props): JSX.Element {
  const { notifier } = useToast();
  const [images, setImages] = useState<DocumentEod[]>([]);
  const [apercus, setApercus] = useState<Record<string, string>>({});
  const [envoi, setEnvoi] = useState(false);
  const [survole, setSurvole] = useState(false);
  const [aSupprimer, setASupprimer] = useState<DocumentEod | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const base = `/eod/${soireeId}/documents`;

  const charger = useCallback(async (): Promise<void> => {
    const docs = await api.get<DocumentEod[]>(base);
    setImages(docs.filter((d) => d.type_mime.startsWith('image/')));
  }, [base]);

  useEffect(() => {
    void charger();
  }, [charger]);

  // Les aperçus se chargent une fois, et se libèrent quand l'image disparaît : un blob par
  // capture, jamais rechargé à chaque rendu.
  useEffect(() => {
    let annule = false;
    const manquantes = images.filter((d) => !(d.id in apercus));
    if (manquantes.length === 0) return undefined;
    void Promise.all(
      manquantes.map(async (d) => [
        d.id,
        URL.createObjectURL(await recupererBlob(`${base}/${d.id}`)),
      ]),
    ).then((paires) => {
      if (!annule) setApercus((a) => ({ ...a, ...Object.fromEntries(paires) }));
    });
    return () => {
      annule = true;
    };
  }, [images, apercus, base]);

  const deposer = async (fichiers: File[]): Promise<void> => {
    const valides = fichiers.filter((f) => f.type.startsWith('image/'));
    if (valides.length === 0) {
      notifier('Déposez une image — capture d’écran, photo du terminal.', 'erreur');
      return;
    }
    setEnvoi(true);
    try {
      for (const f of valides) await televerser(base, f);
      await charger();
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Le dépôt a échoué.', 'erreur');
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <section className={styles.bloc} aria-label="Captures de la nuit">
      {images.map((d) => (
        <figure key={d.id} className={styles.capture}>
          {apercus[d.id] !== undefined ? (
            <img src={apercus[d.id]} alt={d.nom} className={styles.image} />
          ) : (
            <div className={styles.chargement} aria-hidden="true" />
          )}
          <figcaption className={styles.legende}>
            <span className={styles.nom}>{d.nom}</span>
            {peutEcrire && (
              <button
                type="button"
                className={styles.retirer}
                title="Retirer cette capture"
                aria-label={`Retirer ${d.nom}`}
                onClick={() => setASupprimer(d)}
              >
                <Trash2 size={14} />
              </button>
            )}
          </figcaption>
        </figure>
      ))}

      {peutEcrire && (
        <div
          role="button"
          tabIndex={0}
          className={cx(styles.depot, survole && styles.depotSurvole, envoi && styles.depotOccupe)}
          onClick={() => !envoi && input.current?.click()}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') input.current?.click();
          }}
          onDragOver={(e) => {
            e.preventDefault();
            setSurvole(true);
          }}
          onDragLeave={() => setSurvole(false)}
          onDrop={(e) => {
            e.preventDefault();
            setSurvole(false);
            void deposer(Array.from(e.dataTransfer.files));
          }}
        >
          <input
            ref={input}
            type="file"
            accept="image/*"
            multiple
            hidden
            onChange={(e) => {
              void deposer(Array.from(e.target.files ?? []));
              e.target.value = '';
            }}
          />
          <ImagePlus size={20} className={styles.depotIcone} />
          <span className={styles.depotTexte}>
            {envoi ? 'Dépôt…' : 'Déposer la capture d’écran de la nuit'}
          </span>
          <span className={styles.depotSous}>
            Elle s’affiche ici sur toute la largeur, et sort en pied du rapport Excel.
          </span>
        </div>
      )}

      <ModaleConfirmation
        demande={
          aSupprimer === null
            ? null
            : {
                titre: 'Retirer cette capture',
                message: `« ${aSupprimer.nom} » sera retirée de la soirée et du rapport.`,
                libelleConfirmer: 'Retirer',
                variante: 'danger',
                action: async () => {
                  await api.del(`${base}/${aSupprimer.id}`);
                  await charger();
                },
              }
        }
        onFermer={() => setASupprimer(null)}
      />
    </section>
  );
}
