import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowRight, Check, Clock, Send, XCircle } from 'lucide-react';
import { Button, Modale, Skeleton, useToast } from '@/design-system/primitives';
import { SelecteurListe } from '@/common/SelecteurListe';
import { SelecteurDate } from '@/common/SelecteurDate';
import { CurseurNiveau } from '@/common/CurseurNiveau';
import { GestionActeurs, type Acteur } from '@/common/GestionActeurs';
import { PiecesJointes } from '@/common/PiecesJointes';
import { SelecteurCategorie, type OptionCategorie } from '@/common/SelecteurCategorie';
import { ChampMention } from '@/common/ChampMention';
import { LigneCommentaire } from '@/common/LigneCommentaire';
import { extraireMentions, useAgents } from '@/common/useAgents';
import { commentairesApi, type Commentaire } from '@/common/commentairesApi';
import { api, ErreurApi, televerser, telecharger, recupererBlob } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { cx } from './cx';
import { BadgeCriticite, BadgePriorite, BadgeSla, BadgeStatut, couleurStatut } from './statuts';
import styles from './FicheTransition.module.css';

interface Agent {
  id: string;
  nom: string;
  profil: string;
}

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
  impact?: number;
  urgence?: number;
  categorie?: string | null;
  categorie_id?: string | null;
  statut_sla?: 'a_lheure' | 'approche' | 'depasse';
  sla_resolution_le?: string | null;
  cree_le?: string;
  responsable?: { prenom: string; nom: string } | null;
  demandeur?: string | null;
  gestionnaire?: string | null;
  responsable_id?: string | null;
  contributeurs?: Acteur[];
  valideurs?: Acteur[];
  niveau_support?: number;
  periodicite?: string | null;
  prochaine_revue?: string | null;
}

interface FicheTransitionProps {
  base: string;
  id: string | null;
  onFermer: () => void;
  onChange: () => void;
  /** Active l'assignation du gestionnaire DSI (modules ticketing : factory d'activités). */
  assignable?: boolean;
  /** Libellé du champ catégorie selon le module (ex. « Type » pour les changements). */
  labelCategorie?: string;
  /** Module (code) : si fourni, la catégorie devient éditable depuis la fiche. */
  moduleCategorie?: string;
  /** Active la gestion des pièces jointes (module avec `avec_documents`). */
  avecDocuments?: boolean;
  /** Active la revue périodique (périodicité + prochaine revue). */
  avecRevue?: boolean;
  /** Gestionnaire figé (tickets importés) : affiché (compte lié ou nom importé), non modifiable. */
  gestionnaireFige?: boolean;
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
export function FicheTransition({
  base,
  id,
  onFermer,
  onChange,
  assignable = false,
  labelCategorie = 'Catégorie',
  moduleCategorie,
  avecDocuments = false,
  gestionnaireFige = false,
  avecRevue = false,
}: FicheTransitionProps): JSX.Element {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const agentsMention = useAgents();
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [commentaires, setCommentaires] = useState<Commentaire[]>([]);
  const [texte, setTexte] = useState('');
  const [envoiC, setEnvoiC] = useState(false);
  const histoRef = useRef<HTMLOListElement>(null);
  const { notifier } = useToast();
  const { moi } = useAuth();
  const [categories, setCategories] = useState<OptionCategorie[]>([]);
  const gerableCat =
    (moi?.acces.includes('administration') ?? false) && moduleCategorie !== 'changement';

  const chargerCategories = useCallback((): void => {
    if (moduleCategorie === undefined) return;
    void api
      .get<OptionCategorie[]>(`/referentiels/categories?module=${moduleCategorie}`)
      .then(setCategories);
  }, [moduleCategorie]);

  useEffect(() => {
    if (moduleCategorie === undefined || id === null) {
      setCategories([]);
      return;
    }
    chargerCategories();
  }, [moduleCategorie, id, chargerCategories]);

  const changerCategorie = async (categorie_id: string | null): Promise<void> => {
    if (id === null) return;
    setEnvoi(true);
    setErreur(null);
    try {
      const d = await api.post<Detail>(`${base}/${id}/categorie`, { categorie_id });
      setDetail(d);
      onChange();
      notifier('Catégorie mise à jour', 'succes');
    } catch (err) {
      setErreur(err instanceof ErreurApi ? err.message : 'Modification impossible.');
    } finally {
      setEnvoi(false);
    }
  };

  const charger = useCallback(async (): Promise<void> => {
    if (id === null) return;
    setDetail(null);
    setErreur(null);
    setDetail(await api.get<Detail>(`${base}/${id}`));
  }, [base, id]);

  useEffect(() => {
    void charger();
  }, [charger]);

  // Positionne l'historique sur la dernière entrée (la plus récente, en bas).
  useEffect(() => {
    const liste = histoRef.current;
    if (liste !== null) liste.scrollTop = liste.scrollHeight;
  }, [detail]);

  // Charge le fil de discussion à l'ouverture, puis le marque comme lu.
  useEffect(() => {
    if (id === null) {
      setCommentaires([]);
      setTexte('');
      return;
    }
    void commentairesApi.lister(id).then((liste) => {
      setCommentaires(liste);
      void commentairesApi.marquerVues(id);
    });
  }, [id]);

  const commenter = async (): Promise<void> => {
    if (id === null || texte.trim() === '') return;
    setEnvoiC(true);
    try {
      await commentairesApi.ajouter(id, texte.trim(), undefined, extraireMentions(texte, agentsMention));
      setTexte('');
      setCommentaires(await commentairesApi.lister(id));
    } finally {
      setEnvoiC(false);
    }
  };

  useEffect(() => {
    if (assignable && agents.length === 0) void api.get<Agent[]>('/referentiels/agents').then(setAgents);
  }, [assignable, agents.length]);

  const assigner = async (responsableId: string | null): Promise<void> => {
    if (id === null) return;
    setEnvoi(true);
    setErreur(null);
    try {
      setDetail(await api.post<Detail>(`${base}/${id}/assignation`, { responsable_id: responsableId }));
      onChange();
      notifier(responsableId === null ? 'Gestionnaire retiré' : 'Gestionnaire mis à jour', 'succes');
    } catch (err) {
      setErreur(err instanceof ErreurApi ? err.message : 'Assignation impossible.');
    } finally {
      setEnvoi(false);
    }
  };

  const ajouterContributeur = async (utilisateurId: string | null): Promise<void> => {
    if (id === null || utilisateurId === null) return;
    setEnvoi(true);
    setErreur(null);
    try {
      setDetail(
        await api.post<Detail>(`${base}/${id}/contributeurs`, { utilisateur_id: utilisateurId }),
      );
      notifier('Contributeur ajouté', 'succes');
    } catch (err) {
      setErreur(err instanceof ErreurApi ? err.message : 'Ajout impossible.');
    } finally {
      setEnvoi(false);
    }
  };

  const retirerContributeur = async (utilisateurId: string): Promise<void> => {
    if (id === null) return;
    setEnvoi(true);
    setErreur(null);
    try {
      setDetail(await api.del<Detail>(`${base}/${id}/contributeurs/${utilisateurId}`));
      notifier('Contributeur retiré', 'succes');
    } catch (err) {
      setErreur(err instanceof ErreurApi ? err.message : 'Retrait impossible.');
    } finally {
      setEnvoi(false);
    }
  };

  const planifierRevue = async (
    champ: 'periodicite' | 'prochaine_revue',
    valeur: string | null,
  ): Promise<void> => {
    if (id === null) return;
    setEnvoi(true);
    setErreur(null);
    try {
      setDetail(await api.post<Detail>(`${base}/${id}/revue`, { [champ]: valeur }));
      notifier('Revue mise à jour', 'succes');
    } catch (err) {
      setErreur(err instanceof ErreurApi ? err.message : 'Mise à jour impossible.');
    } finally {
      setEnvoi(false);
    }
  };

  const decider = async (decision: 'APPROUVE' | 'REJETE'): Promise<void> => {
    if (id === null) return;
    setEnvoi(true);
    setErreur(null);
    try {
      setDetail(await api.post<Detail>(`${base}/${id}/decision`, { decision }));
      onChange();
      notifier(decision === 'APPROUVE' ? 'Approuvé' : 'Rejeté', 'succes');
    } catch (err) {
      setErreur(err instanceof ErreurApi ? err.message : 'Décision impossible.');
    } finally {
      setEnvoi(false);
    }
  };

  const reevaluer = async (champ: 'impact' | 'urgence', valeur: number): Promise<void> => {
    if (id === null) return;
    setEnvoi(true);
    setErreur(null);
    try {
      const d = await api.post<Detail>(`${base}/${id}/evaluation`, { [champ]: valeur });
      setDetail(d);
      onChange();
      notifier('Priorité et échéances réévaluées', 'succes');
    } catch (err) {
      setErreur(err instanceof ErreurApi ? err.message : 'Réévaluation impossible.');
    } finally {
      setEnvoi(false);
    }
  };


  const ajouterValideur = async (utilisateurId: string): Promise<void> => {
    if (id === null) return;
    setEnvoi(true);
    setErreur(null);
    try {
      setDetail(await api.post<Detail>(`${base}/${id}/valideurs`, { utilisateur_id: utilisateurId }));
      notifier('Valideur ajouté', 'succes');
    } catch (err) {
      setErreur(err instanceof ErreurApi ? err.message : 'Ajout impossible.');
    } finally {
      setEnvoi(false);
    }
  };

  const retirerValideur = async (utilisateurId: string): Promise<void> => {
    if (id === null) return;
    setEnvoi(true);
    setErreur(null);
    try {
      setDetail(await api.del<Detail>(`${base}/${id}/valideurs/${utilisateurId}`));
      notifier('Valideur retiré', 'succes');
    } catch (err) {
      setErreur(err instanceof ErreurApi ? err.message : 'Retrait impossible.');
    } finally {
      setEnvoi(false);
    }
  };

  const transitionner = async (vers: string): Promise<void> => {
    if (id === null) return;
    setEnvoi(true);
    setErreur(null);
    try {
      const d = await api.post<Detail>(`${base}/${id}/transition`, { vers });
      setDetail(d);
      onChange();
      notifier(`${d.reference} · ${vers}`, 'succes');
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
      largeur={640}
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
            {moduleCategorie !== undefined ? (
              <div className={cx(styles.metaItem, styles.metaLarge)}>
                <dt>{labelCategorie}</dt>
                <dd>
                  <SelecteurCategorie
                    categories={categories}
                    valeur={detail.categorie_id ?? null}
                    onChange={(v) => void changerCategorie(v)}
                    module={moduleCategorie}
                    gerable={gerableCat}
                    onModifie={chargerCategories}
                  />
                </dd>
              </div>
            ) : detail.categorie !== undefined ? (
              <div className={styles.metaItem}>
                <dt>{labelCategorie}</dt>
                <dd className={styles.valeur}>{detail.categorie ?? '—'}</dd>
              </div>
            ) : null}
            {detail.demandeur ? (
              <div className={styles.metaItem}>
                <dt>Demandeur</dt>
                <dd className={styles.valeur}>{detail.demandeur}</dd>
              </div>
            ) : null}
            {gestionnaireFige ? (
              <div className={styles.metaItem}>
                <dt>Gestionnaire (import)</dt>
                <dd className={styles.valeur}>{detail.gestionnaire ?? '—'}</dd>
              </div>
            ) : assignable ? (
              <div className={cx(styles.metaItem, styles.metaLarge)}>
                <dt>Gestionnaire</dt>
                <dd>
                  <SelecteurListe
                    options={agents.map((a) => ({ valeur: a.id, libelle: a.nom }))}
                    valeur={detail.responsable_id ?? null}
                    onChange={(v) => void assigner(v)}
                    permettreVide
                    libelleVide="Non assigné"
                    placeholder="Assigner à un agent DSI…"
                  />
                </dd>
              </div>
            ) : detail.responsable !== undefined ? (
              <div className={styles.metaItem}>
                <dt>Responsable</dt>
                <dd className={styles.valeur}>
                  {detail.responsable
                    ? `${detail.responsable.prenom} ${detail.responsable.nom}`
                    : '—'}
                </dd>
              </div>
            ) : null}
            {assignable ? (
              <>
                <div className={cx(styles.metaItem, styles.metaLarge)}>
                  <dt>Contributeurs</dt>
                  <dd>
                    <GestionActeurs
                      acteurs={detail.contributeurs ?? []}
                      agents={agents}
                      exclureIds={[detail.responsable_id ?? '']}
                      onAjouter={(v) => void ajouterContributeur(v)}
                      onRetirer={(v) => void retirerContributeur(v)}
                      placeholder="Ajouter un contributeur…"
                      disabled={envoi}
                    />
                  </dd>
                </div>
                <div className={cx(styles.metaItem, styles.metaLarge)}>
                  <dt>Valideurs</dt>
                  <dd>
                    <GestionActeurs
                      acteurs={detail.valideurs ?? []}
                      agents={agents}
                      exclureIds={[detail.responsable_id ?? '']}
                      onAjouter={(v) => void ajouterValideur(v)}
                      onRetirer={(v) => void retirerValideur(v)}
                      placeholder="Ajouter un valideur…"
                      disabled={envoi}
                    />
                    {moi !== null && (detail.valideurs ?? []).some((v) => v.id === moi.id) && (
                      <div className={styles.decision}>
                        <span className={styles.decisionLabel}>Votre décision :</span>
                        <Button variante="secondaire" onClick={() => void decider('APPROUVE')} disabled={envoi}>
                          <Check size={15} /> Approuver
                        </Button>
                        <Button variante="secondaire" onClick={() => void decider('REJETE')} disabled={envoi}>
                          <XCircle size={15} /> Rejeter
                        </Button>
                      </div>
                    )}
                  </dd>
                </div>
              </>
            ) : null}
            {assignable && detail.impact !== undefined && detail.priorite !== undefined && (
              <div className={cx(styles.metaItem, styles.metaLarge)}>
                <dt>Évaluation</dt>
                <dd className={styles.evaluation}>
                  <div className={styles.evalChamps}>
                    <label className={styles.evalChamp}>
                      <span className={styles.evalLabel}>Impact</span>
                      <CurseurNiveau valeur={detail.impact ?? 3} onChange={(v) => void reevaluer('impact', v)} />
                    </label>
                    <span className={styles.evalOperateur} aria-hidden="true">×</span>
                    <label className={styles.evalChamp}>
                      <span className={styles.evalLabel}>Urgence</span>
                      <CurseurNiveau valeur={detail.urgence ?? 3} onChange={(v) => void reevaluer('urgence', v)} />
                    </label>
                    <span className={styles.evalFleche} aria-hidden="true">
                      <ArrowRight size={15} />
                    </span>
                    <span className={styles.evalResultat}>
                      <span className={styles.evalLabel}>Priorité</span>
                      <BadgePriorite priorite={detail.priorite} />
                    </span>
                  </div>
                  <p className={styles.evalAide}>
                    Impact × urgence détermine la priorité (P1 à P5), qui fixe les délais SLA de prise
                    en charge et de résolution.
                  </p>
                </dd>
              </div>
            )}
            {avecRevue && (
              <div className={cx(styles.metaItem, styles.metaLarge)}>
                <dt>Revue périodique</dt>
                <dd className={styles.revue}>
                  <SelecteurListe
                    options={['Mensuelle', 'Trimestrielle', 'Semestrielle', 'Annuelle'].map((p) => ({
                      valeur: p,
                      libelle: p,
                    }))}
                    valeur={detail.periodicite ?? null}
                    onChange={(v) => void planifierRevue('periodicite', v)}
                    permettreVide
                    libelleVide="Non définie"
                    placeholder="Périodicité…"
                  />
                  <SelecteurDate
                    valeur={detail.prochaine_revue ?? null}
                    onChange={(v) => void planifierRevue('prochaine_revue', v)}
                    placeholder="Prochaine revue"
                  />
                </dd>
              </div>
            )}
            {(detail.cree_le !== undefined || detail.sla_resolution_le !== undefined) && (
              <div className={cx(styles.metaItem, styles.metaLarge)}>
                <dd className={styles.datesLigne}>
                  <span className={styles.dateBloc}>
                    <span className={styles.dateLabel}>Créé le</span>
                    <span className={styles.dateValeur}>{formaterDate(detail.cree_le ?? null)}</span>
                  </span>
                  <span className={cx(styles.dateBloc, styles.dateDroite)}>
                    <span className={styles.dateLabel}>Échéance</span>
                    <span className={styles.dateValeur}>
                      <Clock size={14} className={styles.dateIcone} />
                      {formaterDate(detail.sla_resolution_le ?? null)}
                    </span>
                  </span>
                </dd>
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

          {avecDocuments && id !== null && (
            <div className={styles.histo}>
              <PiecesJointes
                titre="Pièces jointes"
                charger={() => api.get(`${base}/${id}/documents`)}
                deposer={(f) => televerser(`${base}/${id}/documents`, f)}
                telecharger={(docId) => telecharger(`${base}/${id}/documents/${docId}`)}
                apercu={(docId) => recupererBlob(`${base}/${id}/documents/${docId}`)}
                renommer={(docId, nom) => api.patch(`${base}/${id}/documents/${docId}`, { nom })}
                supprimer={(docId) => api.del(`${base}/${id}/documents/${docId}`)}
              />
            </div>
          )}

          {detail.historique.length > 0 && (
            <div className={styles.histo}>
              <span className={styles.wfTitre}>Historique</span>
              <div className={styles.histoZone}>
                <ol className={styles.histoListe} ref={histoRef}>
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
                {detail.historique.length > 3 && <div className={styles.histoFondu} aria-hidden="true" />}
              </div>
            </div>
          )}

          <div className={styles.discussion}>
            <span className={styles.wfTitre}>Discussion interne (DSI)</span>
            {commentaires.length === 0 ? (
              <p className={styles.commVide}>Aucun échange pour le moment.</p>
            ) : (
              <ul className={styles.commListe}>
                {commentaires.map((c) => (
                  <LigneCommentaire
                    key={c.id}
                    commentaire={c}
                    moiId={moi?.id ?? null}
                    agents={agentsMention}
                    onModifier={async (cid, t) => {
                      await commentairesApi.modifier(cid, t);
                      if (id !== null) setCommentaires(await commentairesApi.lister(id));
                    }}
                    onSupprimer={async (cid) => {
                      await commentairesApi.supprimer(cid);
                      if (id !== null) setCommentaires(await commentairesApi.lister(id));
                    }}
                  />
                ))}
              </ul>
            )}
            <div className={styles.commForm}>
              <ChampMention
                valeur={texte}
                onChange={setTexte}
                agents={agentsMention}
                placeholder="Ajouter un commentaire…  (@ pour mentionner)"
                onEnvoyer={() => void commenter()}
              />
              <Button onClick={() => void commenter()} disabled={envoiC || texte.trim() === ''}>
                <Send size={15} />
                {envoiC ? 'Envoi…' : 'Commenter'}
              </Button>
            </div>
          </div>

          {erreur !== null && <p className={styles.erreur}>{erreur}</p>}
        </div>
      )}
    </Modale>
  );
}
