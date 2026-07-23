import { useState } from 'react';
import { FileText, FileSpreadsheet, Loader2 } from 'lucide-react';
import { Button, useToast } from '@/design-system/primitives';
import { ErreurApi, telecharger } from '@/lib/api';
import styles from './BoutonsExport.module.css';

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
  // Un export de plusieurs milliers de lignes prend quelques secondes, sans que rien ne bouge
  // à l'écran : on cliquait deux ou trois fois, et le serveur préparait autant de fichiers.
  const [enCours, setEnCours] = useState<string | null>(null);
  const { notifier } = useToast();

  const lien = (format: string): string => {
    const p = new URLSearchParams({ format });
    for (const [cle, valeur] of Object.entries(filtres ?? {})) {
      if (valeur !== null && valeur !== undefined && valeur.trim() !== '') {
        p.set(cle, valeur.trim());
      }
    }
    return `${base}/export?${p.toString()}`;
  };

  const exporter = async (format: string): Promise<void> => {
    if (enCours !== null) return;
    setEnCours(format);
    try {
      await telecharger(lien(format));
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Export impossible.', 'erreur');
    } finally {
      setEnCours(null);
    }
  };

  const rendu = (
    format: string,
    libelle: string,
    couleur: string,
    Icone: typeof FileText,
  ): JSX.Element => (
    <Button
      variante="secondaire"
      style={styleFormat(couleur)}
      onClick={() => void exporter(format)}
      disabled={enCours !== null}
      title={enCours === format ? 'Préparation du fichier…' : `Exporter en ${libelle}`}
    >
      {enCours === format ? (
        <Loader2 size={16} className={styles.tourne} />
      ) : (
        <Icone size={16} />
      )}
      {enCours === format ? 'Préparation…' : libelle}
    </Button>
  );

  return (
    <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
      {rendu('csv', 'CSV', 'var(--cat-1)', FileText)}
      {rendu('xlsx', 'Excel', 'var(--status-ok)', FileSpreadsheet)}
    </div>
  );
}
