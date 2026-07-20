import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Check, CheckCircle2, Circle, XCircle } from 'lucide-react';
import { Button, Skeleton, useToast } from '@/design-system/primitives';
import { useAuth } from '@/lib/auth';
import { AUCUNE_PERMISSION } from '@/common/permissions';
import { PastilleEcheance } from '@/common/PastilleEcheance';
import { chargerAgents, type Agent } from '@/common/agentsApi';
import { ChampInline } from '@/common/ChampInline';
import { DiscussionTache } from '@/common/DiscussionTache';
import { GestionActeurs } from '@/common/GestionActeurs';
import { JournalNotes } from '@/common/JournalNotes';
import { LiensActivite } from '@/common/LiensActivite';
import { ListeTaches } from '@/common/ListeTaches';
import { SelecteurCategorie } from '@/common/SelecteurCategorie';
import { SelecteurListe } from '@/common/SelecteurListe';
import {
  BadgePriorite,
  BadgeSla,
  BadgeStatut,
  couleurStatut,
  estTransitionCloturante,
  libelleStatut,
} from '@/common/statuts';
import { ModaleConfirmation, type DemandeConfirmation } from '@/common/ModaleConfirmation';
import { cx } from '@/common/cx';
import { ErreurApi } from '@/lib/api';
import type { MajTache, NouvelleTache, Tache } from '@/common/tacheTypes';
import fiche from '@/common/FicheTransition.module.css';
import styles from './ChangementPage.module.css';
import { changementsApi, type Categorie, type ChangementDetail } from './changementsApi';

const TYPE_COULEUR: Record<string, string> = {
  STANDARD: 'var(--status-ok)',
  NORMAL: 'var(--cat-1)',
  URGENT: 'var(--status-danger)',
};
const TYPE_NIVEAU: Record<string, { impact: number; urgence: number }> = {
  STANDARD: { impact: 2, urgence: 2 },
  NORMAL: { impact: 3, urgence: 3 },
  URGENT: { impact: 4, urgence: 4 },
};
const NIVEAU_DEFAUT = { impact: 3, urgence: 3 };

/** Dossier RFC (ITIL SI-12.04) : ce que le CAB attend avant d'autoriser le changement, et le
 *  bilan qui suit la mise en production. Chaque champ porte son indication de saisie. */
/** Pourquoi un champ est figé. Le serveur refuserait de toute façon (403). */
const TITRE_LECTURE = 'Réservé au gestionnaire, aux contributeurs et à l’administrateur.';

const CHAMPS_RFC = [
  [
    'analyse_impact',
    "Analyse d'impact",
    'Systèmes, services et utilisateurs touchés ; interruption prévue.',
  ],
  ['analyse_risque', 'Analyse de risque', 'Risques identifiés, probabilité, mesures de réduction.'],
  [
    'plan_deploiement',
    'Plan de déploiement',
    'Étapes de mise en production, fenêtre, contrôles après bascule.',
  ],
  [
    'plan_retour_arriere',
    'Plan de retour arrière',
    'Comment revenir à l’état antérieur, et en combien de temps.',
  ],
  [
    'bilan_post_implementation',
    'Bilan post-implémentation',
    'À remplir après la mise en production : résultat, écarts, incidents.',
  ],
] as const;

function formaterDate(iso: string | null): string {
  if (iso === null || iso === '') return '—';
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

/** Décision déjà rendue : le choix reste coloré (vert/rouge), l'autre est grisé, non cliquable. */
function BlocDecisionFigee({ decision }: { decision: string }): JSX.Element {
  const approuve = decision === 'APPROUVE';
  const couleur = approuve ? 'var(--status-ok)' : 'var(--status-danger)';
  return (
    <div className={styles.decision}>
      <span className={styles.note}>Votre décision :</span>
      <Button
        variante="secondaire"
        disabled
        style={{
          color: couleur,
          borderColor: couleur,
          background: `color-mix(in srgb, ${couleur} 12%, transparent)`,
          opacity: 1,
        }}
      >
        {approuve ? <Check size={15} /> : <XCircle size={15} />} {approuve ? 'Approuvé' : 'Rejeté'}
      </Button>
      <Button variante="secondaire" disabled>
        {approuve ? <XCircle size={15} /> : <Check size={15} />}{' '}
        {approuve ? 'Rejeter' : 'Approuver'}
      </Button>
    </div>
  );
}

/** Page changement unifiée : même vue pour la création et le détail ; champs éditables au clic. */
export function ChangementPage(): JSX.Element {
  const { id } = useParams();
  const creation = id === undefined;
  const navigate = useNavigate();
  const { notifier } = useToast();
  const { moi } = useAuth();

  const [detail, setDetail] = useState<ChangementDetail | null>(null);
  const [taches, setTaches] = useState<Tache[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [categories, setCategories] = useState<Categorie[]>([]);
  const [introuvable, setIntrouvable] = useState(false);
  const [envoi, setEnvoi] = useState(false);
  const [confirmation, setConfirmation] = useState<DemandeConfirmation | null>(null);

  // Le serveur a calculé ce que l'utilisateur peut faire ici : l'écran obéit, il ne rejoue rien.
  const permissions = detail?.permissions ?? AUCUNE_PERMISSION;

  // Brouillon (mode création)
  const [titre, setTitre] = useState('');
  const [description, setDescription] = useState('');
  const [categorie, setCategorie] = useState<string | null>(null);
  const [gestionnaire, setGestionnaire] = useState<string | null>(null);

  const chargerTaches = useCallback((): void => {
    if (id !== undefined) void changementsApi.taches(id).then(setTaches);
  }, [id]);

  const charger = useCallback(async (): Promise<void> => {
    if (id === undefined) return;
    try {
      setDetail(await changementsApi.detail(id));
      chargerTaches();
    } catch {
      setIntrouvable(true);
    }
  }, [id, chargerTaches]);

  useEffect(() => {
    void charger();
  }, [charger]);
  useEffect(() => {
    void chargerAgents('changements').then(setAgents);
    void changementsApi.categories().then(setCategories);
  }, []);

  const optionsAgents = agents.map((a) => ({ valeur: a.id, libelle: a.nom }));

  const agir = async (op: () => Promise<ChangementDetail>, ok?: string): Promise<void> => {
    if (id === undefined) return;
    setEnvoi(true);
    try {
      setDetail(await op());
      if (ok !== undefined) notifier(ok, 'succes');
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Opération impossible.', 'erreur');
    } finally {
      setEnvoi(false);
    }
  };

  // Transition portant son propre feedback : succès + rappel d'attente si l'on entre au comité.
  const transitionner = async (vers: string): Promise<void> => {
    if (id === undefined) return;
    setEnvoi(true);
    try {
      const d = await changementsApi.transition(id, vers);
      setDetail(d);
      notifier(`${d.reference} · ${libelleStatut(vers, 'changement')}`, 'succes');
      if (d.en_attente_validation === true) {
        notifier('En attente de la décision du valideur pour passer à l’étape suivante.', 'info');
      }
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Transition impossible.', 'erreur');
    } finally {
      setEnvoi(false);
    }
  };

  // Confirmation seulement pour les états qui closent ou annulent le changement.
  const lancerTransition = (vers: string): void => {
    if (estTransitionCloturante(vers, 'changement')) {
      setConfirmation({
        titre: `${libelleStatut(vers, 'changement')} — confirmation`,
        message: `Passer le changement à « ${libelleStatut(vers, 'changement')} » ? Cet état le clôt : il passera en lecture seule.`,
        libelleConfirmer: libelleStatut(vers, 'changement'),
        variante: 'danger',
        action: () => transitionner(vers),
      });
      return;
    }
    void transitionner(vers);
  };

  // Décision d'un valideur : toujours confirmée avant d'agir (c'est définitif).
  const demanderDecision = (decision: 'APPROUVE' | 'REJETE'): void => {
    setConfirmation({
      titre: decision === 'APPROUVE' ? 'Approuver le changement' : 'Rejeter le changement',
      message:
        decision === 'APPROUVE'
          ? 'Confirmer votre approbation ? Votre décision est définitive.'
          : 'Confirmer votre rejet ? Votre décision est définitive.',
      libelleConfirmer: decision === 'APPROUVE' ? 'Approuver' : 'Rejeter',
      variante: decision === 'APPROUVE' ? 'primaire' : 'danger',
      action: () =>
        agir(
          () => changementsApi.decider(id!, decision),
          decision === 'APPROUVE' ? 'Approuvé' : 'Rejeté',
        ),
    });
  };

  const codeType = categories.find((c) => c.id === categorie)?.code;
  const niveau = TYPE_NIVEAU[codeType ?? ''] ?? NIVEAU_DEFAUT;

  const creer = async (): Promise<void> => {
    if (titre.trim().length < 3) return;
    setEnvoi(true);
    try {
      const { id: nouvel } = await changementsApi.creer({
        titre: titre.trim(),
        description: description.trim(),
        impact: niveau.impact,
        urgence: niveau.urgence,
        categorie_id: categorie,
        responsable_id: gestionnaire,
      });
      navigate(`/changements/${nouvel}`);
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Création impossible.', 'erreur');
      setEnvoi(false);
    }
  };

  const ajouterTache = async (corps: NouvelleTache): Promise<void> => {
    if (id === undefined) return;
    setDetail(await changementsApi.creerTache(id, corps));
    chargerTaches();
  };
  const majTache = async (tid: string, corps: MajTache): Promise<void> => {
    if (id === undefined) return;
    setDetail(await changementsApi.majTache(id, tid, corps));
    chargerTaches();
  };
  const supprimerTache = async (tid: string): Promise<void> => {
    if (id === undefined) return;
    setDetail(await changementsApi.supprimerTache(id, tid));
    chargerTaches();
  };

  if (introuvable) {
    return (
      <div className={styles.page}>
        <button type="button" className={styles.retour} onClick={() => navigate('/changements')}>
          <ArrowLeft size={15} /> Changements
        </button>
        <p className={styles.note}>Changement introuvable ou hors de votre périmètre.</p>
      </div>
    );
  }

  if (!creation && detail === null) {
    return (
      <div className={styles.page}>
        <Skeleton hauteur="28px" largeur="40%" />
        <Skeleton hauteur="120px" />
        <Skeleton hauteur="200px" />
      </div>
    );
  }

  const v = {
    titre: creation ? titre : (detail?.titre ?? ''),
    description: creation ? description : (detail?.description ?? ''),
    type: creation ? categorie : (detail?.categorie_id ?? null),
    gestionnaire: creation ? gestionnaire : (detail?.responsable_id ?? null),
  };

  return (
    <div className={styles.page}>
      <header className={styles.entete}>
        <div style={{ flex: 1 }}>
          <button type="button" className={styles.retour} onClick={() => navigate('/changements')}>
            <ArrowLeft size={15} /> Changements
          </button>
          {!creation && <div className={styles.reference}>{detail?.reference}</div>}
          <ChampInline
            valeur={v.titre}
            onValider={(val) =>
              creation
                ? setTitre(val)
                : void agir(() => changementsApi.modifier(id!, { titre: val }))
            }
            toujoursEdition={creation}
            titre
            placeholder="Objet du changement"
            classeTexte={styles.titre}
            aria-label="Objet du changement"
            lectureSeule={!creation && !permissions.peut_travailler}
            titreLectureSeule={TITRE_LECTURE}
          />
        </div>
        {creation ? (
          <Button onClick={() => void creer()} disabled={envoi || titre.trim().length < 3}>
            {envoi ? 'Création…' : 'Créer le changement'}
          </Button>
        ) : (
          detail && <BadgeStatut statut={detail.statut} module="changement" />
        )}
      </header>

      <div className={styles.grille}>
        <div className={styles.colonne}>
          <section className={styles.carte}>
            <span className={styles.carteTitre}>Cadrage</span>
            <dl className={styles.meta}>
              <div className={cx(styles.metaItem, styles.metaLarge)}>
                <dt>Type</dt>
                <dd>
                  <SelecteurCategorie
                    categories={categories}
                    valeur={v.type}
                    onChange={(val) =>
                      creation
                        ? setCategorie(val)
                        : void agir(() => changementsApi.changerType(id!, val), 'Type mis à jour')
                    }
                    couleurs={TYPE_COULEUR}
                    desactive={!creation && !permissions.peut_evaluer}
                    titreDesactive="Le Type pilote le circuit de validation : seul l’administrateur le change."
                  />
                </dd>
              </div>
              {!creation && detail && (
                <>
                  <div className={styles.metaItem}>
                    <dt>Priorité</dt>
                    <dd>
                      <BadgePriorite priorite={detail.priorite} />
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
                  <div className={styles.metaItem}>
                    <dt className={styles.echeanceTitre}>
                      Échéance
                      {detail.sla_resolution_le && (
                        <PastilleEcheance date={detail.sla_resolution_le} />
                      )}
                    </dt>
                    <dd className={styles.valeur}>{formaterDate(detail.sla_resolution_le)}</dd>
                  </div>
                </>
              )}
              <div className={cx(styles.metaItem, styles.metaLarge)}>
                <dt>Gestionnaire</dt>
                <dd>
                  <SelecteurListe
                    options={optionsAgents}
                    valeur={v.gestionnaire}
                    onChange={(val) =>
                      creation
                        ? setGestionnaire(val)
                        : void agir(
                            () => changementsApi.assigner(id!, val),
                            'Gestionnaire mis à jour',
                          )
                    }
                    permettreVide
                    libelleVide="Non assigné"
                    placeholder="Assigner à un agent DSI…"
                    desactive={!creation && !permissions.peut_assigner}
                    titreDesactive="Seul l’administrateur assigne le gestionnaire."
                  />
                </dd>
              </div>
              {!creation && detail && (
                <>
                  <div className={cx(styles.metaItem, styles.metaLarge)}>
                    <dt>Contributeurs</dt>
                    <dd>
                      <GestionActeurs
                        acteurs={detail.contributeurs}
                        agents={agents}
                        exclureIds={[detail.responsable_id ?? '']}
                        onAjouter={(val) =>
                          void agir(() => changementsApi.ajouterContributeur(id!, val))
                        }
                        onRetirer={(val) =>
                          void agir(() => changementsApi.retirerContributeur(id!, val))
                        }
                        placeholder="Ajouter un contributeur…"
                        disabled={envoi}
                        lectureSeule={!permissions.peut_gerer_acteurs}
                      />
                    </dd>
                  </div>
                  <div className={cx(styles.metaItem, styles.metaLarge)}>
                    <dt>Valideurs</dt>
                    <dd>
                      <GestionActeurs
                        acteurs={detail.valideurs}
                        agents={agents}
                        exclureIds={[detail.responsable_id ?? '']}
                        onAjouter={(val) =>
                          void agir(() => changementsApi.ajouterValideur(id!, val))
                        }
                        onRetirer={(val) =>
                          void agir(() => changementsApi.retirerValideur(id!, val))
                        }
                        placeholder="Ajouter un valideur…"
                        disabled={envoi}
                        avecDecision
                        lectureSeule={
                          !permissions.peut_gerer_acteurs || (detail.valideurs_verrouilles ?? false)
                        }
                      />
                      {detail.ma_decision ? (
                        <BlocDecisionFigee decision={detail.ma_decision} />
                      ) : permissions.peut_decider ? (
                        <div className={styles.decision}>
                          <span className={styles.note}>Votre décision :</span>
                          <Button
                            variante="secondaire"
                            onClick={() => demanderDecision('APPROUVE')}
                            disabled={envoi}
                          >
                            <Check size={15} /> Approuver
                          </Button>
                          <Button
                            variante="secondaire"
                            onClick={() => demanderDecision('REJETE')}
                            disabled={envoi}
                          >
                            <XCircle size={15} /> Rejeter
                          </Button>
                        </div>
                      ) : null}
                    </dd>
                  </div>
                </>
              )}
            </dl>
            <div className={styles.champBloc}>
              <span className={styles.carteTitre}>Description / plan</span>
              <ChampInline
                valeur={v.description}
                onValider={(val) =>
                  creation
                    ? setDescription(val)
                    : void agir(() => changementsApi.modifier(id!, { description: val }))
                }
                toujoursEdition={creation}
                multiligne
                placeholder="Analyse d'impact, plan de déploiement, retour arrière…"
                aria-label="Description"
                lectureSeule={!creation && !permissions.peut_travailler}
                titreLectureSeule={TITRE_LECTURE}
              />
            </div>
          </section>

          <section className={styles.carte}>
            <div className={styles.enteteStat}>
              <span className={styles.carteTitre}>Tâches (plan de déploiement)</span>
              {taches.length > 0 && (
                <span className={styles.stat}>
                  {taches.filter((t) => t.statut === 'Terminée').length}/{taches.length} terminées
                </span>
              )}
            </div>
            {creation ? (
              <p className={styles.note}>Créez le changement pour ajouter des tâches.</p>
            ) : (
              <ListeTaches
                taches={taches}
                agents={optionsAgents}
                peutTravailler={permissions.peut_travailler}
                moiId={moi?.id ?? null}
                onAjouter={ajouterTache}
                onMaj={majTache}
                onSupprimer={supprimerTache}
                onReordonner={async (ids) => {
                  setDetail(await changementsApi.reordonnerTaches(id!, ids));
                  chargerTaches();
                }}
                renduEnfant={(t) => (
                  <>
                    <DiscussionTache
                      activiteId={id!}
                      tacheId={t.id}
                      nombre={t.nb_commentaires ?? 0}
                      nonVus={t.nb_non_vus ?? 0}
                      onVu={(tid) =>
                        setTaches((liste) =>
                          liste.map((x) => (x.id === tid ? { ...x, nb_non_vus: 0 } : x)),
                        )
                      }
                    />
                  </>
                )}
              />
            )}
          </section>

          {!creation && detail && (
            <section className={styles.carte}>
              {(() => {
                const remplis = CHAMPS_RFC.filter(([c]) => (detail[c] ?? '') !== '').length;
                const complet = remplis === CHAMPS_RFC.length;
                return (
                  <div className={styles.rfcEntete}>
                    <span className={styles.carteTitre}>Analyse &amp; plans (RFC)</span>
                    {/* Complétude du dossier CAB : une jauge segmentée, une pièce par cellule. */}
                    <span
                      className={styles.rfcMeter}
                      title={`${remplis}/${CHAMPS_RFC.length} pièce(s) fournie(s)`}
                    >
                      {CHAMPS_RFC.map(([c]) => (
                        <span
                          key={c}
                          className={cx(
                            styles.rfcCell,
                            (detail[c] ?? '') !== '' && styles.rfcCellPlein,
                          )}
                        />
                      ))}
                      <span className={cx(styles.rfcCompte, complet && styles.rfcCompteOk)}>
                        {remplis}/{CHAMPS_RFC.length}
                      </span>
                    </span>
                  </div>
                );
              })()}
              <div className={styles.rfcListe}>
                {CHAMPS_RFC.map(([champ, libelle, indication]) => {
                  const rempli = (detail[champ] ?? '') !== '';
                  return (
                    <div
                      key={champ}
                      className={cx(styles.rfcChamp, rempli && styles.rfcChampPlein)}
                    >
                      <span className={styles.rfcMarqueur} aria-hidden="true">
                        {rempli ? <CheckCircle2 size={16} /> : <Circle size={16} />}
                      </span>
                      <div className={styles.rfcCorps}>
                        <span className={cx(styles.rfcLibelle, rempli && styles.rfcRempli)}>
                          {libelle}
                        </span>
                        <ChampInline
                          valeur={detail[champ] ?? ''}
                          onValider={(val) =>
                            void agir(() => changementsApi.modifier(id!, { [champ]: val }))
                          }
                          multiligne
                          indication={indication}
                          lectureSeule={!permissions.peut_completer_dossier}
                          titreLectureSeule={TITRE_LECTURE}
                          placeholder="Non renseigné"
                          aria-label={libelle}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          )}
        </div>

        <div className={styles.colonne}>
          {!creation && detail ? (
            <>
              <section className={styles.carte}>
                <div className={styles.avTete}>
                  <span className={styles.carteTitre}>Avancement</span>
                  <span className={styles.avValeur}>{detail.avancement}%</span>
                </div>
                <div className={styles.barre}>
                  <div
                    className={cx(
                      styles.remplissage,
                      detail.avancement === 100 && styles.remplissageComplet,
                    )}
                    style={{ width: `${detail.avancement}%` }}
                  />
                </div>
                <p className={styles.note}>Calculé d'après les tâches terminées.</p>
              </section>

              <section className={styles.carte}>
                <span className={styles.carteTitre}>Cycle de vie (ITIL)</span>
                <div className={fiche.etapes}>
                  <span
                    className={cx(fiche.chip, fiche.chipActuel)}
                    style={{
                      color: couleurStatut(detail.statut),
                      borderColor: couleurStatut(detail.statut),
                    }}
                  >
                    {libelleStatut(detail.statut)}
                  </span>
                  {/* Faire avancer le sujet appartient aux acteurs : les autres lisent le parcours. */}
                  {(permissions.peut_travailler ? detail.transitions_possibles : []).map((etat) => {
                    const c = couleurStatut(etat, 'changement');
                    return (
                      <button
                        key={etat}
                        type="button"
                        className={fiche.chip}
                        style={{
                          color: c,
                          background: `color-mix(in srgb, ${c} 14%, transparent)`,
                        }}
                        disabled={envoi}
                        onClick={() => lancerTransition(etat)}
                      >
                        {libelleStatut(etat, 'changement')}
                        <ArrowRight size={13} />
                      </button>
                    );
                  })}
                </div>
                <p className={styles.note}>
                  Les tâches font avancer l’implémentation ; le passage en comité (normal ou
                  express) est tranché par les valideurs.
                </p>
              </section>

              <section className={styles.carte}>
                <span className={styles.carteTitre}>Liens utiles</span>
                <LiensActivite
                  charger={() => changementsApi.liens(id!)}
                  creer={(libelle, url) => changementsApi.creerLien(id!, libelle, url)}
                  supprimer={(lienId) => changementsApi.supprimerLien(id!, lienId)}
                  modifiable={permissions.peut_completer_dossier}
                />
              </section>

              <section className={styles.carte}>
                <span className={styles.carteTitre}>Notes (journal de bord)</span>
                <JournalNotes
                  charger={() => changementsApi.notes(id!)}
                  creer={(texte) => changementsApi.creerNote(id!, texte)}
                />
              </section>
            </>
          ) : (
            <section className={styles.carte}>
              <span className={styles.carteTitre}>Prochaines étapes</span>
              <p className={styles.note}>
                Après création : tâches, cycle de vie ITIL, valideurs et notes.
              </p>
              <Button
                onClick={() => void creer()}
                disabled={envoi || titre.trim().length < 3}
                pleineLargeur
              >
                {envoi ? 'Création…' : 'Créer le changement'}
              </Button>
            </section>
          )}
        </div>
      </div>
      <ModaleConfirmation demande={confirmation} onFermer={() => setConfirmation(null)} />
    </div>
  );
}
