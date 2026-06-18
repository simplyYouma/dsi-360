import { Download } from 'lucide-react';
import { Button } from '@/design-system/primitives';
import { telecharger } from '@/lib/api';

/** Boutons d'export CSV / Excel pour une liste (ex. base="/incidents"). */
export function BoutonsExport({ base }: { base: string }): JSX.Element {
  return (
    <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
      <Button variante="secondaire" onClick={() => void telecharger(`${base}/export?format=csv`)}>
        <Download size={16} />
        CSV
      </Button>
      <Button variante="secondaire" onClick={() => void telecharger(`${base}/export?format=xlsx`)}>
        <Download size={16} />
        Excel
      </Button>
    </div>
  );
}
