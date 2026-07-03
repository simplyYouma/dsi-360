import { useState, type RefObject } from 'react';
import { FileDown } from 'lucide-react';
import { Button, useToast } from '@/design-system/primitives';
import { exporterVisuelsPdf } from './exportPdf';

interface Props {
  /** Élément dont on capture les visuels (mode clair forcé). */
  cible: RefObject<HTMLElement | null>;
  titre: string;
  nomFichier: string;
}

/** Bouton « Exporter PDF » : capture les visuels de `cible` dans un document structuré. */
export function BoutonExportPdf({ cible, titre, nomFichier }: Props): JSX.Element {
  const [enCours, setEnCours] = useState(false);
  const { notifier } = useToast();

  const exporter = async (): Promise<void> => {
    if (cible.current === null) return;
    setEnCours(true);
    try {
      await exporterVisuelsPdf(cible.current, titre, nomFichier);
    } catch {
      notifier('Export PDF impossible.', 'erreur');
    } finally {
      setEnCours(false);
    }
  };

  return (
    <Button variante="secondaire" onClick={() => void exporter()} disabled={enCours}>
      <FileDown size={16} />
      {enCours ? 'Export…' : 'Exporter PDF'}
    </Button>
  );
}
