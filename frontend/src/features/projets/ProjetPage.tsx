import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Check, Flag, Plus } from 'lucide-react';
import { Button, Modale, Skeleton, useToast } from '@/design-system/primitives';
import { chargerAgents, type Agent } from '@/common/agentsApi';
import { BoutonSupprimer } from '@/common/BoutonSupprimer';
import { ChampInline } from '@/common/ChampInline';
import { DiscussionTache } from '@/common/DiscussionTache';
import { LiensActivite } from '@/common/LiensActivite';
import { ListeTaches } from '@/common/ListeTaches';
import { AUCUNE_PERMISSION } from '@/common/permissions';
import { useAuth } from '@/lib/auth';
import { SelecteurDate } from '@/common/SelecteurDate';
import { SelecteurListe } from '@/common/SelecteurListe';
import { BadgeStatut, couleurStatut } from '@/common/statuts';
import { cx } from '@/common/cx';
import { ErreurApi } from '@/lib/api';
import type { MajTache, NouvelleTache, Tache } from '@/common/tacheTypes';
import fiche from '@/common/FicheTransition.module.css';
import styles from './ProjetPage.module.css';
import { JournalNotes } from '@/common/JournalNotes';
import { projetsApi, type Jalon, type ProjetDetail } from './projetsApi';

function formaterDateCourte(iso: string | null): string {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: '2-digit' });
}

/** Jalons (dates clés) d'un projet : liste avec case « atteint », ajout et suppression. */
function Jalons({ projetId }: { projetId: string }): JSX.Element {
  const [jalons, setJalons] = useState<Jalon[]>([]);
  const [titre, setTitre] = useState('');
  const [echeance, setEcheance] = useState('');
  const { notifier } = useToast();

  const charger = useCallback((): void => {
    void projetsApi.jalons(projetId).then(setJalons);
  }, [projetId]);
  useEffect(() => charger(), [charger]);

  const ajouter = async (): Promise<void> => {
    if (titre.trim().length < 2) return;
    try {
      await projetsApi.creerJalon(projetId, { titre: titre.trim(), echeance: echeance || null });
      setTitre('');
      setEcheance('');
      charger();
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Ajout impossible.', 'erreur');
    }
  };
  const basculer = async (j: Jalon): Promise<void> => {
    await projetsApi.majJalon(projetId, j.id, { atteint: !j.atteint });
    charger();
  };
  const retirer = async (id: string): Promise<void> => {
    await projetsApi.supprimerJalon(projetId, id);
    charger();
  };

  return (
    <div className={styles.jalons}>
      {jalons.length === 0 && <p className={styles.note}>Aucun jalon.</p>}
      {jalons.map((j) => (
        <div key={j.id} className={styles.jalon}>
          <button
            type="button"
            className={cx(styles.jalonCase, j.atteint && styles.jalonAtteint)}
            onClick={() => void basculer(j)}
            aria-label={j.atteint ? 'Marquer non atteint' : 'Marquer atteint'}
          >
            {j.atteint ? <Check size={13} /> : <Flag size={13} />}
          </button>
          <span className={cx(styles.jalonTitre, j.atteint && styles.jalonFait)}>{j.titre}</span>
          <span className={styles.note}>{formaterDateCourte(j.echeance)}</span>
          <BoutonSupprimer
            cible={`le jalon « ${j.titre} »`}
            onSupprimer={() => retirer(j.id)}
            className={styles.docAction}
            taille={14}
          />
        </div>
      ))}
      <div className={styles.jalonAjout}>
        <input
          className={styles.jalonInput}
          value={titre}
          onChange={(e) => setTitre(e.target.value)}
          placeholder="Nouveau jalon…"
          onKeyDown={(e) => {
            if (e.key === 'Enter') void ajouter();
          }}
        />
        <SelecteurDate valeur={echeance || null} onChange={(v) => setEcheance(v ?? '')} placeholder="Échéance" />
        <Button onClick={() => void ajouter()} disabled={titre.trim().length < 2}>
          <Plus size={15} />
        </Button>
      </div>
    </div>
  );
}

/** Pastille d'état d'échéance du projet (date de fin dépassée / proche), hors clôture. */
function EtatEcheanceProjet({
  dateFin,
  statut,
}: {
  dateFin: string;
  statut: string;
}): JSX.Element | null {
  if (statut === 'Clôturé') return null;
  const jours = Math.ceil(
    (new Date(dateFin).setHours(23, 59, 59, 999) - Date.now()) / 86_400_000,
  );
  if (jours < 0) return <span className={styles.pilRetard}>Échéance dépassée</span>;
  if (jours <= 7) {
    return (
      <span className={styles.pilProche}>
        {jours === 0 ? 'Échéance aujourd’hui' : `Échéance dans ${jours} j`}
      </span>
    );
  }
  return null;
}


// Transitions qui exigent une note de justification (enregistrée au journal de bord).
const TRANSITIONS_JUSTIFIEES = new Set(['Suspendu', 'Clôturé']);

/** Page projet unifiée : même vue pour la création et le détail ; champs éditables au clic. */
export function ProjetPage(): JSX.Element {
  const { id } = useParams();
  const creation = id === undefined;
  const navigate = useNavigate();
  const { notifier } = useToast();

  const [detail, setDetail] = useState<ProjetDetail | null>(null);
  const [taches, setTaches] = useState<Tache[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [introuvable, setIntrouvable] = useState(false);
  const [envoi, setEnvoi] = useState(false);
  const { moi } = useAuth();

  // Le serveur a calculé ce que l'utilisateur peut faire ici : l'écran obéit, il ne rejoue rien.
  const permissions = detail?.permissions ?? AUCUNE_PERMISSION;

  // Brouillon utilisé en mode création (avant que le projet n'existe).
  const [titre, setTitre] = useState('');
  const [sponsor, setSponsor] = useState('');
  const [chef, setChef] = useState<string | null>(null);
  const [budget, setBudget] = useState('');
  const [dateDebut, setDateDebut] = useState('');
  const [dateFin, setDateFin] = useState('');
  const [description, setDescription] = useState('');

  const chargerTaches = useCallback((): void => {
    if (id !== undefined) void projetsApi.taches(id).then(setTaches);
  }, [id]);

  const charger = useCallback(async (): Promise<void> => {
    if (id === undefined) return;
    try {
      setDetail(await projetsApi.detail(id));
      chargerTaches();
    } catch {
      setIntrouvable(true);
    }
  }, [id, chargerTaches]);

  useEffect(() => {
    void charger();
  }, [charger]);
  useEffect(() => {
    void chargerAgents('projets').then(setAgents);
  }, []);

  const optionsAgents = agents.map((a) => ({ valeur: a.id, libelle: a.nom }));

  // Applique une modification : PATCH en mode détail, mise à jour du brouillon en mode création.
  const patch = async (corps: Parameters<typeof projetsApi.modifier>[1]): Promise<void> => {
    if (id === undefined) return;
    try {
      setDetail(await projetsApi.modifier(id, corps));
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Modification impossible.', 'erreur');
    }
  };

  const creer = async (): Promise<void> => {
    if (titre.trim().length < 3) return;
    setEnvoi(true);
    try {
      const { id: nouvel } = await projetsApi.creer({
        titre: titre.trim(),
        description: description.trim(),
        sponsor: sponsor.trim(),
        budget: budget.trim() === '' ? null : Number(budget),
        date_debut: dateDebut || null,
        date_fin: dateFin || null,
        responsable_id: chef,
      });
      navigate(`/projets/${nouvel}`);
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Création impossible.', 'erreur');
      setEnvoi(false);
    }
  };

  const ajouterTache = async (corps: NouvelleTache): Promise<void> => {
    if (id === undefined) return;
    setDetail(await projetsApi.creerTache(id, corps));
    chargerTaches();
  };
  const majTache = async (tid: string, corps: MajTache): Promise<void> => {
    if (id === undefined) return;
    setDetail(await projetsApi.majTache(id, tid, corps));
    chargerTaches();
  };
  const supprimerTache = async (tid: string): Promise<void> => {
    if (id === undefined) return;
    setDetail(await projetsApi.supprimerTache(id, tid));
    chargerTaches();
  };

  // Suspension / clôture : exigent une note de justification (modale) avant la transition.
  const [justifPour, setJustifPour] = useState<string | null>(null);
  const [justif, setJustif] = useState('');
  const [versionNotes, setVersionNotes] = useState(0);

  const executerTransition = async (vers: string, note?: string): Promise<void> => {
    if (id === undefined) return;
    setEnvoi(true);
    try {
      setDetail(await projetsApi.transition(id, vers, note));
      notifier(vers, 'succes');
      setJustifPour(null);
      if (note !== undefined) setVersionNotes((n) => n + 1);
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Transition impossible.', 'erreur');
    } finally {
      setEnvoi(false);
    }
  };

  const transitionner = async (vers: string): Promise<void> => {
    if (TRANSITIONS_JUSTIFIEES.has(vers)) {
      setJustif('');
      setJustifPour(vers);
      return;
    }
    await executerTransition(vers);
  };

  if (introuvable) {
    return (
      <div className={styles.page}>
        <button type="button" className={styles.retour} onClick={() => navigate('/projets')}>
          <ArrowLeft size={15} /> Projets
        </button>
        <p className={styles.note}>Projet introuvable ou hors de votre périmètre.</p>
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

  // Valeurs affichées : brouillon (création) ou détail chargé.
  const v = {
    titre: creation ? titre : (detail?.titre ?? ''),
    sponsor: creation ? sponsor : (detail?.sponsor ?? ''),
    chef: creation ? chef : (detail?.responsable_id ?? null),
    budget: creation ? budget : detail?.budget != null ? String(detail.budget) : '',
    dateDebut: creation ? dateDebut : (detail?.date_debut ?? ''),
    dateFin: creation ? dateFin : (detail?.date_fin ?? ''),
    description: creation ? description : (detail?.description ?? ''),
  };

  return (
    <div className={styles.page}>
      <header className={styles.entete}>
        <div style={{ flex: 1 }}>
          <button type="button" className={styles.retour} onClick={() => navigate('/projets')}>
            <ArrowLeft size={15} /> Projets
          </button>
          {!creation && <div className={styles.reference}>{detail?.reference}</div>}
          <ChampInline
            valeur={v.titre}
            onValider={(val) => (creation ? setTitre(val) : void patch({ titre: val }))}
            toujoursEdition={creation}
            titre
            placeholder="Intitulé du projet"
            classeTexte={styles.titre}
            aria-label="Intitulé du projet"
          />
        </div>
        {creation ? (
          <Button onClick={() => void creer()} disabled={envoi || titre.trim().length < 3}>
            {envoi ? 'Création…' : 'Créer le projet'}
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
                <dt>Chef de projet</dt>
                <dd>
                  <SelecteurListe
                    options={optionsAgents}
                    valeur={v.chef}
                    onChange={(val) => (creation ? setChef(val) : void patch({ responsable_id: val }))}
                    permettreVide
                    libelleVide="Non désigné"
                    placeholder="Désigner un chef de projet"
                  />
                </dd>
              </div>
              <div className={styles.metaItem}>
                <dt>Sponsor</dt>
                <dd>
                  <ChampInline
                    valeur={v.sponsor}
                    onValider={(val) => (creation ? setSponsor(val) : void patch({ sponsor: val }))}
                    toujoursEdition={creation}
                    placeholder="—"
                    aria-label="Sponsor"
                  />
                </dd>
              </div>
              <div className={styles.metaItem}>
                <dt>Budget (FCFA)</dt>
                <dd>
                  <ChampInline
                    valeur={v.budget}
                    onValider={(val) =>
                      creation ? setBudget(val) : void patch({ budget: val === '' ? null : Number(val) })
                    }
                    toujoursEdition={creation}
                    inputMode="numeric"
                    placeholder="0"
                    aria-label="Budget"
                  />
                </dd>
              </div>
              <div className={styles.metaItem}>
                <dt>Début</dt>
                <dd>
                  <SelecteurDate
                    valeur={v.dateDebut || null}
                    onChange={(val) =>
                      creation ? setDateDebut(val ?? '') : void patch({ date_debut: val })
                    }
                    placeholder="jj/mm/aaaa"
                  />
                </dd>
              </div>
              <div className={styles.metaItem}>
                <dt>
                  Échéance{' '}
                  {!creation && detail && v.dateFin && (
                    <EtatEcheanceProjet dateFin={v.dateFin} statut={detail.statut} />
                  )}
                </dt>
                <dd>
                  <SelecteurDate
                    valeur={v.dateFin || null}
                    onChange={(val) => (creation ? setDateFin(val ?? '') : void patch({ date_fin: val }))}
                    placeholder="jj/mm/aaaa"
                    remplissageEcheance={!creation && detail?.statut !== 'Clôturé'}
                    depuis={v.dateDebut || null}
                  />
                </dd>
              </div>
            </dl>
            <div className={styles.champBloc}>
              <span className={styles.carteTitre}>Description</span>
              <ChampInline
                valeur={v.description}
                onValider={(val) =>
                  creation ? setDescription(val) : void patch({ description: val })
                }
                toujoursEdition={creation}
                multiligne
                placeholder="Objectifs, périmètre…"
                aria-label="Description"
              />
            </div>
          </section>

          <section className={styles.carte}>
            <div className={styles.enteteStat}>
              <span className={styles.carteTitre}>Tâches</span>
              {taches.length > 0 && (
                <span className={styles.stat}>
                  {taches.filter((t) => t.statut === 'Terminée').length}/{taches.length} terminées
                </span>
              )}
            </div>
            {creation ? (
              <p className={styles.note}>
                Créez le projet pour y ajouter des tâches (l'avancement et le passage « En cours »
                en découlent).
              </p>
            ) : (
              id !== undefined && (
                <ListeTaches
                  taches={taches}
                  agents={optionsAgents}
                  peutTravailler={permissions.peut_travailler}
                  moiId={moi?.id ?? null}
                  onAjouter={ajouterTache}
                  onMaj={majTache}
                  onSupprimer={supprimerTache}
                  onReordonner={async (ids) => {
                    setDetail(await projetsApi.reordonnerTaches(id, ids));
                    chargerTaches();
                  }}
                  renduEnfant={(t) => (
                    <DiscussionTache
                      activiteId={id}
                      tacheId={t.id}
                      nombre={t.nb_commentaires ?? 0}
                      nonVus={t.nb_non_vus ?? 0}
                      onVu={(tid) =>
                        setTaches((liste) =>
                          liste.map((x) => (x.id === tid ? { ...x, nb_non_vus: 0 } : x)),
                        )
                      }
                    />
                  )}
                />
              )
            )}
          </section>

          {!creation && id !== undefined && (
            <section className={styles.carte}>
              <span className={styles.carteTitre}>Jalons</span>
              <Jalons projetId={id} />
            </section>
          )}
        </div>

        <div className={styles.colonne}>
          {!creation && detail && (
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
                <p className={styles.note}>Calculé automatiquement d'après les tâches terminées.</p>
              </section>

              <section className={styles.carte}>
                <span className={styles.carteTitre}>Cycle de vie</span>
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
                        onClick={() => void transitionner(etat)}
                      >
                        {etat}
                        <ArrowRight size={13} />
                      </button>
                    );
                  })}
                </div>
              </section>

              <section className={styles.carte}>
                <span className={styles.carteTitre}>Liens utiles</span>
                <p className={styles.note}>
                  Espace documentaire, wiki, dossiers réseau… Les pièces jointes se déposent sur
                  les tâches.
                </p>
                {id !== undefined && (
                  <LiensActivite
                    charger={() => projetsApi.liens(id)}
                    creer={(libelle, url) => projetsApi.creerLien(id, libelle, url)}
                    supprimer={(lienId) => projetsApi.supprimerLien(id, lienId)}
                    modifiable={permissions.peut_travailler}
                  />
                )}
              </section>

              <section className={styles.carte}>
                <span className={styles.carteTitre}>Notes (journal de bord)</span>
                {id !== undefined && (
                  <JournalNotes
                    charger={() => projetsApi.notes(id)}
                    creer={(texte) => projetsApi.creerNote(id, texte)}
                    version={versionNotes}
                  />
                )}
              </section>
            </>
          )}
          {creation && (
            <section className={styles.carte}>
              <span className={styles.carteTitre}>Liens & notes</span>
              <p className={styles.note}>
                Disponibles après la création : liens utiles, journal de bord, et pièces jointes
                sur chaque tâche.
              </p>
              <Button onClick={() => void creer()} disabled={envoi || titre.trim().length < 3} pleineLargeur>
                <Plus size={15} /> {envoi ? 'Création…' : 'Créer le projet'}
              </Button>
            </section>
          )}
        </div>
      </div>

      <Modale
        ouverte={justifPour !== null}
        onFermer={() => setJustifPour(null)}
        titre={justifPour === 'Suspendu' ? 'Suspendre le projet' : 'Clôturer le projet'}
        pied={
          <>
            <Button variante="secondaire" onClick={() => setJustifPour(null)}>
              Annuler
            </Button>
            <Button
              onClick={() => justifPour !== null && void executerTransition(justifPour, justif.trim())}
              disabled={envoi || justif.trim().length < 3}
            >
              {envoi ? 'En cours…' : 'Confirmer'}
            </Button>
          </>
        }
      >
        <p className={styles.note}>
          Une justification est requise : elle sera consignée au journal de bord du projet.
        </p>
        <textarea
          className={fiche.commInput}
          value={justif}
          onChange={(e) => setJustif(e.target.value)}
          rows={3}
          placeholder={
            justifPour === 'Suspendu'
              ? 'Motif de la suspension (budget, dépendance, décision COPIL…)'
              : 'Bilan / motif de clôture (livrables, décision COPIL…)'
          }
        />
      </Modale>
    </div>
  );
}
