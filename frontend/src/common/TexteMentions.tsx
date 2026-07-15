import { Fragment } from 'react';
import type { AgentRef } from '@/common/useAgents';

interface Props {
  texte: string;
  agents: AgentRef[];
}

/** URL http(s) dans un texte de discussion. Capture large ; la ponctuation finale est retirée. */
export const URL_REGEX = /https?:\/\/[^\s<]+/g;

/** Première URL d'un texte (ponctuation finale retirée), ou null. */
export function premiereUrl(texte: string): string | null {
  const m = texte.match(URL_REGEX);
  return m ? m[0].replace(/[.,;:!?)\]]+$/, '') : null;
}

/** Affiche un texte de discussion : mentions « @Nom » surlignées et URL http(s) cliquables. */
export function TexteMentions({ texte, agents }: Props): JSX.Element {
  const noms = agents.map((a) => a.nom).filter(Boolean);
  // Mentions connues (plus longues d'abord) OU URL. Une seule passe pour ne pas casser les indices.
  const motifNoms = noms
    .slice()
    .sort((a, b) => b.length - a.length)
    .map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    .join('|');
  const source = motifNoms !== '' ? `@(?:${motifNoms})|${URL_REGEX.source}` : URL_REGEX.source;
  const regex = new RegExp(source, 'g');

  const morceaux: (string | JSX.Element)[] = [];
  let dernier = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = regex.exec(texte)) !== null) {
    if (m.index > dernier) morceaux.push(texte.slice(dernier, m.index));
    const brut = m[0];
    if (brut.startsWith('@')) {
      morceaux.push(
        <strong key={i} style={{ color: 'var(--secondary)', fontWeight: 'var(--weight-semibold)' }}>
          {brut}
        </strong>,
      );
      dernier = m.index + brut.length;
    } else {
      // On laisse la ponctuation finale hors du lien (elle appartient à la phrase, pas à l'URL).
      const suffixe = brut.match(/[.,;:!?)\]]+$/)?.[0] ?? '';
      const url = suffixe ? brut.slice(0, -suffixe.length) : brut;
      morceaux.push(
        <a
          key={i}
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: 'var(--secondary)', textDecoration: 'underline' }}
        >
          {url}
        </a>,
      );
      if (suffixe) morceaux.push(suffixe);
      dernier = m.index + brut.length;
    }
    i += 1;
  }
  if (dernier < texte.length) morceaux.push(texte.slice(dernier));

  return (
    <>
      {morceaux.map((mc, idx) => (
        <Fragment key={idx}>{mc}</Fragment>
      ))}
    </>
  );
}
