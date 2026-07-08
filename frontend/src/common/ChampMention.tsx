import { useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { AtSign } from 'lucide-react';
import type { AgentRef } from '@/common/useAgents';
import styles from './ChampMention.module.css';

interface Props {
  valeur: string;
  onChange: (v: string) => void;
  agents: AgentRef[];
  placeholder?: string;
  rows?: number;
  className?: string | undefined;
  /** Entrée simple (sans Maj) envoie le message. */
  onEnvoyer?: () => void;
}

/** Position du « token » @ en cours de frappe (du @ jusqu'au curseur, sans espace). */
function tokenActif(texte: string, curseur: number): { debut: number; requete: string } | null {
  const avant = texte.slice(0, curseur);
  const at = avant.lastIndexOf('@');
  if (at < 0) return null;
  // Le @ doit être en début de texte ou précédé d'un espace / saut de ligne.
  if (at > 0 && !/\s/.test(avant[at - 1] ?? '')) return null;
  const fragment = avant.slice(at + 1);
  if (/\s/.test(fragment)) return null; // un espace ferme la mention
  return { debut: at, requete: fragment };
}

/** Zone de texte avec autocomplétion @ : mentionner un agent DSI dans une discussion. */
export function ChampMention({
  valeur,
  onChange,
  agents,
  placeholder,
  rows = 2,
  className,
  onEnvoyer,
}: Props): JSX.Element {
  const ref = useRef<HTMLTextAreaElement>(null);
  const [token, setToken] = useState<{ debut: number; requete: string } | null>(null);
  const [surligne, setSurligne] = useState(0);
  const [pos, setPos] = useState<{ left: number; top: number; width: number } | null>(null);

  const suggestions = token
    ? agents
        .filter((a) => a.nom.toLowerCase().includes(token.requete.toLowerCase()))
        .slice(0, 6)
    : [];

  const majToken = (): void => {
    const el = ref.current;
    if (!el) return;
    const t = tokenActif(el.value, el.selectionStart ?? el.value.length);
    setToken(t);
    setSurligne(0);
    if (t) {
      const r = el.getBoundingClientRect();
      setPos({ left: r.left, top: r.bottom + 4, width: Math.max(220, r.width) });
    }
  };

  useLayoutEffect(() => {
    majToken();
  }, [valeur]);

  const inserer = (agent: AgentRef): void => {
    if (!token) return;
    const el = ref.current;
    const curseur = el?.selectionStart ?? valeur.length;
    const avant = valeur.slice(0, token.debut);
    const apres = valeur.slice(curseur);
    const nouveau = `${avant}@${agent.nom} ${apres}`;
    onChange(nouveau);
    setToken(null);
    // Replace le curseur juste après la mention insérée.
    requestAnimationFrame(() => {
      const p = `${avant}@${agent.nom} `.length;
      el?.focus();
      el?.setSelectionRange(p, p);
    });
  };

  return (
    <>
      <textarea
        ref={ref}
        className={className}
        value={valeur}
        rows={rows}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        onClick={majToken}
        onKeyUp={majToken}
        onKeyDown={(e) => {
          if (token && suggestions.length > 0) {
            if (e.key === 'ArrowDown') {
              e.preventDefault();
              setSurligne((s) => (s + 1) % suggestions.length);
            } else if (e.key === 'ArrowUp') {
              e.preventDefault();
              setSurligne((s) => (s - 1 + suggestions.length) % suggestions.length);
            } else if (e.key === 'Enter' || e.key === 'Tab') {
              e.preventDefault();
              const choisi = suggestions[surligne];
              if (choisi) inserer(choisi);
            } else if (e.key === 'Escape') {
              setToken(null);
            }
            return;
          }
          if (e.key === 'Enter' && !e.shiftKey && onEnvoyer) {
            e.preventDefault();
            onEnvoyer();
          }
        }}
        onBlur={() => window.setTimeout(() => setToken(null), 120)}
      />
      {token && suggestions.length > 0 && pos !== null &&
        createPortal(
          <ul
            className={styles.menu}
            style={{ position: 'fixed', left: pos.left, top: pos.top, width: pos.width }}
          >
            {suggestions.map((a, i) => (
              <li key={a.id}>
                <button
                  type="button"
                  className={i === surligne ? styles.optionActive : styles.option}
                  // onMouseDown (pas onClick) : agit avant le blur du textarea.
                  onMouseDown={(e) => {
                    e.preventDefault();
                    inserer(a);
                  }}
                >
                  <AtSign size={13} />
                  <span>{a.nom}</span>
                  {a.profil && <span className={styles.profil}>{a.profil}</span>}
                </button>
              </li>
            ))}
          </ul>,
          document.body,
        )}
    </>
  );
}
