import { useCallback, useEffect, useState } from 'react';
import { ArrowRight, Minus, Plus } from 'lucide-react';
import { Button, Modale, Skeleton } from '@/design-system/primitives';
import { BadgeStatut, couleurStatut } from '@/common/statuts';
import { cx } from '@/common/cx';
import { ErreurApi } from '@/lib/api';
import fiche from '@/common/FicheTransition.module.css';
import styles from './ProjetFiche.module.css';
import { projetsApi, type ProjetDetail } from './projetsApi';

interface Props {
  id: string | null;
  onFermer: () => void;
  onChange: () => void;
}

function formaterDate(iso: string | null): string {
  if (iso === null || iso === '') return '—';
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

function formaterBudget(v: number | null): string {
  if (v === null) return '—';
  return `${new Intl.NumberFormat('fr-FR').format(v)} FCFA`;
}

/** Fiche projet : tous les champs du projet + cycle de vie + ajustement de l'avancement. */
export function ProjetFiche({ id, onFermer, onChange }: Props): JSX.Element {
  const [detail, setDetail] = useState<ProjetDetail | null>(null);
  const [avancementLocal, setAvancementLocal] = useState(0);
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(async (): Promise<void> => {
    if (id === null) return;
    setDetail(null);
    setErreur(null);
    const d = await projetsApi.detail(id);
    setDetail(d);
    setAvancementLocal(d.avancement);
  }, [id]);

  useEffect(() => {
    void charger();
  }, [charger]);

  const transitionner = async (vers: string): Promise<void> => {
    if (id === null) return;
    setEnvoi(true);
    setErreur(null);
    try {
      const d = await projetsApi.transition(id, vers);
      setDetail(d);
      setAvancementLocal(d.avancement);
      onChange();
    } catch (err) {
      setErreur(err instanceof ErreurApi ? err.message : 'Transition impossible.');
    } finally {
      setEnvoi(false);
    }
  };

  const enregistrerAvancement = async (): Promise<void> => {
    if (id === null) return;
    setEnvoi(true);
    setErreur(null);
    try {
      const d = await projetsApi.avancement(id, avancementLocal);
      setDetail(d);
      setAvancementLocal(d.avancement);
      onChange();
    } catch (err) {
      setErreur(err instanceof ErreurApi ? err.message : 'Mise à jour impossible.');
    } finally {
      setEnvoi(false);
    }
  };

  const ajuster = (delta: number): void => {
    setAvancementLocal((v) => Math.max(0, Math.min(100, v + delta)));
  };

  const visites = new Set<string>(); // les projets n'exposent pas d'historique : on grise le futur
  const modifie = detail !== null && avancementLocal !== detail.avancement;

  return (
    <Modale
      ouverte={id !== null}
      onFermer={onFermer}
      titre={detail ? detail.reference : 'Projet'}
      pied={
        <Button variante="secondaire" onClick={onFermer}>
          Fermer
        </Button>
      }
    >
      {detail === null ? (
        <div className={fiche.fiche}>
          <Skeleton hauteur="22px" largeur="60%" />
          <Skeleton hauteur="64px" />
          <Skeleton hauteur="40px" />
        </div>
      ) : (
        <div className={fiche.fiche}>
          <div className={fiche.tete}>
            <h3 className={fiche.titre}>{detail.titre}</h3>
            <BadgeStatut statut={detail.statut} />
          </div>

          <dl className={fiche.meta}>
            <div className={fiche.metaItem}>
              <dt>Chef de projet</dt>
              <dd className={fiche.valeur}>
                {detail.chef ? `${detail.chef.prenom} ${detail.chef.nom}` : '—'}
              </dd>
            </div>
            <div className={fiche.metaItem}>
              <dt>Sponsor</dt>
              <dd className={fiche.valeur}>{detail.sponsor ?? '—'}</dd>
            </div>
            <div className={fiche.metaItem}>
              <dt>Budget</dt>
              <dd className={fiche.valeur}>{formaterBudget(detail.budget)}</dd>
            </div>
            <div className={fiche.metaItem}>
              <dt>Direction</dt>
              <dd className={fiche.valeur}>{detail.direction ?? '—'}</dd>
            </div>
            <div className={fiche.metaItem}>
              <dt>Début</dt>
              <dd className={fiche.valeur}>{formaterDate(detail.date_debut)}</dd>
            </div>
            <div className={fiche.metaItem}>
              <dt>Échéance</dt>
              <dd className={fiche.valeur}>{formaterDate(detail.date_fin)}</dd>
            </div>
          </dl>

          {detail.description !== null && detail.description !== '' && (
            <p className={fiche.description}>{detail.description}</p>
          )}

          <div className={styles.avancement}>
            <div className={styles.avTete}>
              <span className={fiche.wfTitre}>Avancement</span>
              <span className={styles.avValeur}>{avancementLocal}%</span>
            </div>
            <div className={styles.barre}>
              <div className={styles.remplissage} style={{ width: `${avancementLocal}%` }} />
            </div>
            <div className={styles.avActions}>
              <button className={styles.pas} onClick={() => ajuster(-10)} disabled={envoi} aria-label="-10%">
                <Minus size={15} />
              </button>
              <button className={styles.pas} onClick={() => ajuster(10)} disabled={envoi} aria-label="+10%">
                <Plus size={15} />
              </button>
              <Button onClick={() => void enregistrerAvancement()} disabled={envoi || !modifie}>
                Enregistrer
              </Button>
            </div>
          </div>

          <div className={fiche.workflow}>
            <span className={fiche.wfTitre}>Cycle de vie</span>
            <div className={fiche.etapes}>
              {/* Projets : pas de liste d'états exhaustive renvoyée ; on affiche le statut courant
                  et les transitions disponibles, mêmes codes couleur que les autres modules. */}
              <span
                className={cx(fiche.chip, fiche.chipActuel)}
                style={{ color: couleurStatut(detail.statut), borderColor: couleurStatut(detail.statut) }}
              >
                {detail.statut}
              </span>
              {detail.transitions_possibles
                .filter((e) => !visites.has(e))
                .map((etat) => {
                  const c = couleurStatut(etat);
                  return (
                    <button
                      key={etat}
                      type="button"
                      className={fiche.chip}
                      style={{ color: c, background: `color-mix(in srgb, ${c} 14%, transparent)` }}
                      disabled={envoi}
                      onClick={() => void transitionner(etat)}
                    >
                      {etat}
                      <ArrowRight size={13} />
                    </button>
                  );
                })}
            </div>
          </div>

          {erreur !== null && <p className={fiche.erreur}>{erreur}</p>}
        </div>
      )}
    </Modale>
  );
}
