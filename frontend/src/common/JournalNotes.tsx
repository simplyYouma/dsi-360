import { useCallback, useEffect, useState } from 'react';
import { Send } from 'lucide-react';
import { Button } from '@/design-system/primitives';
import { couleurStatut } from '@/common/statuts';
import fiche from './FicheTransition.module.css';

export interface NoteJournal {
  id: string;
  texte: string;
  contexte: string | null;
  auteur: string | null;
  cree_le: string;
}

interface Props {
  charger: () => Promise<NoteJournal[]>;
  creer: (texte: string) => Promise<unknown>;
  /** Incrémenter pour forcer un rechargement (ex. justification ajoutée par une transition). */
  version?: number;
  placeholder?: string;
}

/** Journal de bord : notes horodatées (dont les justifications de suspension/clôture). */
export function JournalNotes({
  charger,
  creer,
  version = 0,
  placeholder = "Ajouter une note (décision, point d'étape…)",
}: Props): JSX.Element {
  const [notes, setNotes] = useState<NoteJournal[]>([]);
  const [texte, setTexte] = useState('');
  const [envoi, setEnvoi] = useState(false);

  const recharger = useCallback((): void => {
    void charger().then(setNotes);
  }, [charger]);
  useEffect(() => recharger(), [recharger, version]);

  const ajouter = async (): Promise<void> => {
    if (texte.trim().length < 3) return;
    setEnvoi(true);
    try {
      await creer(texte.trim());
      setTexte('');
      recharger();
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <div style={{ minWidth: 0 }}>
      {notes.length === 0 && <p className={fiche.commVide}>Aucune note pour le moment.</p>}
      {notes.length > 0 && (
        <ul className={fiche.commListe}>
          {notes.map((n) => (
            <li key={n.id} className={fiche.commItem}>
              <div className={fiche.commTete}>
                <span className={fiche.commAuteur}>
                  {n.auteur ?? '—'}
                  {n.contexte !== null && (
                    <span
                      style={{
                        marginLeft: 'var(--space-2)',
                        color: couleurStatut(n.contexte),
                        fontSize: 'var(--text-xs)',
                        fontWeight: 600,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {n.contexte}
                    </span>
                  )}
                </span>
                <span className={fiche.commDate}>
                  {new Date(n.cree_le).toLocaleString('fr-FR', {
                    day: '2-digit',
                    month: '2-digit',
                    year: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
              </div>
              <p className={fiche.commTexte}>{n.texte}</p>
            </li>
          ))}
        </ul>
      )}
      <div className={fiche.commForm} style={{ marginTop: 'var(--space-4)' }}>
        <textarea
          className={fiche.commInput}
          value={texte}
          onChange={(e) => setTexte(e.target.value)}
          rows={2}
          placeholder={placeholder}
        />
        <Button onClick={() => void ajouter()} disabled={envoi || texte.trim().length < 3}>
          <Send size={14} />
          {envoi ? 'Envoi…' : 'Noter'}
        </Button>
      </div>
    </div>
  );
}
