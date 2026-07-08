import { Fragment } from 'react';
import type { AgentRef } from '@/common/useAgents';

interface Props {
  texte: string;
  agents: AgentRef[];
}

/** Affiche un texte de discussion en surlignant les mentions « @Nom » d'agents connus. */
export function TexteMentions({ texte, agents }: Props): JSX.Element {
  const noms = agents.map((a) => a.nom).filter(Boolean);
  if (noms.length === 0) return <>{texte}</>;

  // Regex des noms connus, précédés d'un @, plus longs d'abord (évite les préfixes partiels).
  const motif = noms
    .sort((a, b) => b.length - a.length)
    .map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    .join('|');
  const regex = new RegExp(`@(${motif})`, 'g');

  const morceaux: (string | JSX.Element)[] = [];
  let dernier = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = regex.exec(texte)) !== null) {
    if (m.index > dernier) morceaux.push(texte.slice(dernier, m.index));
    morceaux.push(
      <strong key={i} style={{ color: 'var(--secondary)', fontWeight: 'var(--weight-semibold)' }}>
        {m[0]}
      </strong>,
    );
    dernier = m.index + m[0].length;
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
