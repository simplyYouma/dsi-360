import { useCallback, useEffect, useState } from 'react';
import { ArrowRight } from 'lucide-react';
import { Button, Modale, Skeleton } from '@/design-system/primitives';
import { api, ErreurApi } from '@/lib/api';
import { BadgePriorite, BadgeSla, BadgeStatut, couleurStatut } from './statuts';
import styles from './FicheTransition.module.css';

interface Detail {
  reference: string;
  titre: string;
  statut: string;
  priorite: number;
  categorie: string | null;
  statut_sla: 'a_lheure' | 'approche' | 'depasse';
  sla_resolution_le: string | null;
  cree_le: string;
  responsable: { prenom: string; nom: string } | null;
  description: string | null;
  transitions_possibles: string[];
}

interface FicheTransitionProps {
  base: string;
  id: string | null;
  onFermer: () => void;
  onChange: () => void;
}

function formaterDate(iso: string | null): string {
  if (iso === null) return '—';
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

/** Fiche d'une activité : détails présentés proprement + transitions d'état (couleurs sémantiques). */
export function FicheTransition({ base, id, onFermer, onChange }: FicheTransitionProps): JSX.Element {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(async (): Promise<void> => {
    if (id === null) return;
    setDetail(null);
    setErreur(null);
    setDetail(await api.get<Detail>(`${base}/${id}`));
  }, [base, id]);

  useEffect(() => {
    void charger();
  }, [charger]);

  const transitionner = async (vers: string): Promise<void> => {
    if (id === null) return;
    setEnvoi(true);
    setErreur(null);
    try {
      setDetail(await api.post<Detail>(`${base}/${id}/transition`, { vers }));
      onChange();
    } catch (err) {
      setErreur(err instanceof ErreurApi ? err.message : 'Transition impossible.');
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <Modale
      ouverte={id !== null}
      onFermer={onFermer}
      titre={detail ? detail.reference : 'Fiche'}
      pied={
        <Button variante="secondaire" onClick={onFermer}>
          Fermer
        </Button>
      }
    >
      {detail === null ? (
        <div className={styles.fiche}>
          <Skeleton hauteur="22px" largeur="60%" />
          <Skeleton hauteur="64px" />
          <Skeleton hauteur="40px" />
        </div>
      ) : (
        <div className={styles.fiche}>
          <div className={styles.tete}>
            <h3 className={styles.titre}>{detail.titre}</h3>
            <BadgePriorite priorite={detail.priorite} />
          </div>

          <dl className={styles.meta}>
            <div className={styles.metaItem}>
              <dt>Statut</dt>
              <dd>
                <BadgeStatut statut={detail.statut} />
              </dd>
            </div>
            <div className={styles.metaItem}>
              <dt>Échéance SLA</dt>
              <dd>
                <BadgeSla etat={detail.statut_sla} />
              </dd>
            </div>
            <div className={styles.metaItem}>
              <dt>Catégorie</dt>
              <dd className={styles.valeur}>{detail.categorie ?? '—'}</dd>
            </div>
            <div className={styles.metaItem}>
              <dt>Responsable</dt>
              <dd className={styles.valeur}>
                {detail.responsable ? `${detail.responsable.prenom} ${detail.responsable.nom}` : '—'}
              </dd>
            </div>
            <div className={styles.metaItem}>
              <dt>Échéance</dt>
              <dd className={styles.valeur}>{formaterDate(detail.sla_resolution_le)}</dd>
            </div>
            <div className={styles.metaItem}>
              <dt>Créé le</dt>
              <dd className={styles.valeur}>{formaterDate(detail.cree_le)}</dd>
            </div>
          </dl>

          {detail.description !== null && detail.description !== '' && (
            <p className={styles.description}>{detail.description}</p>
          )}

          <div className={styles.workflow}>
            <span className={styles.wfTitre}>Faire évoluer</span>
            {detail.transitions_possibles.length === 0 ? (
              <span className={styles.wfFinal}>État final — aucune évolution possible.</span>
            ) : (
              <div className={styles.transitions}>
                {detail.transitions_possibles.map((vers) => {
                  const c = couleurStatut(vers);
                  return (
                    <button
                      key={vers}
                      type="button"
                      className={styles.transBtn}
                      style={{ color: c, background: `color-mix(in srgb, ${c} 14%, transparent)` }}
                      disabled={envoi}
                      onClick={() => void transitionner(vers)}
                    >
                      {vers}
                      <ArrowRight size={14} />
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {erreur !== null && <p className={styles.erreur}>{erreur}</p>}
        </div>
      )}
    </Modale>
  );
}
