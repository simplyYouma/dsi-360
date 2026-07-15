import { FileText, FileSpreadsheet } from 'lucide-react';
import { Button } from '@/design-system/primitives';
import { telecharger } from '@/lib/api';

/** Couleur sémantique d'un format d'export : bordure teintée + icône/texte de la couleur du sens. */
function styleFormat(couleur: string): React.CSSProperties {
  return {
    color: couleur,
    borderColor: `color-mix(in srgb, ${couleur} 45%, var(--border))`,
  };
}

/** Boutons d'export CSV / Excel pour une liste (ex. base="/incidents"). */
export function BoutonsExport({ base }: { base: string }): JSX.Element {
  return (
    <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
      <Button
        variante="secondaire"
        style={styleFormat('var(--cat-1)')}
        onClick={() => void telecharger(`${base}/export?format=csv`)}
      >
        <FileText size={16} />
        CSV
      </Button>
      <Button
        variante="secondaire"
        style={styleFormat('var(--status-ok)')}
        onClick={() => void telecharger(`${base}/export?format=xlsx`)}
      >
        <FileSpreadsheet size={16} />
        Excel
      </Button>
    </div>
  );
}
