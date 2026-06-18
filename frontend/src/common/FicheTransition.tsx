import { useCallback, useEffect, useState } from 'react';
import { ArrowRight } from 'lucide-react';
import { Button, Modale, Skeleton } from '@/design-system/primitives';
import { api, ErreurApi } from '@/lib/api';
import { cx } from './cx';
import { BadgeCriticite, BadgePriorite, BadgeSla, BadgeStatut, couleurStatut } from './statuts';
import styles from './FicheTransition.module.css';

interface Detail {
  reference: string;
  titre: string;
  statut: string;
  description: string | null;
  transitions_possibles: string[];
  etats: string[];
  historique: { statut: string; horodatage: string; acteur: string | null }[];
  // Champs optionnels selon le module (activité, risque…).
  priorite?: number;
  criticite?: number;
  categorie?: string | null;
  statut_sla?: 'a_lheure' | 'approche' | 'depasse';
  sla_resolution_le?: string | null;
  cree_le?: string;
  responsable?: { prenom: string; nom: string } | null;
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

  const visites = new Set((detail?.historique ?? []).map((h) => h.statut));

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
            {detail.priorite !== undefined ? (
              <BadgePriorite priorite={detail.priorite} />
            ) : detail.criticite !== undefined ? (
              <BadgeCriticite niveau={detail.criticite} />
            ) : null}
          </div>

          <dl className={styles.meta}>
            <div className={styles.metaItem}>
              <dt>Statut</dt>
              <dd>
                <BadgeStatut statut={detail.statut} />
              </dd>
            </div>
            {detail.statut_sla !== undefined && (
              <div className={styles.metaItem}>
                <dt>Échéance SLA</dt>
                <dd>
                  <BadgeSla etat={detail.statut_sla} />
                </dd>
              </div>
            )}
            {detail.categorie !== undefined && (
              <div className={styles.metaItem}>
                <dt>Catégorie</dt>
                <dd className={styles.valeur}>{detail.categorie ?? '—'}</dd>
              </div>
            )}
            {detail.responsable !== undefined && (
              <div className={styles.metaItem}>
                <dt>Responsable</dt>
                <dd className={styles.valeur}>
                  {detail.responsable
                    ? `${detail.responsable.prenom} ${detail.responsable.nom}`
                    : '—'}
                </dd>
              </div>
            )}
            {detail.sla_resolution_le !== undefined && (
              <div className={styles.metaItem}>
                <dt>Échéance</dt>
                <dd className={styles.valeur}>{formaterDate(detail.sla_resolution_le)}</dd>
              </div>
            )}
            {detail.cree_le !== undefined && (
              <div className={styles.metaItem}>
                <dt>Créé le</dt>
                <dd className={styles.valeur}>{formaterDate(detail.cree_le)}</dd>
              </div>
            )}
          </dl>

          {detail.description !== null && detail.description !== '' && (
            <p className={styles.description}>{detail.description}</p>
          )}

          <div className={styles.workflow}>
            <span className={styles.wfTitre}>Cycle de vie</span>
            <div className={styles.etapes}>
              {detail.etats.map((etat) => {
                const visite = visites.has(etat);
                const estCourant = etat === detail.statut;
                const passe = visite && !estCourant;
                const cliquable = detail.transitions_possibles.includes(etat);
                const c = couleurStatut(etat);
                if (cliquable && !estCourant) {
                  return (
                    <button
                      key={etat}
                      type="button"
                      className={styles.chip}
                      style={{ color: c, background: `color-mix(in srgb, ${c} 14%, transparent)` }}
                      disabled={envoi}
                      onClick={() => void transitionner(etat)}
                    >
                      {etat}
                      <ArrowRight size={13} />
                    </button>
                  );
                }
                return (
                  <span
                    key={etat}
                    className={cx(
                      styles.chip,
                      passe && styles.chipPasse,
                      estCourant && styles.chipActuel,
                      !passe && !estCourant && styles.chipFutur,
                    )}
                    style={estCourant ? { color: c, borderColor: c } : undefined}
                  >
                    {etat}
                  </span>
                );
              })}
            </div>
          </div>

          {detail.historique.length > 0 && (
            <div className={styles.histo}>
              <span className={styles.wfTitre}>Historique</span>
              <ol className={styles.histoListe}>
                {detail.historique.map((h, i) => (
                  <li key={i} className={styles.histoItem}>
                    <span className={styles.histoDate}>{formaterDate(h.horodatage)}</span>
                    <span className={styles.histoStatut} style={{ color: couleurStatut(h.statut) }}>
                      {h.statut}
                    </span>
                    {h.acteur !== null && <span className={styles.histoActeur}>{h.acteur}</span>}
                  </li>
                ))}
              </ol>
            </div>
          )}

          {erreur !== null && <p className={styles.erreur}>{erreur}</p>}
        </div>
      )}
    </Modale>
  );
}
