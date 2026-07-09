import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Check, XCircle } from 'lucide-react';
import { Button, Skeleton, useToast } from '@/design-system/primitives';
import { useAuth } from '@/lib/auth';
import { ChampInline } from '@/common/ChampInline';
import { DiscussionTache } from '@/common/DiscussionTache';
import { GestionActeurs } from '@/common/GestionActeurs';
import { JournalNotes } from '@/common/JournalNotes';
import { LiensTache } from '@/common/LiensTache';
import { ListeTaches } from '@/common/ListeTaches';
import { SelecteurCategorie } from '@/common/SelecteurCategorie';
import { SelecteurListe } from '@/common/SelecteurListe';
import { BadgePriorite, BadgeSla, BadgeStatut, couleurStatut } from '@/common/statuts';
import { cx } from '@/common/cx';
import { api, ErreurApi } from '@/lib/api';
import type { MajTache, NouvelleTache, Tache } from '@/common/tacheTypes';
import fiche from '@/common/FicheTransition.module.css';
import styles from './ChangementPage.module.css';
import { changementsApi, type Categorie, type ChangementDetail } from './changementsApi';

interface Agent {
  id: string;
  nom: string;
  profil: string;
}

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
const CHAMPS_RFC = [
  [
    'analyse_impact',
    "Analyse d'impact",
    'Systèmes, services et utilisateurs touchés ; interruption prévue.',
  ],
  [
    'analyse_risque',
    'Analyse de risque',
    'Risques identifiés, probabilité, mesures de réduction.',
  ],
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
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });
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
    void api.get<Agent[]>('/referentiels/agents').then(setAgents);
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
            onValider={(val) => (creation ? setTitre(val) : void agir(() => changementsApi.modifier(id!, { titre: val })))}
            toujoursEdition={creation}
            titre
            placeholder="Objet du changement"
            classeTexte={styles.titre}
            aria-label="Objet du changement"
          />
        </div>
        {creation ? (
          <Button onClick={() => void creer()} disabled={envoi || titre.trim().length < 3}>
            {envoi ? 'Création…' : 'Créer le changement'}
          </Button>
        ) : (
          detail && <BadgeStatut statut={detail.statut} />
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
                      creation ? setCategorie(val) : void agir(() => changementsApi.changerType(id!, val), 'Type mis à jour')
                    }
                    couleurs={TYPE_COULEUR}
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
                    <dt>Échéance</dt>
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
                      creation ? setGestionnaire(val) : void agir(() => changementsApi.assigner(id!, val), 'Gestionnaire mis à jour')
                    }
                    permettreVide
                    libelleVide="Non assigné"
                    placeholder="Assigner à un agent DSI…"
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
                        onAjouter={(val) => void agir(() => changementsApi.ajouterContributeur(id!, val))}
                        onRetirer={(val) => void agir(() => changementsApi.retirerContributeur(id!, val))}
                        placeholder="Ajouter un contributeur…"
                        disabled={envoi}
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
                        onAjouter={(val) => void agir(() => changementsApi.ajouterValideur(id!, val))}
                        onRetirer={(val) => void agir(() => changementsApi.retirerValideur(id!, val))}
                        placeholder="Ajouter un valideur…"
                        disabled={envoi}
                      />
                      {moi !== null && detail.valideurs.some((v) => v.id === moi.id) && (
                        <div className={styles.decision}>
                          <span className={styles.note}>Votre décision :</span>
                          <Button variante="secondaire" onClick={() => void agir(() => changementsApi.decider(id!, 'APPROUVE'), 'Approuvé')} disabled={envoi}>
                            <Check size={15} /> Approuver
                          </Button>
                          <Button variante="secondaire" onClick={() => void agir(() => changementsApi.decider(id!, 'REJETE'), 'Rejeté')} disabled={envoi}>
                            <XCircle size={15} /> Rejeter
                          </Button>
                        </div>
                      )}
                    </dd>
                  </div>
                </>
              )}
            </dl>
            <div className={styles.champBloc}>
              <span className={styles.carteTitre}>Description / plan</span>
              <ChampInline
                valeur={v.description}
                onValider={(val) => (creation ? setDescription(val) : void agir(() => changementsApi.modifier(id!, { description: val })))}
                toujoursEdition={creation}
                multiligne
                placeholder="Analyse d'impact, plan de déploiement, retour arrière…"
                aria-label="Description"
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
                onAjouter={ajouterTache}
                onMaj={majTache}
                onSupprimer={supprimerTache}
                onReordonner={async (ids) => {
                  setDetail(await changementsApi.reordonnerTaches(id!, ids));
                  chargerTaches();
                }}
                renduSousTitre={(t) => (
                  <LiensTache
                    charger={() => changementsApi.liensTache(id!, t.id)}
                    creer={(libelle, url) => changementsApi.creerLienTache(id!, t.id, libelle, url)}
                    supprimer={(lienId) => changementsApi.supprimerLien(id!, lienId)}
                  />
                )}
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
              <span className={styles.carteTitre}>Analyse & plans (RFC)</span>
              {CHAMPS_RFC.map(([champ, libelle, indication]) => (
                <div key={champ} className={styles.champBloc}>
                  <span className={styles.note}>{libelle}</span>
                  <ChampInline
                    valeur={detail[champ] ?? ''}
                    onValider={(val) =>
                      void agir(() => changementsApi.modifier(id!, { [champ]: val }))
                    }
                    multiligne
                    indication={indication}
                    aria-label={libelle}
                  />
                </div>
              ))}
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
                    style={{ color: couleurStatut(detail.statut), borderColor: couleurStatut(detail.statut) }}
                  >
                    {detail.statut}
                  </span>
                  {detail.transitions_possibles.map((etat) => {
                    const c = couleurStatut(etat);
                    return (
                      <button
                        key={etat}
                        type="button"
                        className={fiche.chip}
                        style={{ color: c, background: `color-mix(in srgb, ${c} 14%, transparent)` }}
                        disabled={envoi}
                        onClick={() => void agir(() => changementsApi.transition(id!, etat), etat)}
                      >
                        {etat}
                        <ArrowRight size={13} />
                      </button>
                    );
                  })}
                </div>
                <p className={styles.note}>
                  Les tâches font avancer l’implémentation ; le CAB/ECAB est tranché par les
                  valideurs.
                </p>
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
                Après création : tâches, cycle de vie ITIL (CAB/ECAB), valideurs et notes.
              </p>
              <Button onClick={() => void creer()} disabled={envoi || titre.trim().length < 3} pleineLargeur>
                {envoi ? 'Création…' : 'Créer le changement'}
              </Button>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
