import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Download, Eye, Paperclip, Plus, Trash2, Upload } from 'lucide-react';
import { Button, Skeleton, useToast } from '@/design-system/primitives';
import { ApercuDocument } from '@/common/ApercuDocument';
import { ChampInline } from '@/common/ChampInline';
import { ListeTaches } from '@/common/ListeTaches';
import { SelecteurDate } from '@/common/SelecteurDate';
import { SelecteurListe } from '@/common/SelecteurListe';
import { BadgeStatut, couleurStatut } from '@/common/statuts';
import { cx } from '@/common/cx';
import { api, ErreurApi } from '@/lib/api';
import type { MajTache, NouvelleTache, Tache } from '@/common/tacheTypes';
import fiche from '@/common/FicheTransition.module.css';
import styles from './ProjetPage.module.css';
import { projetsApi, type DocumentItem, type ProjetDetail } from './projetsApi';

interface Agent {
  id: string;
  nom: string;
  profil: string;
}

function formaterTaille(octets: number): string {
  if (octets < 1024) return `${octets} o`;
  if (octets < 1024 * 1024) return `${Math.round(octets / 1024)} Ko`;
  return `${(octets / (1024 * 1024)).toFixed(1)} Mo`;
}

/** Liste de pièces jointes (projet ou tâche) : dépôt, aperçu au clic, renommage, suppression. */
function Documents({
  charger,
  deposer,
  telecharger,
  apercu,
  renommer,
  supprimer,
  compact,
}: {
  charger: () => Promise<DocumentItem[]>;
  deposer: (f: File) => Promise<unknown>;
  telecharger: (docId: string) => Promise<void>;
  apercu: (docId: string) => Promise<Blob>;
  renommer: (docId: string, nom: string) => Promise<unknown>;
  supprimer: (docId: string) => Promise<void>;
  compact?: boolean;
}): JSX.Element {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [envoi, setEnvoi] = useState(false);
  const [surviole, setSurviole] = useState(false);
  const [vue, setVue] = useState<{ url: string; type: string; nom: string; docId: string } | null>(
    null,
  );
  const input = useRef<HTMLInputElement>(null);
  const { notifier } = useToast();

  const recharger = useCallback((): void => {
    void charger().then(setDocs);
    // charger est recréé à chaque rendu par l'appelant ; on ne le met pas en dépendance.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => recharger(), [recharger]);

  const envoyer = async (fichiers: File[]): Promise<void> => {
    if (fichiers.length === 0) return;
    setEnvoi(true);
    try {
      for (const f of fichiers) await deposer(f);
      recharger();
      notifier('Document déposé', 'succes');
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Dépôt impossible.', 'erreur');
    } finally {
      setEnvoi(false);
    }
  };

  const retirer = async (docId: string): Promise<void> => {
    try {
      await supprimer(docId);
      recharger();
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Suppression impossible.', 'erreur');
    }
  };

  const visualiser = async (d: DocumentItem): Promise<void> => {
    try {
      const blob = await apercu(d.id);
      setVue({ url: URL.createObjectURL(blob), type: d.type_mime, nom: d.nom, docId: d.id });
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Aperçu impossible.', 'erreur');
    }
  };
  const fermerVue = (): void => {
    setVue((prec) => {
      if (prec) URL.revokeObjectURL(prec.url);
      return null;
    });
  };

  const nommer = async (docId: string, nom: string): Promise<void> => {
    if (nom.trim() === '') return;
    try {
      await renommer(docId, nom.trim());
      recharger();
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Renommage impossible.', 'erreur');
    }
  };

  return (
    <div className={styles.docs}>
      <input
        ref={input}
        type="file"
        hidden
        multiple
        onChange={(e) => {
          const f = Array.from(e.target.files ?? []);
          e.target.value = '';
          void envoyer(f);
        }}
      />
      <div
        role="button"
        tabIndex={0}
        className={cx(styles.dropzone, surviole && styles.dropzoneActif, compact && styles.dropCompact)}
        onClick={() => !envoi && input.current?.click()}
        onKeyDown={(e) => {
          if ((e.key === 'Enter' || e.key === ' ') && !envoi) {
            e.preventDefault();
            input.current?.click();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setSurviole(true);
        }}
        onDragLeave={() => setSurviole(false)}
        onDrop={(e) => {
          e.preventDefault();
          setSurviole(false);
          void envoyer(Array.from(e.dataTransfer.files ?? []));
        }}
      >
        <Upload size={compact ? 15 : 20} />
        <span>{envoi ? 'Dépôt…' : compact ? 'Ajouter une pièce jointe' : 'Glissez des fichiers ou cliquez'}</span>
      </div>
      {docs.map((d) => (
        <div key={d.id} className={styles.docLigne}>
          <button
            type="button"
            className={styles.docApercu}
            title={`Aperçu de ${d.nom}`}
            aria-label={`Aperçu de ${d.nom}`}
            onClick={() => void visualiser(d)}
          >
            <Paperclip size={13} />
          </button>
          <div className={styles.docNom}>
            <ChampInline
              valeur={d.nom}
              onValider={(nom) => void nommer(d.id, nom)}
              aria-label={`Renommer ${d.nom}`}
            />
          </div>
          <span className={styles.note}>{formaterTaille(d.taille)}</span>
          <button type="button" className={styles.docAction} aria-label="Aperçu" title="Aperçu" onClick={() => void visualiser(d)}>
            <Eye size={14} />
          </button>
          <button type="button" className={styles.docAction} aria-label="Télécharger" title="Télécharger" onClick={() => void telecharger(d.id)}>
            <Download size={14} />
          </button>
          <button type="button" className={styles.docAction} aria-label="Supprimer" title="Supprimer" onClick={() => void retirer(d.id)}>
            <Trash2 size={14} />
          </button>
        </div>
      ))}
      {vue !== null && (
        <ApercuDocument
          url={vue.url}
          type={vue.type}
          nom={vue.nom}
          onFermer={fermerVue}
          onTelecharger={() => void telecharger(vue.docId)}
        />
      )}
    </div>
  );
}

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
    void api.get<Agent[]>('/referentiels/agents').then(setAgents);
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

  const transitionner = async (vers: string): Promise<void> => {
    if (id === undefined) return;
    setEnvoi(true);
    try {
      setDetail(await projetsApi.transition(id, vers));
      notifier(vers, 'succes');
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Transition impossible.', 'erreur');
    } finally {
      setEnvoi(false);
    }
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
                <dt>Échéance</dt>
                <dd>
                  <SelecteurDate
                    valeur={v.dateFin || null}
                    onChange={(val) => (creation ? setDateFin(val ?? '') : void patch({ date_fin: val }))}
                    placeholder="jj/mm/aaaa"
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
            <span className={styles.carteTitre}>Tâches</span>
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
                  onAjouter={ajouterTache}
                  onMaj={majTache}
                  onSupprimer={supprimerTache}
                  renduEnfant={(t) => (
                    <Documents
                      compact
                      charger={() => projetsApi.documentsTache(id, t.id)}
                      deposer={(f) => projetsApi.deposerDocumentTache(id, t.id, f)}
                      telecharger={(docId) => projetsApi.telechargerDocument(id, docId)}
                      apercu={(docId) => projetsApi.apercuDocument(id, docId)}
                      renommer={(docId, nom) => projetsApi.renommerDocument(id, docId, nom)}
                      supprimer={(docId) => projetsApi.supprimerDocument(id, docId)}
                    />
                  )}
                />
              )
            )}
          </section>
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
                  <div className={styles.remplissage} style={{ width: `${detail.avancement}%` }} />
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
                <p className={styles.note}>Le passage « En cours » est automatique ; la clôture reste manuelle (COPIL).</p>
              </section>

              <section className={styles.carte}>
                <span className={styles.carteTitre}>Documents du projet</span>
                {id !== undefined && (
                  <Documents
                    charger={() => projetsApi.documents(id)}
                    deposer={(f) => projetsApi.deposerDocument(id, f)}
                    telecharger={(docId) => projetsApi.telechargerDocument(id, docId)}
                    apercu={(docId) => projetsApi.apercuDocument(id, docId)}
                    renommer={(docId, nom) => projetsApi.renommerDocument(id, docId, nom)}
                    supprimer={(docId) => projetsApi.supprimerDocument(id, docId)}
                  />
                )}
              </section>
            </>
          )}
          {creation && (
            <section className={styles.carte}>
              <span className={styles.carteTitre}>Documents</span>
              <p className={styles.note}>
                Disponibles après la création (au niveau du projet et de chaque tâche).
              </p>
              <Button onClick={() => void creer()} disabled={envoi || titre.trim().length < 3} pleineLargeur>
                <Plus size={15} /> {envoi ? 'Création…' : 'Créer le projet'}
              </Button>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
