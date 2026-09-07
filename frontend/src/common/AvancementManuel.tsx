import { useEffect, useRef, useState } from 'react';
import { Check, MessageSquareQuote, X } from 'lucide-react';
import { Button, Modale } from '@/design-system/primitives';
import { BarreAvancement } from './BarreAvancement';
import styles from './AvancementManuel.module.css';

/** Une justification déjà consignée : ce qui a bougé, et pourquoi. */
export interface JustificationAvancement {
  texte: string;
  auteur: string | null;
  horodatage: string;
}

interface Props {
  valeur: number;
  /** Faux : la barre se lit, elle ne se manipule pas. La permission vient du serveur. */
  modifiable: boolean;
  /** Motif exigé : le bouton reste inactif tant qu'il n'y a pas de quoi relire la décision. */
  onValider: (valeur: number, justification: string) => Promise<void> | void;
  justifications?: JustificationAvancement[];
  /** Raison du grisage, en infobulle : on n'interdit jamais sans dire pourquoi. */
  raisonVerrou?: string;
}

/** Pas de curseur libre : dix crans lisibles, et un chiffre rond au bout. Un avancement se
 *  raconte en dizaines, pas au pour-cent près — et un pas trop fin invite à mentir sur la
 *  précision de ce qu'on sait. */
const PAS = 10;
const CRANS = Array.from({ length: 100 / PAS + 1 }, (_, i) => i * PAS);

function horodate(iso: string): string {
  return new Date(iso).toLocaleString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Avancement **déclaré** d'un sujet de gouvernance — par opposition à celui des projets, déduit
 * des tâches terminées.
 *
 * Deux règles portent tout le composant :
 *
 * 1. **Rien ne s'enregistre sans justification.** Choisir un cran n'écrit pas : il ouvre une
 *    demande de motif, et le bouton reste inactif tant qu'il n'y a pas de quoi relire la décision
 *    dans six mois. Le serveur refuse de son côté — l'écran ne fait que l'annoncer plus tôt.
 * 2. **Le composant ne décide de rien.** `modifiable` vient de la permission calculée par le
 *    serveur (`peut_avancer`). Le gestionnaire rend compte ; le contributeur, lui, travaille.
 *
 * Les justifications passées s'affichent en pastilles discrètes. Au clic, le texte s'ouvre en
 * grand : une note écrite pour être relue ne doit pas rester coupée à trois mots.
 */
export function AvancementManuel({
  valeur,
  modifiable,
  onValider,
  justifications = [],
  raisonVerrou,
}: Props): JSX.Element {
  const [choisi, setChoisi] = useState<number | null>(null);
  const [motif, setMotif] = useState('');
  const [envoi, setEnvoi] = useState(false);
  const [ouverte, setOuverte] = useState<JustificationAvancement | null>(null);
  const champ = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (choisi !== null) champ.current?.focus();
  }, [choisi]);

  const suffisant = motif.trim().length >= 3;

  const demander = (v: number): void => {
    if (!modifiable || v === valeur) return;
    setMotif('');
    setChoisi(v);
  };

  const enregistrer = async (): Promise<void> => {
    if (choisi === null || !suffisant) return;
    setEnvoi(true);
    try {
      await onValider(choisi, motif.trim());
      setChoisi(null);
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <div className={styles.bloc}>
      <BarreAvancement valeur={valeur} />

      {modifiable ? (
        <div
          className={styles.crans}
          role="group"
          aria-label="Déclarer l’avancement"
          onKeyDown={(e) => {
            // Pilotable au clavier : la charte proscrit les composants natifs, elle n'excuse
            // pas de rendre le geste inaccessible à qui n'utilise pas la souris.
            if (e.key === 'ArrowRight' || e.key === 'ArrowUp') {
              e.preventDefault();
              demander(Math.min(100, valeur + PAS));
            }
            if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') {
              e.preventDefault();
              demander(Math.max(0, valeur - PAS));
            }
          }}
        >
          {CRANS.map((v) => (
            <button
              key={v}
              type="button"
              className={v <= valeur ? styles.cranAtteint : styles.cran}
              onClick={() => demander(v)}
              title={`Déclarer ${v} %`}
              aria-label={`Déclarer ${v} %`}
              aria-pressed={v === valeur}
            >
              <span className={styles.cranValeur}>{v}</span>
            </button>
          ))}
        </div>
      ) : (
        <p className={styles.verrou} title={raisonVerrou}>
          {raisonVerrou ?? 'Seul le gestionnaire du sujet déclare son avancement.'}
        </p>
      )}

      {justifications.length > 0 && (
        <ul className={styles.motifs}>
          {justifications.map((j, i) => (
            <li key={`${j.horodatage}-${i}`}>
              <button
                type="button"
                className={styles.motif}
                onClick={() => setOuverte(j)}
                title="Lire la justification en entier"
              >
                <MessageSquareQuote size={13} />
                <span className={styles.motifTexte}>{j.texte}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* Le motif : ce qu'on écrit ici se relira dans six mois, quand personne ne se souviendra. */}
      <Modale
        ouverte={choisi !== null}
        onFermer={() => setChoisi(null)}
        titre={choisi !== null ? `Avancement : ${valeur} % → ${choisi} %` : 'Avancement'}
        pied={
          <>
            <Button variante="secondaire" onClick={() => setChoisi(null)} disabled={envoi}>
              <X size={15} />
              Annuler
            </Button>
            <Button onClick={() => void enregistrer()} disabled={envoi || !suffisant}>
              <Check size={15} />
              {envoi ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </>
        }
      >
        <label className={styles.champ}>
          <span>Qu’est-ce qui a avancé ?</span>
          <textarea
            ref={champ}
            value={motif}
            rows={3}
            maxLength={500}
            placeholder="Ex. livrables reçus du prestataire, COPIL du 12/09 tenu, arbitrage rendu…"
            onChange={(e) => setMotif(e.target.value)}
          />
        </label>
        <p className={styles.aide}>
          Obligatoire : un pourcentage seul ne se relit pas. Cette phrase rejoint le dossier et son
          journal.
        </p>
      </Modale>

      {/* La justification en grand : elle a été écrite pour être lue, pas pour tenir en pastille. */}
      <Modale
        ouverte={ouverte !== null}
        onFermer={() => setOuverte(null)}
        titre="Justification"
        pied={
          <Button variante="secondaire" onClick={() => setOuverte(null)}>
            Fermer
          </Button>
        }
      >
        <p className={styles.motifOuvert}>{ouverte?.texte}</p>
        <p className={styles.aide}>
          {ouverte?.auteur ?? 'Auteur inconnu'} · {ouverte ? horodate(ouverte.horodatage) : ''}
        </p>
      </Modale>
    </div>
  );
}
