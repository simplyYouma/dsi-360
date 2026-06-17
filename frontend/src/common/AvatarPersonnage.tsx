import { useMemo } from 'react';
import { createAvatar } from '@dicebear/core';
import { notionistsNeutral } from '@dicebear/collection';

interface AvatarPersonnageProps {
  /** Graine stable (id ou e-mail) : une même personne donne toujours le même visage. */
  seed: string;
  taille?: number;
}

/** Avatar illustré DiceBear « Notionists Neutral » (hors-ligne, généré localement). */
export function AvatarPersonnage({ seed, taille = 36 }: AvatarPersonnageProps): JSX.Element {
  const uri = useMemo(
    () =>
      createAvatar(notionistsNeutral, {
        seed,
        size: taille,
        radius: 50,
        backgroundColor: ['f1f3f5'],
      }).toDataUri(),
    [seed, taille],
  );
  return (
    <img
      src={uri}
      width={taille}
      height={taille}
      alt=""
      aria-hidden="true"
      style={{ borderRadius: '50%', flex: '0 0 auto', display: 'block' }}
    />
  );
}
