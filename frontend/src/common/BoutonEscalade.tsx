import { useState } from 'react';
import { ArrowUpRight } from 'lucide-react';
import { Button, Modale, useToast } from '@/design-system/primitives';
import { api, ErreurApi } from '@/lib/api';
import fiche from './FicheTransition.module.css';

interface Props {
  /** Préfixe du module, ex. « /incidents ». */
  base: string;
  id: string;
  niveau: number;
  transfereDbs: boolean;
  sansGestionnaire: boolean;
  onChange: () => void;
}

/** Niveau 3 = DBS, qui n'a aucun compte dans le système (ADR-0003 §3). */
const NIVEAU_DBS = 3;

/** Niveau de support du ticket, et escalade d'un cran.
 *
 *  La DSI tient N1 et N2. Escalader depuis le N2 — ou escalader un ticket que personne n'a pris —
 *  le transfère à DBS : le travail sort de la plateforme. C'est irréversible, donc confirmé.
 *  Le gestionnaire reste référent du suivi et de la relance ; le SLA continue de courir. */
export function BoutonEscalade({
  base,
  id,
  niveau,
  transfereDbs,
  sansGestionnaire,
  onChange,
}: Props): JSX.Element {
  const { notifier } = useToast();
  const [confirmation, setConfirmation] = useState(false);
  const [envoi, setEnvoi] = useState(false);

  const versDbs = sansGestionnaire || niveau >= NIVEAU_DBS - 1;

  const escalader = async (): Promise<void> => {
    setEnvoi(true);
    try {
      await api.post(`${base}/${id}/escalader`);
      setConfirmation(false);
      onChange();
      notifier(versDbs ? 'Transféré à DBS' : `Escaladé au niveau N${niveau + 1}`, 'succes');
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Escalade impossible.', 'erreur');
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <div className={fiche.escalade}>
      <span
        className={fiche.niveau}
        title={
          transfereDbs
            ? 'Traité par DBS, hors de la plateforme'
            : `Support de niveau ${niveau} à la DSI`
        }
      >
        {transfereDbs ? 'DBS' : `N${niveau}`}
      </span>

      {transfereDbs ? (
        <span className={fiche.valeur}>Transféré à DBS — vous en restez référent</span>
      ) : (
        <Button
          variante="secondaire"
          onClick={() => (versDbs ? setConfirmation(true) : void escalader())}
          disabled={envoi}
        >
          <ArrowUpRight size={16} />
          {versDbs ? 'Transférer à DBS' : `Escalader en N${niveau + 1}`}
        </Button>
      )}

      <Modale
        ouverte={confirmation}
        onFermer={() => setConfirmation(false)}
        titre="Transférer à DBS ?"
        pied={
          <>
            <Button variante="secondaire" onClick={() => setConfirmation(false)} disabled={envoi}>
              Annuler
            </Button>
            <Button onClick={() => void escalader()} disabled={envoi}>
              Transférer à DBS
            </Button>
          </>
        }
      >
        <p>
          {sansGestionnaire
            ? 'Personne à la DSI n’a pris ce ticket. Le transférer à DBS le confie à une équipe qui ne travaille pas dans cette plateforme.'
            : 'La DSI ne va pas au-delà du N2. Le travail passe à DBS, qui n’a pas de compte ici.'}
        </p>
        <p>
          Vous en restez référent : suivi, relance et clôture. L’échéance SLA continue de courir. Le
          transfert ne peut pas être annulé depuis la plateforme.
        </p>
      </Modale>
    </div>
  );
}
