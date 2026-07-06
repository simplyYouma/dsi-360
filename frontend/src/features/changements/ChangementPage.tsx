import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Send, X } from 'lucide-react';
import { Button, Skeleton, useToast } from '@/design-system/primitives';
import { ChampInline } from '@/common/ChampInline';
import { ListeTaches } from '@/common/ListeTaches';
import { PiecesJointes } from '@/common/PiecesJointes';
import { SelecteurCategorie } from '@/common/SelecteurCategorie';
import { SelecteurListe } from '@/common/SelecteurListe';
import { BadgePriorite, BadgeSla, BadgeStatut, couleurStatut } from '@/common/statuts';
import { commentairesApi, type Commentaire } from '@/common/commentairesApi';
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

  const [detail, setDetail] = useState<ChangementDetail | null>(null);
  const [taches, setTaches] = useState<Tache[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [categories, setCategories] = useState<Categorie[]>([]);
  const [commentaires, setCommentaires] = useState<Commentaire[]>([]);
  const [texte, setTexte] = useState('');
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
  const chargerCommentaires = useCallback((): void => {
    if (id !== undefined) void commentairesApi.lister(id).then(setCommentaires);
  }, [id]);

  const charger = useCallback(async (): Promise<void> => {
    if (id === undefined) return;
    try {
      setDetail(await changementsApi.detail(id));
      chargerTaches();
      chargerCommentaires();
    } catch {
      setIntrouvable(true);
    }
  }, [id, chargerTaches, chargerCommentaires]);

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

  const commenter = async (): Promise<void> => {
    if (id === undefined || texte.trim() === '') return;
    try {
      await commentairesApi.ajouter(id, texte.trim());
      setTexte('');
      chargerCommentaires();
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Envoi impossible.', 'erreur');
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
                <div className={cx(styles.metaItem, styles.metaLarge)}>
                  <dt>Contributeurs</dt>
                  <dd>
                    {detail.contributeurs.length > 0 && (
                      <ul className={styles.contribListe}>
                        {detail.contributeurs.map((c) => (
                          <li key={c.id} className={styles.contribItem}>
                            <span>
                              {c.prenom} {c.nom}
                            </span>
                            <button
                              type="button"
                              className={styles.contribRetirer}
                              disabled={envoi}
                              onClick={() => void agir(() => changementsApi.retirerContributeur(id!, c.id))}
                              aria-label={`Retirer ${c.prenom} ${c.nom}`}
                            >
                              <X size={13} />
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                    <SelecteurListe
                      options={optionsAgents.filter(
                        (a) =>
                          a.valeur !== (detail.responsable_id ?? '') &&
                          !detail.contributeurs.some((c) => c.id === a.valeur),
                      )}
                      valeur={null}
                      onChange={(val) => val !== null && void agir(() => changementsApi.ajouterContributeur(id!, val))}
                      permettreVide={false}
                      placeholder="Ajouter un contributeur…"
                    />
                  </dd>
                </div>
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
            <span className={styles.carteTitre}>Tâches (plan de déploiement)</span>
            {creation ? (
              <p className={styles.note}>
                Créez le changement pour ajouter les tâches ; elles pilotent le passage « En
                implémentation » puis « Implémenté ».
              </p>
            ) : (
              <ListeTaches
                taches={taches}
                agents={optionsAgents}
                onAjouter={ajouterTache}
                onMaj={majTache}
                onSupprimer={supprimerTache}
                renduEnfant={(t) => (
                  <PiecesJointes
                    compact
                    charger={() => changementsApi.documentsTache(id!, t.id)}
                    deposer={(f) => changementsApi.deposerDocumentTache(id!, t.id, f)}
                    telecharger={(docId) => changementsApi.telechargerDocument(id!, docId)}
                    apercu={(docId) => changementsApi.apercuDocument(id!, docId)}
                    renommer={(docId, nom) => changementsApi.renommerDocument(id!, docId, nom)}
                    supprimer={(docId) => changementsApi.supprimerDocument(id!, docId)}
                  />
                )}
              />
            )}
          </section>

          {!creation && (
            <section className={styles.carte}>
              <span className={styles.carteTitre}>Discussion interne (DSI)</span>
              {commentaires.length === 0 ? (
                <p className={fiche.commVide}>Aucun échange pour le moment.</p>
              ) : (
                <ul className={fiche.commListe}>
                  {commentaires.map((c) => (
                    <li key={c.id} className={fiche.commItem}>
                      <div className={fiche.commTete}>
                        <span className={fiche.commAuteur}>{c.auteur}</span>
                        <span className={fiche.commDate}>
                          {new Date(c.cree_le).toLocaleString('fr-FR', {
                            day: '2-digit',
                            month: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </span>
                      </div>
                      <p className={fiche.commTexte}>{c.texte}</p>
                    </li>
                  ))}
                </ul>
              )}
              <div className={fiche.commForm}>
                <textarea
                  className={fiche.commInput}
                  value={texte}
                  onChange={(e) => setTexte(e.target.value)}
                  rows={2}
                  placeholder="Ajouter un commentaire pour l'équipe…"
                />
                <Button onClick={() => void commenter()} disabled={texte.trim() === ''}>
                  <Send size={15} />
                  Commenter
                </Button>
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
                  <div className={styles.remplissage} style={{ width: `${detail.avancement}%` }} />
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
                  « En implémentation » et « Implémenté » découlent des tâches ; CAB/ECAB et clôture
                  restent manuels.
                </p>
              </section>

              <section className={styles.carte}>
                <span className={styles.carteTitre}>Documents du changement</span>
                <PiecesJointes
                  charger={() => changementsApi.documents(id!)}
                  deposer={(f) => changementsApi.deposerDocument(id!, f)}
                  telecharger={(docId) => changementsApi.telechargerDocument(id!, docId)}
                  apercu={(docId) => changementsApi.apercuDocument(id!, docId)}
                  renommer={(docId, nom) => changementsApi.renommerDocument(id!, docId, nom)}
                  supprimer={(docId) => changementsApi.supprimerDocument(id!, docId)}
                />
              </section>
            </>
          ) : (
            <section className={styles.carte}>
              <span className={styles.carteTitre}>Prochaines étapes</span>
              <p className={styles.note}>
                Après création : tâches, cycle de vie ITIL (CAB/ECAB), contributeurs et discussion.
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
