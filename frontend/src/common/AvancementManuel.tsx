import { useEffect, useRef, useState } from 'react';
import { Check, Quote, X } from 'lucide-react';
import { Button, Modale } from '@/design-system/primitives';
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

/** Pas de curseur libre : dix crans lisibles, et un chiffre rond au bout. Un avancement se raconte
 *  en dizaines, pas au pour-cent près — un pas trop fin inviterait à mentir sur la précision de ce
 *  qu'on sait réellement. */
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
 * Bandeau d'avancement d'un sujet de gouvernance — **déclaré**, par opposition à celui des projets
 * qui se déduit des tâches terminées.
 *
 * Il s'accroche sous l'en-tête de la fiche, pleine largeur : « où en est-on ? » est la première
 * question qu'on se pose en ouvrant un sujet de COPIL, pas une ligne de détail parmi d'autres.
 *
 * Deux règles portent tout le composant :
 *
 * 1. **Rien ne s'enregistre sans justification.** Choisir un cran n'écrit pas — il ouvre une
 *    demande de motif, et le bouton reste inactif tant qu'il n'y a pas de quoi relire la décision
 *    dans six mois. Le serveur refuse de son côté ; l'écran ne fait que l'annoncer plus tôt.
 * 2. **Le composant ne décide de rien.** `modifiable` vient de `peut_avancer`, calculé par le
 *    serveur : le gestionnaire rend compte, le contributeur travaille.
 *
 * Les justifications passées vivent en pastilles sous la barre. Au clic, la pastille **s'ouvre sur
 * place** — elle grandit et déploie son texte entier, sans quitter la fiche ni empiler une modale
 * par-dessus celle qu'on lit déjà.
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
  const [ouverte, setOuverte] = useState<number | null>(null);
  const champ = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (choisi !== null) champ.current?.focus();
  }, [choisi]);

  const suffisant = motif.trim().length >= 3;
  // La plus récente d'abord : c'est celle qui explique où l'on en est aujourd'hui.
  const recentes = [...justifications].reverse();

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
    <section className={styles.bandeau} aria-label="Avancement du sujet">
      <div className={styles.tete}>
        <span className={styles.chiffre}>
          {valeur}
          <span className={styles.pourcent}>%</span>
        </span>
        <div className={styles.piste}>
          <div className={styles.rail}>
            <div
              className={valeur === 100 ? styles.remplissageComplet : styles.remplissage}
              style={{ width: `${valeur}%` }}
            />
          </div>

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
                  {v}
                </button>
              ))}
            </div>
          ) : (
            <p className={styles.verrou} title={raisonVerrou}>
              {raisonVerrou ?? 'Seul le gestionnaire du sujet déclare son avancement.'}
            </p>
          )}
        </div>
      </div>

      {recentes.length > 0 && (
        <ul className={styles.motifs}>
          {recentes.map((j, i) => {
            const active = ouverte === i;
            return (
              <li key={`${j.horodatage}-${i}`} className={active ? styles.motifOuvert : undefined}>
                <button
                  type="button"
                  className={active ? styles.pastilleOuverte : styles.pastille}
                  onClick={() => setOuverte(active ? null : i)}
                  aria-expanded={active}
                  title={active ? 'Replier' : 'Lire en entier'}
                >
                  <Quote size={13} className={styles.guillemet} aria-hidden="true" />
                  <span className={active ? styles.texteEntier : styles.texteCoupe}>{j.texte}</span>
                  {active && (
                    <span className={styles.signature}>
                      {j.auteur ?? 'Auteur inconnu'} · {horodate(j.horodatage)}
                    </span>
                  )}
                </button>
              </li>
            );
          })}
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
    </section>
  );
}
