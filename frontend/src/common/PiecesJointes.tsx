import { useCallback, useEffect, useRef, useState } from 'react';
import { Download, Eye, Paperclip, Upload } from 'lucide-react';
import { useToast } from '@/design-system/primitives';
import { ApercuDocument } from '@/common/ApercuDocument';
import { BoutonSupprimer } from '@/common/BoutonSupprimer';
import { ChampInline } from '@/common/ChampInline';
import { cx } from '@/common/cx';
import { ErreurApi } from '@/lib/api';
import styles from './PiecesJointes.module.css';

export interface PieceJointe {
  id: string;
  nom: string;
  type_mime: string;
  taille: number;
}

interface Props {
  charger: () => Promise<PieceJointe[]>;
  deposer: (f: File) => Promise<unknown>;
  telecharger: (docId: string) => Promise<void>;
  apercu: (docId: string) => Promise<Blob>;
  renommer: (docId: string, nom: string) => Promise<unknown>;
  supprimer: (docId: string) => Promise<void>;
  /** Variante compacte (pièces jointes d'une tâche). */
  compact?: boolean;
}

function formaterTaille(octets: number): string {
  if (octets < 1024) return `${octets} o`;
  if (octets < 1024 * 1024) return `${Math.round(octets / 1024)} Ko`;
  return `${(octets / (1024 * 1024)).toFixed(1)} Mo`;
}

/** Pièces jointes (projet, changement, tâche…) : dépôt, aperçu au clic, renommage, suppression. */
export function PiecesJointes({
  charger,
  deposer,
  telecharger,
  apercu,
  renommer,
  supprimer,
  compact,
}: Props): JSX.Element {
  const [docs, setDocs] = useState<PieceJointe[]>([]);
  const [envoi, setEnvoi] = useState(false);
  const [surviole, setSurviole] = useState(false);
  const [vue, setVue] = useState<{ url: string; type: string; nom: string; docId: string } | null>(
    null,
  );
  const input = useRef<HTMLInputElement>(null);
  const { notifier } = useToast();

  const recharger = useCallback((): void => {
    void charger().then(setDocs);
    // charger est recréé à chaque rendu par l'appelant ; on ne le met pas en dépendance.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => recharger(), [recharger]);

  const envoyer = async (fichiers: File[]): Promise<void> => {
    if (fichiers.length === 0) return;
    setEnvoi(true);
    try {
      for (const f of fichiers) await deposer(f);
      recharger();
      notifier('Document déposé', 'succes');
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Dépôt impossible.', 'erreur');
    } finally {
      setEnvoi(false);
    }
  };

  const retirer = async (docId: string): Promise<void> => {
    try {
      await supprimer(docId);
      recharger();
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Suppression impossible.', 'erreur');
    }
  };

  const visualiser = async (d: PieceJointe): Promise<void> => {
    try {
      const blob = await apercu(d.id);
      setVue({ url: URL.createObjectURL(blob), type: d.type_mime, nom: d.nom, docId: d.id });
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Aperçu impossible.', 'erreur');
    }
  };
  const fermerVue = (): void => {
    setVue((prec) => {
      if (prec) URL.revokeObjectURL(prec.url);
      return null;
    });
  };

  const nommer = async (docId: string, nom: string): Promise<void> => {
    if (nom.trim() === '') return;
    try {
      await renommer(docId, nom.trim());
      recharger();
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Renommage impossible.', 'erreur');
    }
  };

  return (
    <div className={styles.docs}>
      <input
        ref={input}
        type="file"
        hidden
        multiple
        onChange={(e) => {
          const f = Array.from(e.target.files ?? []);
          e.target.value = '';
          void envoyer(f);
        }}
      />
      <div
        role="button"
        tabIndex={0}
        className={cx(styles.dropzone, surviole && styles.dropzoneActif, compact && styles.dropCompact)}
        onClick={() => !envoi && input.current?.click()}
        onKeyDown={(e) => {
          if ((e.key === 'Enter' || e.key === ' ') && !envoi) {
            e.preventDefault();
            input.current?.click();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setSurviole(true);
        }}
        onDragLeave={() => setSurviole(false)}
        onDrop={(e) => {
          e.preventDefault();
          setSurviole(false);
          void envoyer(Array.from(e.dataTransfer.files ?? []));
        }}
      >
        <Upload size={compact ? 15 : 20} />
        <span>{envoi ? 'Dépôt…' : compact ? 'Ajouter une pièce jointe' : 'Glissez des fichiers ou cliquez'}</span>
      </div>
      {docs.map((d) => (
        <div key={d.id} className={styles.docLigne}>
          <button
            type="button"
            className={styles.docApercu}
            title={`Aperçu de ${d.nom}`}
            aria-label={`Aperçu de ${d.nom}`}
            onClick={() => void visualiser(d)}
          >
            <Paperclip size={13} />
          </button>
          <div className={styles.docNom}>
            <ChampInline
              valeur={d.nom}
              onValider={(nom) => void nommer(d.id, nom)}
              aria-label={`Renommer ${d.nom}`}
            />
          </div>
          <span className={styles.taille}>{formaterTaille(d.taille)}</span>
          <button type="button" className={styles.docAction} aria-label="Aperçu" title="Aperçu" onClick={() => void visualiser(d)}>
            <Eye size={14} />
          </button>
          <button type="button" className={styles.docAction} aria-label="Télécharger" title="Télécharger" onClick={() => void telecharger(d.id)}>
            <Download size={14} />
          </button>
          <BoutonSupprimer
            cible={`la pièce jointe « ${d.nom} »`}
            onSupprimer={() => retirer(d.id)}
            className={styles.docAction}
            taille={14}
          />
        </div>
      ))}
      {vue !== null && (
        <ApercuDocument
          url={vue.url}
          type={vue.type}
          nom={vue.nom}
          onFermer={fermerVue}
          onTelecharger={() => void telecharger(vue.docId)}
        />
      )}
    </div>
  );
}
