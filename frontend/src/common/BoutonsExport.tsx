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

/** Boutons d'export CSV / Excel pour une liste (ex. base="/incidents").
 *
 *  `filtres` : la vue courante, transmise à l'export. Un fichier qui dirait autre chose que
 *  l'écran dont il sort serait un piège — on exporte ce qu'on regarde.
 */
export function BoutonsExport({
  base,
  filtres,
}: {
  base: string;
  filtres?: Record<string, string | null | undefined>;
}): JSX.Element {
  const lien = (format: string): string => {
    const p = new URLSearchParams({ format });
    for (const [cle, valeur] of Object.entries(filtres ?? {})) {
      if (valeur !== null && valeur !== undefined && valeur.trim() !== '') {
        p.set(cle, valeur.trim());
      }
    }
    return `${base}/export?${p.toString()}`;
  };

  return (
    <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
      <Button
        variante="secondaire"
        style={styleFormat('var(--cat-1)')}
        onClick={() => void telecharger(lien('csv'))}
      >
        <FileText size={16} />
        CSV
      </Button>
      <Button
        variante="secondaire"
        style={styleFormat('var(--status-ok)')}
        onClick={() => void telecharger(lien('xlsx'))}
      >
        <FileSpreadsheet size={16} />
        Excel
      </Button>
    </div>
  );
}
