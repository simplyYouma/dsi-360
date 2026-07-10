import { useState, type MouseEvent } from 'react';
import { ImageDown } from 'lucide-react';
import { useToast } from '@/design-system/primitives';
import { exporterVisuelPng } from './exportVisuels';
import styles from './BoutonExportPng.module.css';

/**
 * Export PNG d'un visuel, discret : visible au survol de la carte, invisible dans la capture.
 * Le bouton retrouve son visuel par l'attribut `data-visuel` du parent — aucune ref à câbler.
 */
export function BoutonExportPng({ nom }: { nom: string }): JSX.Element {
  const [enCours, setEnCours] = useState(false);
  const { notifier } = useToast();

  const exporter = async (e: MouseEvent<HTMLButtonElement>): Promise<void> => {
    const cible = e.currentTarget.closest<HTMLElement>('[data-visuel]');
    if (cible === null) return;
    setEnCours(true);
    try {
      await exporterVisuelPng(cible, nom);
    } catch {
      notifier('Export PNG impossible.', 'erreur');
    } finally {
      setEnCours(false);
    }
  };

  return (
    <button
      type="button"
      className={styles.btn}
      data-export-ignore
      onClick={(e) => void exporter(e)}
      disabled={enCours}
      title={`Exporter « ${nom} » en PNG`}
      aria-label={`Exporter « ${nom} » en PNG`}
    >
      <ImageDown size={14} />
    </button>
  );
}
