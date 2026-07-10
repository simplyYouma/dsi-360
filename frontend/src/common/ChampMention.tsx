import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { AtSign } from 'lucide-react';
import { cx } from './cx';
import type { AgentRef } from '@/common/useAgents';
import styles from './ChampMention.module.css';

interface Props {
  valeur: string;
  onChange: (v: string) => void;
  agents: AgentRef[];
  placeholder?: string | undefined;
  rows?: number;
  className?: string | undefined;
  /** Entrée simple (sans Maj) envoie le message. Maj+Entrée insère un saut de ligne. */
  onEnvoyer?: () => void;
  /** Images collées depuis le presse-papier (Ctrl+V d'une capture d'écran). */
  onImagesCollees?: (fichiers: File[]) => void;
}

/** Position du « token » @ en cours de frappe (du @ jusqu'au curseur, sans espace). */
function tokenActif(texte: string, curseur: number): { debut: number; requete: string } | null {
  const avant = texte.slice(0, curseur);
  const at = avant.lastIndexOf('@');
  if (at < 0) return null;
  if (at > 0 && !/\s/.test(avant[at - 1] ?? '')) return null;
  const fragment = avant.slice(at + 1);
  if (/\s/.test(fragment)) return null;
  return { debut: at, requete: fragment };
}

/** Découpe le texte en segments texte / mention (« @Nom » d'un agent connu). */
function segmenter(texte: string, agents: AgentRef[]): { t: string; mention: boolean }[] {
  const noms = agents
    .map((a) => a.nom)
    .filter(Boolean)
    .sort((a, b) => b.length - a.length);
  if (noms.length === 0) return [{ t: texte, mention: false }];
  const motif = noms.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
  const regex = new RegExp(`@(${motif})`, 'g');
  const out: { t: string; mention: boolean }[] = [];
  let dernier = 0;
  let m: RegExpExecArray | null;
  while ((m = regex.exec(texte)) !== null) {
    if (m.index > dernier) out.push({ t: texte.slice(dernier, m.index), mention: false });
    out.push({ t: m[0], mention: true });
    dernier = m.index + m[0].length;
  }
  if (dernier < texte.length) out.push({ t: texte.slice(dernier), mention: false });
  return out;
}

/** Zone de texte avec autocomplétion @ et surlignage inline des mentions (façon réseaux sociaux). */
export function ChampMention({
  valeur,
  onChange,
  agents,
  placeholder,
  rows = 2,
  className,
  onImagesCollees,
  onEnvoyer,
}: Props): JSX.Element {
  const ref = useRef<HTMLTextAreaElement>(null);
  const calque = useRef<HTMLDivElement>(null);
  const [token, setToken] = useState<{ debut: number; requete: string } | null>(null);
  const [surligne, setSurligne] = useState(0);
  const [pos, setPos] = useState<{ left: number; top: number; width: number } | null>(null);

  const suggestions = token
    ? agents.filter((a) => a.nom.toLowerCase().includes(token.requete.toLowerCase())).slice(0, 6)
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

  // Le menu est en position fixe : à tout défilement/redimensionnement, on le ferme (il rouvre à
  // la frappe) plutôt que de le laisser flotter détaché du champ.
  useEffect(() => {
    if (token === null) return;
    const fermer = (): void => setToken(null);
    window.addEventListener('scroll', fermer, true);
    window.addEventListener('resize', fermer);
    return () => {
      window.removeEventListener('scroll', fermer, true);
      window.removeEventListener('resize', fermer);
    };
  }, [token]);

  const inserer = (agent: AgentRef): void => {
    if (!token) return;
    const el = ref.current;
    const curseur = el?.selectionStart ?? valeur.length;
    const avant = valeur.slice(0, token.debut);
    const apres = valeur.slice(curseur);
    const prefixe = `${avant}@${agent.nom} `;
    onChange(`${prefixe}${apres}`);
    setToken(null);
    requestAnimationFrame(() => {
      el?.focus();
      el?.setSelectionRange(prefixe.length, prefixe.length);
    });
  };

  // Efface une mention entière d'un coup (pas lettre par lettre) quand le curseur la suit.
  const effacerMention = (el: HTMLTextAreaElement): boolean => {
    if (el.selectionStart !== el.selectionEnd) return false;
    const c = el.selectionStart;
    const avant = valeur.slice(0, c);
    const agent = agents
      .filter((a) => a.nom)
      .sort((a, b) => b.nom.length - a.nom.length)
      .find((a) => avant.endsWith(`@${a.nom}`));
    if (!agent) return false;
    const debut = c - `@${agent.nom}`.length;
    onChange(valeur.slice(0, debut) + valeur.slice(c));
    requestAnimationFrame(() => {
      el.focus();
      el.setSelectionRange(debut, debut);
    });
    return true;
  };

  const segments = segmenter(valeur, agents);

  return (
    <div className={cx(styles.wrap, className)}>
      <div ref={calque} className={styles.calque} aria-hidden="true">
        {segments.map((s, i) =>
          s.mention ? (
            <span key={i} className={styles.mention}>
              {s.t}
            </span>
          ) : (
            <span key={i}>{s.t}</span>
          ),
        )}
        {/* Une ligne vide finale doit rester visible dans le calque. */}
        {valeur.endsWith('\n') && ' '}
      </div>
      <textarea
        ref={ref}
        className={styles.saisie}
        value={valeur}
        rows={rows}
        placeholder={placeholder}
        onPaste={(e) => {
          if (!onImagesCollees) return;
          // Capture d'écran collée (Ctrl+V) : on l'attache au message plutôt que d'insérer du texte.
          const fichiers = [...e.clipboardData.files].filter((f) => f.type.startsWith('image/'));
          if (fichiers.length > 0) {
            e.preventDefault();
            onImagesCollees(fichiers);
          }
        }}
        onChange={(e) => onChange(e.target.value)}
        onScroll={() => {
          if (calque.current && ref.current) calque.current.scrollTop = ref.current.scrollTop;
        }}
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
          if (e.key === 'Backspace' && ref.current && effacerMention(ref.current)) {
            e.preventDefault();
            return;
          }
          if (e.key === 'Enter' && !e.shiftKey && onEnvoyer) {
            e.preventDefault();
            onEnvoyer();
          }
        }}
        onBlur={() => window.setTimeout(() => setToken(null), 120)}
      />
      {token &&
        suggestions.length > 0 &&
        pos !== null &&
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
    </div>
  );
}
