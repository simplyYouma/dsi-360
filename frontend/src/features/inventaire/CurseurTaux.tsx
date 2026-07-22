import { useEffect, useState, type CSSProperties } from 'react';
import local from './Inventaire.module.css';

interface Props {
  valeur: number | null;
  /** Appelé au relâchement du curseur : un enregistrement par cran serait du bruit. */
  onValider: (taux: number | null) => void;
  desactive?: boolean;
}

/** Curseur de taux d'amortissement : la piste se remplit jusqu'au taux, la durée
 *  implicite se lit dessous. Un taux se choisit, il ne se rédige pas. */
export function CurseurTaux({ valeur, onValider, desactive = false }: Props): JSX.Element {
  const [brouillon, setBrouillon] = useState(valeur ?? 0);
  useEffect(() => setBrouillon(valeur ?? 0), [valeur]);

  const valider = (): void => {
    const taux = brouillon === 0 ? null : brouillon;
    if (taux !== valeur) onValider(taux);
  };

  return (
    <span className={local.curseurBloc}>
      <span className={local.curseur}>
        <input
          type="range"
          min={0}
          max={100}
          step={1}
          value={brouillon}
          onChange={(e) => setBrouillon(Number(e.target.value))}
          onPointerUp={valider}
          onKeyUp={valider}
          onBlur={valider}
          disabled={desactive}
          style={{ '--pct': `${brouillon}%` } as CSSProperties}
          aria-label="Taux d'amortissement"
        />
        <span className={local.curseurValeur}>{brouillon} %</span>
      </span>
      <span className={local.curseurNote}>
        {brouillon > 0
          ? `soit ${(100 / brouillon)
              .toFixed(1)
              .replace('.', ',')
              .replace(',0', '')} ans d'amortissement`
          : 'aucun amortissement'}
      </span>
    </span>
  );
}
