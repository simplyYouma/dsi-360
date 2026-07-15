import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowRight, Check, CheckCircle2, Clock, XCircle } from 'lucide-react';
import { Button, Modale, Skeleton, useToast } from '@/design-system/primitives';
import { SelecteurListe } from '@/common/SelecteurListe';
import { ChampInline } from '@/common/ChampInline';
import { SelecteurDate } from '@/common/SelecteurDate';
import { PastilleEcheance } from '@/common/PastilleEcheance';
import { CurseurNiveau } from '@/common/CurseurNiveau';
import { NiveauSupport } from '@/common/NiveauSupport';
import { chargerAgents, moduleDeLaBase, type Agent } from '@/common/agentsApi';
import { GestionActeurs, type Acteur } from '@/common/GestionActeurs';
import { AUCUNE_PERMISSION, type Permissions } from '@/common/permissions';
import { PiecesJointes } from '@/common/PiecesJointes';
import { SelecteurCategorie, type OptionCategorie } from '@/common/SelecteurCategorie';
import { ComposeurDiscussion } from '@/common/ComposeurDiscussion';
import { LigneCommentaire } from '@/common/LigneCommentaire';
import { extraireMentions, useAgents } from '@/common/useAgents';
import { commentairesApi, type Commentaire } from '@/common/commentairesApi';
import { api, ErreurApi, televerser, telecharger, recupererBlob } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { cx } from './cx';
import {
  BadgeCriticite,
  BadgePriorite,
  BadgeSla,
  BadgeStatut,
  couleurStatut,
  estTransitionCloturante,
  libelleStatut,
} from './statuts';
import { ModaleConfirmation, type DemandeConfirmation } from '@/common/ModaleConfirmation';
import styles from './FicheTransition.module.css';

interface Detail {
  reference: string;
  titre: string;
  statut: string;
  description: string | null;
  transitions_possibles: string[];
  etats: string[];
  /** L'état courant attend la décision des valideurs : rien n'avance manuellement. */
  en_attente_validation?: boolean;
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
  /** Décision de l'appelant s'il est valideur : fige ses boutons Approuver/Rejeter. */
  ma_decision?: string | null;
  /** Un valideur a déjà tranché (ou activité close) : la liste des valideurs est figée. */
  valideurs_verrouilles?: boolean;
  niveau_support?: number;
  /** Transféré à DBS (N3) : traité hors plateforme, le gestionnaire reste référent du suivi. */
  transfere_dbs?: boolean;
  /** Ce que l'appelant peut faire ici, calculé par le serveur. */
  permissions?: Permissions;
  periodicite?: string | null;
  prochaine_revue?: string | null;
  derniere_revue?: string | null;
}

interface FicheTransitionProps {
  base: string;
  id: string | null;
  onFermer: () => void;
  onChange: () => void;
  /** Appelé dès que le fil est marqué lu : permet à la liste de retirer la marque
   *  « nouveaux messages » immédiatement, sans rechargement. */
  onVu?: (activiteId: string) => void;
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
  /** Affiche le niveau de support, déduit du gestionnaire (tickets importés : incidents, demandes). */
  avecNiveauSupport?: boolean;
}

function formaterDate(iso: string | null): string {
  if (iso === null) return '—';
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

/** Pourquoi une commande est grisée. Le serveur refuserait de toute façon. */
const TITRE_LECTURE = 'Réservé au gestionnaire, aux contributeurs et à l’administrateur.';

/** Décision déjà rendue : le choix reste coloré (vert/rouge), l'autre est grisé, non cliquable. */
function BlocDecisionFigee({ decision }: { decision: string }): JSX.Element {
  const approuve = decision === 'APPROUVE';
  const couleur = approuve ? 'var(--status-ok)' : 'var(--status-danger)';
  return (
    <div className={styles.decision}>
      <span className={styles.decisionLabel}>Votre décision :</span>
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

/** Fiche d'une activité : détails présentés proprement + transitions d'état (couleurs sémantiques). */
export function FicheTransition({
  base,
  id,
  onFermer,
  onChange,
  onVu,
  assignable = false,
  labelCategorie = 'Catégorie',
  moduleCategorie,
  avecDocuments = false,
  gestionnaireFige = false,
  avecRevue = false,
  avecNiveauSupport = false,
}: FicheTransitionProps): JSX.Element {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const agentsMention = useAgents();
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState<DemandeConfirmation | null>(null);
  const [commentaires, setCommentaires] = useState<Commentaire[]>([]);
  const [texte, setTexte] = useState('');
  const [envoiC, setEnvoiC] = useState(false);
  const histoRef = useRef<HTMLOListElement>(null);
  const { notifier } = useToast();
  const { moi } = useAuth();
  const [categories, setCategories] = useState<OptionCategorie[]>([]);

  // Le serveur a calculé ce que l'utilisateur peut faire sur CETTE activité : on obéit. Aucune
  // règle d'autorisation ici — la seule source est `permissions` (cf. common/permissions.ts).
  const permissions = detail?.permissions ?? AUCUNE_PERMISSION;
  // Le Type d'un changement est un vocabulaire fixe : il ne s'enrichit pas depuis la fiche.
  const gerableCat = permissions.peut_evaluer && moduleCategorie !== 'changement';

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

  // `onVu` est souvent une lambda : on la garde dans une ref pour ne pas relancer l'effet.
  const onVuRef = useRef(onVu);
  onVuRef.current = onVu;

  // Charge le fil de discussion à l'ouverture, puis le marque comme lu.
  useEffect(() => {
    if (id === null) {
      setCommentaires([]);
      setTexte('');
      return;
    }
    void commentairesApi.lister(id).then((liste) => {
      setCommentaires(liste);
      void commentairesApi.marquerVues(id).then(() => onVuRef.current?.(id));
    });
  }, [id]);

  const commenter = async (images: File[]): Promise<void> => {
    if (id === null || (texte.trim() === '' && images.length === 0)) return;
    setEnvoiC(true);
    setErreur(null);
    try {
      const mentions = extraireMentions(texte, agentsMention);
      if (images.length > 0) {
        await commentairesApi.ajouterAvecImages(id, texte.trim(), images, undefined, mentions);
      } else {
        await commentairesApi.ajouter(id, texte.trim(), undefined, mentions);
      }
      setTexte('');
      setCommentaires(await commentairesApi.lister(id));
    } catch (err) {
      setErreur(err instanceof ErreurApi ? err.message : 'Envoi impossible.');
      throw err; // le composeur conserve les images jointes
    } finally {
      setEnvoiC(false);
    }
  };

  // Les tickets importés ne s'assignent pas, mais ils se suivent : l'administrateur y désigne des
  // contributeurs de chez nous, même quand le rapport a mis DBS au gestionnaire (ADR-0005).
  const avecContributeurs = assignable || gestionnaireFige;

  useEffect(() => {
    // Seuls les agents ayant accès à ce module sont désignables : le serveur refuserait les autres.
    if (avecContributeurs && agents.length === 0) {
      void chargerAgents(moduleDeLaBase(base)).then(setAgents);
    }
  }, [avecContributeurs, agents.length, base]);

  const assigner = async (responsableId: string | null): Promise<void> => {
    if (id === null) return;
    setEnvoi(true);
    setErreur(null);
    try {
      setDetail(
        await api.post<Detail>(`${base}/${id}/assignation`, { responsable_id: responsableId }),
      );
      onChange();
      notifier(
        responsableId === null ? 'Gestionnaire retiré' : 'Gestionnaire mis à jour',
        'succes',
      );
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

  const revueEffectuee = async (): Promise<void> => {
    if (id === null) return;
    setEnvoi(true);
    setErreur(null);
    try {
      const d = await api.post<Detail>(`${base}/${id}/revue/effectuee`, {});
      setDetail(d);
      onChange();
      notifier('Revue enregistrée — prochaine échéance reportée', 'succes');
    } catch (err) {
      setErreur(err instanceof ErreurApi ? err.message : 'Enregistrement impossible.');
    } finally {
      setEnvoi(false);
    }
  };

  // Description d'un incident/demande importé : saisie par un acteur, jamais écrasée à l'import.
  const modifierDescription = async (valeur: string): Promise<void> => {
    if (id === null) return;
    try {
      setDetail(await api.patch<Detail>(`${base}/${id}/description`, { description: valeur }));
      onChange();
    } catch (err) {
      setErreur(err instanceof ErreurApi ? err.message : 'Enregistrement impossible.');
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
      setDetail(
        await api.post<Detail>(`${base}/${id}/valideurs`, { utilisateur_id: utilisateurId }),
      );
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
      notifier(`${d.reference} · ${libelleStatut(vers)}`, 'succes');
      // Étape en attente des valideurs : l'étape suivante ne se déclenche pas toute seule.
      if (d.en_attente_validation === true) {
        notifier('En attente de la décision du valideur pour passer à l’étape suivante.', 'info');
      }
    } catch (err) {
      setErreur(err instanceof ErreurApi ? err.message : 'Transition impossible.');
    } finally {
      setEnvoi(false);
    }
  };

  // Décision d'un valideur : jamais d'un simple clic. On confirme d'abord (c'est définitif).
  const demanderDecision = (decision: 'APPROUVE' | 'REJETE'): void => {
    setConfirmation({
      titre: decision === 'APPROUVE' ? 'Approuver l’activité' : 'Rejeter l’activité',
      message:
        decision === 'APPROUVE'
          ? 'Confirmer votre approbation ? Votre décision est définitive.'
          : 'Confirmer votre rejet ? Votre décision est définitive.',
      libelleConfirmer: decision === 'APPROUVE' ? 'Approuver' : 'Rejeter',
      variante: decision === 'APPROUVE' ? 'primaire' : 'danger',
      action: () => decider(decision),
    });
  };

  // Transition : confirmation seulement pour les états qui closent ou annulent l'activité.
  const lancerTransition = (vers: string): void => {
    if (estTransitionCloturante(vers)) {
      setConfirmation({
        titre: `${libelleStatut(vers)} — confirmation`,
        message: `Passer l’activité à « ${libelleStatut(vers)} » ? Cet état la clôt : elle passera en lecture seule.`,
        libelleConfirmer: libelleStatut(vers),
        variante: 'danger',
        action: () => transitionner(vers),
      });
      return;
    }
    void transitionner(vers);
  };

  const visites = new Set((detail?.historique ?? []).map((h) => h.statut));

  return (
    <Modale
      ouverte={id !== null}
      onFermer={onFermer}
      titre={detail ? detail.reference : 'Fiche'}
      largeur={640}
      largeurPanneau={450}
      panneau={
        <div className={styles.panneauDiscussion}>
          <span className={styles.panneauTitre}>Discussion interne (DSI)</span>
          <div className={styles.panneauFil}>
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
          </div>
          <div className={styles.panneauForm}>
            <ComposeurDiscussion
              valeur={texte}
              onChange={setTexte}
              agents={agentsMention}
              placeholder="Ajouter un commentaire…  (@ pour mentionner)"
              envoi={envoiC}
              onEnvoyer={commenter}
            />
          </div>
        </div>
      }
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
            <div className={styles.teteTexte}>
              <h3 className={styles.titre}>{detail.titre}</h3>
              {(detail.cree_le !== undefined || detail.sla_resolution_le !== undefined) && (
                <div className={styles.teteDates}>
                  {detail.cree_le !== undefined && (
                    <span>
                      Créé le <strong>{formaterDate(detail.cree_le ?? null)}</strong>
                    </span>
                  )}
                  {detail.sla_resolution_le !== undefined && (
                    <span className={styles.teteEcheance}>
                      <Clock size={13} />
                      Échéance <strong>{formaterDate(detail.sla_resolution_le ?? null)}</strong>
                    </span>
                  )}
                </div>
              )}
            </div>
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
                    desactive={!permissions.peut_evaluer}
                    titreDesactive={TITRE_LECTURE}
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
                {/* Le gestionnaire vient du rapport. S'il n'est pas des nôtres, c'est DBS. */}
                <dt>{detail.transfere_dbs === true ? 'Gestionnaire (DBS)' : 'Gestionnaire'}</dt>
                <dd className={styles.valeur}>{detail.gestionnaire ?? '—'}</dd>
              </div>
            ) : assignable && permissions.peut_assigner ? (
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
                    indiceReaffectation="Réassigner"
                  />
                </dd>
              </div>
            ) : assignable ? (
              // Seul l'administrateur distribue le travail : les autres lisent le gestionnaire.
              <div className={styles.metaItem}>
                <dt>Gestionnaire</dt>
                <dd className={styles.valeur}>
                  {detail.responsable
                    ? `${detail.responsable.prenom} ${detail.responsable.nom}`
                    : 'Non assigné'}
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
            {avecNiveauSupport ? (
              <div className={cx(styles.metaItem, styles.metaLarge)}>
                <dt>Support</dt>
                <dd>
                  <NiveauSupport
                    niveau={detail.niveau_support ?? 1}
                    transfereDbs={detail.transfere_dbs ?? false}
                  />
                </dd>
              </div>
            ) : null}
            {avecContributeurs ? (
              <div className={cx(styles.metaItem, styles.metaLarge)}>
                <dt>Contributeur</dt>
                <dd>
                  <GestionActeurs
                    acteurs={detail.contributeurs ?? []}
                    agents={agents}
                    exclureIds={[detail.responsable_id ?? '']}
                    onAjouter={(v) => void ajouterContributeur(v)}
                    onRetirer={(v) => void retirerContributeur(v)}
                    placeholder="Ajouter un contributeur…"
                    disabled={envoi}
                    lectureSeule={!permissions.peut_gerer_acteurs}
                  />
                </dd>
              </div>
            ) : null}
            {assignable ? (
              <>
                <div className={cx(styles.metaItem, styles.metaLarge)}>
                  <dt>Valideur</dt>
                  <dd>
                    <GestionActeurs
                      acteurs={detail.valideurs ?? []}
                      agents={agents}
                      exclureIds={[detail.responsable_id ?? '']}
                      onAjouter={(v) => void ajouterValideur(v)}
                      onRetirer={(v) => void retirerValideur(v)}
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
                        <span className={styles.decisionLabel}>Votre décision :</span>
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
            ) : null}
            {permissions.peut_evaluer &&
              detail.impact !== undefined &&
              detail.priorite !== undefined && (
                <div className={cx(styles.metaItem, styles.metaLarge)}>
                  <dt>Évaluation</dt>
                  <dd className={styles.evaluation}>
                    <div className={styles.evalChamps}>
                      <label className={styles.evalChamp}>
                        <span className={styles.evalLabel}>Impact</span>
                        <CurseurNiveau
                          valeur={detail.impact ?? 3}
                          onChange={(v) => void reevaluer('impact', v)}
                        />
                      </label>
                      <span className={styles.evalOperateur} aria-hidden="true">
                        ×
                      </span>
                      <label className={styles.evalChamp}>
                        <span className={styles.evalLabel}>Urgence</span>
                        <CurseurNiveau
                          valeur={detail.urgence ?? 3}
                          onChange={(v) => void reevaluer('urgence', v)}
                        />
                      </label>
                    </div>
                  </dd>
                </div>
              )}
            {avecRevue && (
              <div className={cx(styles.metaItem, styles.metaLarge)}>
                <dt className={styles.revueTitre}>
                  Revue périodique
                  {detail.periodicite && detail.prochaine_revue && (
                    <PastilleEcheance date={detail.prochaine_revue} prefixe="Revue" />
                  )}
                </dt>
                <dd className={styles.revue}>
                  <SelecteurListe
                    options={['Mensuelle', 'Trimestrielle', 'Semestrielle', 'Annuelle'].map(
                      (p) => ({
                        valeur: p,
                        libelle: p,
                      }),
                    )}
                    valeur={detail.periodicite ?? null}
                    onChange={(v) => void planifierRevue('periodicite', v)}
                    permettreVide
                    libelleVide="Non définie"
                    placeholder="Périodicité…"
                    desactive={!permissions.peut_travailler}
                    titreDesactive={TITRE_LECTURE}
                  />
                  <SelecteurDate
                    valeur={detail.prochaine_revue ?? null}
                    onChange={(v) => void planifierRevue('prochaine_revue', v)}
                    placeholder="Prochaine revue"
                    desactive={!permissions.peut_travailler}
                    titreDesactive={TITRE_LECTURE}
                    remplissageEcheance
                  />
                  <Button
                    variante="secondaire"
                    className={styles.boutonRevue}
                    onClick={() => void revueEffectuee()}
                    disabled={envoi || !detail.periodicite || !permissions.peut_travailler}
                    title={
                      !permissions.peut_travailler
                        ? TITRE_LECTURE
                        : detail.periodicite
                          ? 'Enregistre la revue du jour et reporte l’échéance selon la périodicité'
                          : 'Définissez d’abord une périodicité'
                    }
                  >
                    <CheckCircle2 size={15} />
                    Revue effectuée
                  </Button>
                  {detail.derniere_revue != null && (
                    <span className={styles.revueDerniere}>
                      Dernière revue : {formaterDate(detail.derniere_revue)}
                    </span>
                  )}
                </dd>
              </div>
            )}
          </dl>

          {permissions.peut_editer_description ? (
            <div className={styles.description}>
              <ChampInline
                valeur={detail.description ?? ''}
                onValider={(val) => void modifierDescription(val)}
                multiligne
                placeholder="Ajouter une description…"
                aria-label="Description"
              />
            </div>
          ) : (
            detail.description !== null &&
            detail.description !== '' && <p className={styles.description}>{detail.description}</p>
          )}

          <div className={styles.workflow}>
            <span className={styles.wfTitre}>Cycle de vie</span>
            <div className={styles.etapes}>
              {detail.etats.map((etat) => {
                const visite = visites.has(etat);
                const estCourant = etat === detail.statut;
                const passe = visite && !estCourant;
                // Faire avancer le sujet appartient aux acteurs : les autres lisent le parcours.
                const cliquable =
                  permissions.peut_travailler && detail.transitions_possibles.includes(etat);
                const c = couleurStatut(etat);
                if (cliquable && !estCourant) {
                  return (
                    <button
                      key={etat}
                      type="button"
                      className={styles.chip}
                      style={{ color: c, background: `color-mix(in srgb, ${c} 14%, transparent)` }}
                      disabled={envoi}
                      onClick={() => lancerTransition(etat)}
                    >
                      {libelleStatut(etat)}
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
                    {libelleStatut(etat)}
                  </span>
                );
              })}
            </div>
            {detail.en_attente_validation === true &&
              (() => {
                const valideurs = detail.valideurs ?? [];
                const attendus = valideurs.filter((v) => v.decision == null).length;
                if (valideurs.length === 0) {
                  return (
                    <p className={styles.wfAttente} data-ton="alerte">
                      <Clock size={14} />
                      Aucun valideur désigné : l’étape ne peut pas être tranchée. L’administrateur
                      doit désigner un valideur.
                    </p>
                  );
                }
                return (
                  <p className={styles.wfAttente}>
                    <Clock size={14} />
                    En attente de la décision {attendus > 1 ? 'des valideurs' : 'du valideur'} —
                    l’étape suivante se déclenche dès qu’ils ont tranché.
                  </p>
                );
              })()}
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
                      <span
                        className={styles.histoStatut}
                        style={{ color: couleurStatut(h.statut) }}
                      >
                        {libelleStatut(h.statut)}
                      </span>
                      {h.acteur !== null && <span className={styles.histoActeur}>{h.acteur}</span>}
                    </li>
                  ))}
                </ol>
                {detail.historique.length > 3 && (
                  <div className={styles.histoFondu} aria-hidden="true" />
                )}
              </div>
            </div>
          )}

          {erreur !== null && <p className={styles.erreur}>{erreur}</p>}
        </div>
      )}
      <ModaleConfirmation demande={confirmation} onFermer={() => setConfirmation(null)} />
    </Modale>
  );
}
