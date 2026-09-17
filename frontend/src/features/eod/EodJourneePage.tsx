import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Check,
  ChevronDown,
  FileDown,
  FileSpreadsheet,
  FileText,
  MessageSquarePlus,
  Play,
  Plus,
  RotateCcw,
  SlashSquare,
  Table2,
  TriangleAlert,
  X,
} from 'lucide-react';
import { Button, Modale, StatusBadge, useToast } from '@/design-system/primitives';
import { BarreAvancement } from '@/common/BarreAvancement';
import { ChampInline } from '@/common/ChampInline';
import { ModaleConfirmation } from '@/common/ModaleConfirmation';
import { SelecteurListe } from '@/common/SelecteurListe';
import { BadgeStatut } from '@/common/statuts';
import { ErreurApi, telecharger } from '@/lib/api';
import {
  eodApi,
  estReglee,
  grouperParSection,
  heure,
  heureCourante,
  heureObservation,
  jour,
  type DetailEod,
  type EtapeEod,
  type NatureObservation,
  type NouvelleObservation,
  type StatutEtape,
} from './eodApi';
import { exporterRapportEodPdf } from './rapportPdf';
import styles from './EodJourneePage.module.css';

/** Couleur d'un verdict d'étape. Le vert est réservé à ce qui a abouti ; le gris à ce qui ne
 *  s'appliquait pas ce soir-là — les confondre reviendrait à faire passer une étape sautée pour
 *  une étape faite. */
const COULEUR_STATUT: Record<StatutEtape, string> = {
  'À faire': 'var(--text-muted)',
  'En cours': 'var(--cat-1)',
  Complété: 'var(--status-ok)',
  Anomalie: 'var(--status-danger)',
  'Non applicable': 'var(--text-muted)',
};

/** Verdicts qu'on peut poser à la main, hors pointage. */
const VERDICTS: { statut: StatutEtape; libelle: string; icone: typeof Check }[] = [
  { statut: 'Anomalie', libelle: 'Anomalie', icone: TriangleAlert },
  { statut: 'Non applicable', libelle: 'Non applicable', icone: SlashSquare },
  { statut: 'À faire', libelle: 'Remettre à faire', icone: RotateCcw },
];

/** Au-delà, le journal d'une étape se replie : une étape qui a vu six agences bloquer pousserait
 *  les suivantes hors de l'écran, et c'est le déroulé qu'on vient lire en premier. Les plus
 *  récentes restent visibles — c'est là qu'on en est. */
const JOURNAL_VISIBLE = 3;

/** Ce que la modale d'observation est en train de consigner : sur quelle étape, et le cas échéant
 *  le verdict qui l'a déclenchée (posé dans le même appel que l'observation). */
interface Consigne {
  etape: EtapeEod;
  verdict: StatutEtape | null;
}

/** Le journal d'une étape : ce qui s'est passé, dans l'ordre, signé et horodaté.
 *
 * Il a remplacé le champ d'observations unique, qui s'écrasait à chaque saisie. Sur « PART 3 »,
 * une agence bloque à 01H12, on relance ; une autre bloque à 01H40, on relance encore. L'ancienne
 * forme ne gardait que la dernière phrase tapée : au matin, il ne restait rien à relire.
 *
 * Les lignes ne se corrigent pas et ne s'effacent pas — l'API n'offre pas le geste. Une erreur se
 * rattrape par l'observation suivante, qui la date et la signe (principe n° 4). */
function Journal({
  etape,
  deplie,
  onBasculer,
}: {
  etape: EtapeEod;
  deplie: boolean;
  onBasculer: () => void;
}): JSX.Element | null {
  const total = etape.observations.length;
  if (total === 0) return null;
  const caches = deplie ? 0 : Math.max(0, total - JOURNAL_VISIBLE);
  const visibles = etape.observations.slice(caches);

  return (
    <div className={styles.journal}>
      {caches > 0 && (
        <button className={styles.journalPlus} onClick={onBasculer}>
          <ChevronDown size={12} />
          {caches} observation{caches > 1 ? 's' : ''} plus ancienne{caches > 1 ? 's' : ''}
        </button>
      )}
      <ul className={styles.journalListe}>
        {visibles.map((o) => (
          <li
            key={o.id}
            className={o.nature === 'incident' ? styles.obsIncident : styles.obs}
            /* L'auteur en infobulle et non en ligne : sur une colonne étroite, il repousserait
               le texte, alors qu'on ne le cherche qu'en cas de doute. */
            title={o.auteur ?? undefined}
          >
            <span className={styles.obsTete}>
              <span className={styles.obsHeure}>{heureObservation(o)}</span>
              {o.nature === 'incident' && o.agence !== null && (
                <span className={styles.obsAgence}>{o.agence}</span>
              )}
            </span>
            <span className={styles.obsTexte}>{o.texte}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function EodJourneePage(): JSX.Element {
  const { id = '' } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { notifier } = useToast();
  const [soiree, setSoiree] = useState<DetailEod | null>(null);
  const [chargement, setChargement] = useState(true);
  const [occupe, setOccupe] = useState<string | null>(null);
  const [ajout, setAjout] = useState(false);
  const [libelleNouveau, setLibelleNouveau] = useState('');
  const [sectionNouvelle, setSectionNouvelle] = useState('Tâches additionnelles');
  const [aSupprimer, setASupprimer] = useState<EtapeEod | null>(null);
  const [transitionVisee, setTransitionVisee] = useState<string | null>(null);
  const [noteTransition, setNoteTransition] = useState('');
  const [exportOuvert, setExportOuvert] = useState(false);
  const [exportEnCours, setExportEnCours] = useState(false);

  // --- Consigner une observation ---------------------------------------------------------------
  const [consigne, setConsigne] = useState<Consigne | null>(null);
  const [natureObs, setNatureObs] = useState<NatureObservation>('note');
  const [agence, setAgence] = useState<string | null>(null);
  const [relance, setRelance] = useState('');
  const [texteObs, setTexteObs] = useState('');
  const [agences, setAgences] = useState<string[]>([]);
  // Étapes dont on a déplié le journal entier.
  const [deplies, setDeplies] = useState<Set<string>>(new Set());

  const charger = useCallback(async (): Promise<void> => {
    setChargement(true);
    try {
      setSoiree(await eodApi.detail(id));
    } finally {
      setChargement(false);
    }
  }, [id]);

  useEffect(() => {
    void charger();
  }, [charger]);

  // Le réseau d'agences n'est chargé qu'à la première ouverture de la modale : c'est un référentiel
  // stable, et l'écran de pointage n'en a pas besoin pour s'afficher.
  useEffect(() => {
    if (consigne === null || agences.length > 0) return;
    void eodApi.agences().then(setAgences);
  }, [consigne, agences.length]);

  // L'agence choisie librement doit figurer parmi les options, sinon le champ afficherait de
  // nouveau son indication après l'avoir enregistrée.
  const optionsAgences = useMemo(
    () =>
      [...new Set(agence === null ? agences : [...agences, agence])].map((a) => ({
        valeur: a,
        libelle: a,
      })),
    [agences, agence],
  );

  /** Toute écriture renvoie la soirée entière : avancement, anomalies et clôture conseillée
   *  changent à chaque geste, et les recalculer à l'écran les ferait diverger du serveur. */
  const agir = async (cle: string, action: () => Promise<DetailEod>): Promise<void> => {
    setOccupe(cle);
    try {
      setSoiree(await action());
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Action impossible.', 'erreur');
    } finally {
      setOccupe(null);
    }
  };

  if (chargement && soiree === null) {
    return <div className={styles.page}>Chargement…</div>;
  }
  if (soiree === null) {
    return <div className={styles.page}>Soirée introuvable.</div>;
  }

  const peutEcrire = soiree.permissions.peut_travailler;
  const pointee = soiree.nb_etapes - soiree.reste;

  /** Le PDF se compose dans le navigateur, à partir de la soirée déjà chargée : aucun aller-retour
   *  serveur, et le document sort même si le réseau vient de lâcher — la nuit, ça compte. */
  const exporterPdf = async (): Promise<void> => {
    setExportEnCours(true);
    try {
      await exporterRapportEodPdf(soiree);
      setExportOuvert(false);
    } catch {
      notifier("Le rapport n'a pas pu être composé.", 'erreur');
    } finally {
      setExportEnCours(false);
    }
  };

  const telechargerTableur = (format: 'xlsx' | 'csv'): void => {
    void telecharger(`/eod/${id}/rapport?format=${format}`);
    setExportOuvert(false);
  };

  /** Ouvre la modale d'observation. Un verdict la pré-règle en « incident » : une anomalie pendant
   *  les PART vient presque toujours d'une agence qui bloque — et c'est d'elle que le rapport
   *  parlera. Un clic suffit pour repasser en simple observation. */
  const consigner = (etape: EtapeEod, verdict: StatutEtape | null): void => {
    setConsigne({ etape, verdict });
    setNatureObs(verdict === 'Anomalie' ? 'incident' : 'note');
    setAgence(null);
    setRelance(heureCourante());
    setTexteObs('');
  };

  const fermerConsigne = (): void => setConsigne(null);

  /** Pose le verdict et l'observation en un seul appel quand les deux vont ensemble. */
  const envoyerObservation = async (): Promise<void> => {
    if (consigne === null) return;
    const { etape, verdict } = consigne;
    const observation: NouvelleObservation = {
      nature: natureObs,
      texte: texteObs.trim(),
      agence: natureObs === 'incident' ? agence : null,
      relance: natureObs === 'incident' ? relance.trim() : null,
    };
    await agir(`observation:${etape.id}`, () =>
      verdict === null
        ? eodApi.observer(id, etape.id, observation)
        : eodApi.majEtape(id, etape.id, { statut: verdict, observation }),
    );
    fermerConsigne();
  };

  /** Pose un verdict. Ceux qui, sans un mot, seraient refusés par le serveur passent par la modale
   *  — mais seulement tant que l'étape n'a rien au journal : une explication déjà consignée n'a
   *  pas à être retapée à chaque correction du verdict. */
  const poserVerdict = (etape: EtapeEod, statut: StatutEtape): void => {
    const aExpliquer = statut === 'Anomalie' || statut === 'Non applicable';
    if (aExpliquer && etape.observations.length === 0) {
      consigner(etape, statut);
      return;
    }
    void agir(`statut:${etape.id}`, () => eodApi.majEtape(id, etape.id, { statut }));
  };

  const basculerJournal = (etapeId: string): void =>
    setDeplies((anciens) => {
      const suivants = new Set(anciens);
      if (!suivants.delete(etapeId)) suivants.add(etapeId);
      return suivants;
    });

  const transitionner = async (vers: string): Promise<void> => {
    // Clore une nuit inachevée reste possible — une soirée peut être arrêtée pour de bonnes
    // raisons — mais le serveur exige alors une note. On la demande avant d'envoyer, plutôt que
    // de laisser l'opérateur se heurter à un refus.
    const clot = ['Clôturé', 'Clôturé avec réserves', 'Annulé'].includes(vers);
    if (clot && soiree.cloture_conseillee === null && noteTransition.trim() === '') {
      setTransitionVisee(vers);
      return;
    }
    await agir(`transition:${vers}`, () =>
      eodApi.transition(id, vers, noteTransition || undefined),
    );
    setTransitionVisee(null);
    setNoteTransition('');
  };

  return (
    <div className={styles.page}>
      <header className={styles.entete}>
        <div className={styles.identite}>
          <button className={styles.retour} onClick={() => navigate('/eod')} aria-label="Retour">
            <ArrowLeft size={18} />
          </button>
          <div>
            <div className={styles.reference}>{soiree.reference}</div>
            <h1 className={styles.titre}>
              EOD — {jour(soiree.journee)}
              <BadgeStatut statut={soiree.statut} module="eod" />
              {soiree.categorie !== null && (
                <StatusBadge couleur="var(--cat-6)">{soiree.categorie}</StatusBadge>
              )}
            </h1>
          </div>
        </div>
        <div className={styles.actions}>
          {/* Une fois la soirée close, il ne reste qu'un geste : rendre compte. Le bouton passe
              alors au premier plan — tant qu'il y a des étapes à pointer, il ne doit pas
              concurrencer la clôture. */}
          <Button
            variante={soiree.transitions_possibles.length === 0 ? 'primaire' : 'secondaire'}
            onClick={() => setExportOuvert(true)}
          >
            <FileDown size={16} />
            Rapport du soir
          </Button>
          {peutEcrire &&
            soiree.transitions_possibles.map((vers) => (
              <Button
                key={vers}
                variante={vers === soiree.cloture_conseillee ? 'primaire' : 'secondaire'}
                disabled={occupe !== null}
                onClick={() => void transitionner(vers)}
              >
                {vers}
              </Button>
            ))}
        </div>
      </header>

      <section className={styles.mesures}>
        <div className={styles.mesure}>
          <span className={styles.mesureTitre}>Déroulé</span>
          <BarreAvancement valeur={soiree.avancement} />
          <span className={styles.mesureDetail}>
            {pointee}/{soiree.nb_etapes} étapes réglées
          </span>
        </div>
        <div className={styles.mesure}>
          <span className={styles.mesureTitre}>Anomalies</span>
          <strong className={soiree.anomalies > 0 ? styles.alerte : styles.calme}>
            {soiree.anomalies}
          </strong>
          <span className={styles.mesureDetail}>
            {soiree.anomalies > 0 ? 'à expliquer au rapport' : 'aucune anomalie relevée'}
          </span>
        </div>
        {/* Distincte des anomalies, et pas déductible d'elles : une agence peut être relancée sans
            que l'étape finisse en anomalie, et une anomalie de batch ne touche parfois aucune
            agence. C'est le chiffre qui dit ce que nos nuits coûtent au réseau. */}
        <div className={styles.mesure}>
          <span className={styles.mesureTitre}>Relances d’agence</span>
          <strong className={soiree.incidents > 0 ? styles.alerte : styles.calme}>
            {soiree.incidents}
          </strong>
          <span className={styles.mesureDetail}>
            {soiree.incidents > 0
              ? 'agences relancées cette nuit'
              : 'aucune agence n’a bloqué'}
          </span>
        </div>
        <div className={styles.mesure}>
          <span className={styles.mesureTitre}>Plage</span>
          <strong className={styles.plage}>
            {soiree.debut_effectif === null ? '—' : heure(soiree.debut_effectif)}
            {' → '}
            {soiree.fin_effective === null ? '…' : heure(soiree.fin_effective)}
          </strong>
          <span className={styles.mesureDetail}>
            {soiree.responsable === null
              ? 'aucun opérateur désigné'
              : `${soiree.responsable.prenom} ${soiree.responsable.nom}`}
          </span>
        </div>
      </section>

      {soiree.cloture_conseillee !== null && soiree.transitions_possibles.length > 0 && (
        <p className={styles.conseil}>
          Toutes les étapes sont réglées : la soirée peut être close en «&nbsp;
          {soiree.cloture_conseillee}&nbsp;».
        </p>
      )}

      {grouperParSection(soiree.etapes).map((groupe) => {
        // Le compte par section, et non le seul total : à 2 h du matin, « où en suis-je » se
        // répond par « PART 3 à moitié faite », pas par « 19 étapes sur 28 ».
        const reglees = groupe.etapes.filter(estReglee).length;
        return (
          <section key={groupe.titre} className={styles.section}>
            <div className={styles.sectionEntete}>
              <h2 className={styles.sectionTitre}>{groupe.titre}</h2>
              <span
                className={
                  reglees === groupe.etapes.length ? styles.sectionFaite : styles.sectionCompte
                }
              >
                {reglees}/{groupe.etapes.length} réglées
              </span>
            </div>
            <table className={styles.tableau}>
              <thead>
                <tr>
                  <th>Étape</th>
                  <th className={styles.colHeure}>Début</th>
                  <th className={styles.colHeure}>Fin</th>
                  <th className={styles.colStatut}>Verdict</th>
                  <th>Observations</th>
                  <th className={styles.colRetrait} aria-label="Retirer" />
                </tr>
              </thead>
              <tbody>
                {groupe.etapes.map((e) => (
                  <tr key={e.id} className={e.statut === 'Anomalie' ? styles.ligneAnomalie : ''}>
                    <td>
                      <span className={styles.libelle} title={e.aide ?? undefined}>
                        {e.libelle}
                      </span>
                      {e.aide !== null && <span className={styles.aide}>{e.aide}</span>}
                    </td>

                    {e.nature === 'valeur' ? (
                      // « System Date » : ce qui compte n'est pas quand on a regardé, mais ce qu'on
                      // a lu. Une seule cellule, sur les deux colonnes d'heures.
                      <td colSpan={2} className={styles.valeur}>
                        <ChampInline
                          valeur={e.valeur ?? ''}
                          indication="jj/mm/aaaa"
                          lectureSeule={!peutEcrire}
                          onValider={(v) =>
                            void agir(`valeur:${e.id}`, () =>
                              eodApi.majEtape(id, e.id, {
                                valeur: v,
                                statut: v.trim() === '' ? 'À faire' : 'Complété',
                              }),
                            )
                          }
                          aria-label={`Valeur relevée — ${e.libelle}`}
                        />
                      </td>
                    ) : (
                      <>
                        <td className={styles.colHeure}>
                          {e.debut !== null ? (
                            <span className={styles.horodate}>{heure(e.debut)}</span>
                          ) : peutEcrire ? (
                            <button
                              className={styles.pointer}
                              disabled={occupe !== null}
                              onClick={() =>
                                void agir(`debut:${e.id}`, () => eodApi.pointer(id, e.id, 'debut'))
                              }
                            >
                              <Play size={13} /> Démarrer
                            </button>
                          ) : (
                            <span className={styles.vide}>—</span>
                          )}
                        </td>
                        <td className={styles.colHeure}>
                          {e.fin !== null ? (
                            <span className={styles.horodate}>{heure(e.fin)}</span>
                          ) : peutEcrire ? (
                            <button
                              className={styles.pointer}
                              disabled={occupe !== null}
                              onClick={() =>
                                void agir(`fin:${e.id}`, () => eodApi.pointer(id, e.id, 'fin'))
                              }
                            >
                              <Check size={13} /> Terminer
                            </button>
                          ) : (
                            <span className={styles.vide}>—</span>
                          )}
                        </td>
                      </>
                    )}

                    <td className={styles.colStatut}>
                      <StatusBadge couleur={COULEUR_STATUT[e.statut]}>{e.statut}</StatusBadge>
                      {peutEcrire && (
                        <div className={styles.verdicts}>
                          {VERDICTS.filter((v) => v.statut !== e.statut).map((v) => (
                            <button
                              key={v.statut}
                              className={styles.verdict}
                              title={v.libelle}
                              disabled={occupe !== null}
                              onClick={() => poserVerdict(e, v.statut)}
                            >
                              <v.icone size={13} />
                            </button>
                          ))}
                        </div>
                      )}
                    </td>

                    <td>
                      <Journal
                        etape={e}
                        deplie={deplies.has(e.id)}
                        onBasculer={() => basculerJournal(e.id)}
                      />
                      {peutEcrire ? (
                        <button
                          className={styles.consigner}
                          disabled={occupe !== null}
                          onClick={() => consigner(e, null)}
                        >
                          <MessageSquarePlus size={13} />
                          Consigner
                        </button>
                      ) : (
                        e.observations.length === 0 && <span className={styles.vide}>—</span>
                      )}
                    </td>

                    <td className={styles.colRetrait}>
                      {peutEcrire && (
                        <button
                          className={styles.retrait}
                          title="Retirer cette étape de la soirée"
                          disabled={occupe !== null}
                          onClick={() => setASupprimer(e)}
                        >
                          <X size={14} />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        );
      })}

      {peutEcrire && (
        <div className={styles.piedDeroule}>
          <Button variante="secondaire" onClick={() => setAjout(true)}>
            <Plus size={16} />
            Ajouter une étape à cette soirée
          </Button>
          <span className={styles.mesureDetail}>
            Une vérification exceptionnelle, un rattrapage : elle n’entre pas dans le déroulé de
            référence.
          </span>
        </div>
      )}

      <Modale
        ouverte={exportOuvert}
        onFermer={() => setExportOuvert(false)}
        titre="Rapport du soir"
        pied={
          <Button variante="secondaire" onClick={() => setExportOuvert(false)}>
            Fermer
          </Button>
        }
      >
        <p className={styles.mesureDetail}>
          {soiree.reste > 0
            ? `${soiree.reste} étape(s) ne sont pas encore réglées : le rapport les montrera « À faire ».`
            : 'Toutes les étapes sont réglées : le rapport rend compte de la nuit entière.'}
        </p>
        <div className={styles.formats}>
          <button
            className={styles.format}
            disabled={exportEnCours}
            onClick={() => void exporterPdf()}
          >
            <FileText size={18} />
            <span className={styles.formatNom}>{exportEnCours ? 'Composition…' : 'PDF'}</span>
            <span className={styles.formatQuoi}>
              Le document qui se remet et s’archive : en-tête AFG Bank Mali, synthèse de la nuit,
              déroulé complet et emplacements de visa.
            </span>
          </button>
          <button className={styles.format} onClick={() => telechargerTableur('xlsx')}>
            <FileSpreadsheet size={18} />
            <span className={styles.formatNom}>Excel</span>
            <span className={styles.formatQuoi}>
              Le tableau tel que la Production le lit depuis toujours, pour retraiter les heures.
            </span>
          </button>
          <button className={styles.format} onClick={() => telechargerTableur('csv')}>
            <Table2 size={18} />
            <span className={styles.formatNom}>CSV</span>
            <span className={styles.formatQuoi}>Les mêmes lignes, sans mise en forme.</span>
          </button>
        </div>
      </Modale>

      {/* Consigner : le geste qui manquait. Une observation s'ajoute au journal, elle n'écrase
          rien — et quand c'est une agence qui a bloqué, elle porte les trois informations que la
          hiérarchie réclame au matin : laquelle, à quelle heure on a relancé, ce qui a été fait. */}
      <Modale
        ouverte={consigne !== null}
        onFermer={fermerConsigne}
        titre={
          consigne?.verdict === null || consigne === null
            ? 'Consigner une observation'
            : `« ${consigne.verdict} » — dire ce qui s’est passé`
        }
        pied={
          <>
            <Button variante="secondaire" onClick={fermerConsigne}>
              Annuler
            </Button>
            <Button
              disabled={
                occupe !== null ||
                texteObs.trim().length < 2 ||
                (natureObs === 'incident' &&
                  ((agence ?? '').trim() === '' || relance.trim() === ''))
              }
              onClick={() => void envoyerObservation()}
            >
              Consigner
            </Button>
          </>
        }
      >
        {consigne !== null && (
          <p className={styles.mesureDetail}>
            {consigne.etape.section} · {consigne.etape.libelle}
          </p>
        )}
        <div className={styles.natures}>
          {(
            [
              { valeur: 'note', libelle: 'Observation' },
              { valeur: 'incident', libelle: 'Incident sur une agence' },
            ] as const
          ).map((n) => (
            <button
              key={n.valeur}
              className={natureObs === n.valeur ? styles.natureActive : styles.nature}
              onClick={() => setNatureObs(n.valeur)}
            >
              {n.libelle}
            </button>
          ))}
        </div>

        {natureObs === 'incident' && (
          <>
            <div className={styles.champ}>
              <span>Agence concernée</span>
              <SelecteurListe
                options={optionsAgences}
                valeur={agence}
                onChange={setAgence}
                placeholder="Choisir ou saisir une agence…"
                // La liste officielle oriente la saisie vers un nom unique par site ; le core
                // banking nomme aussi des agences qui lui sont propres (« 000 BAM »), et une nuit
                // ne doit pas s'arrêter faute de vocabulaire. Ce qu'on tape ici ne crée pas
                // d'entrée au référentiel du parc : ce n'est pas le même objet.
                onCreer={(libelle) => Promise.resolve(libelle)}
              />
            </div>
            <label className={styles.champ}>
              <span>Heure de relance</span>
              <input
                value={relance}
                onChange={(e) => setRelance(e.target.value)}
                placeholder="01H12"
                /* Pré-remplie à l'instant : on consigne sur le moment, et l'opérateur ne tape que
                   ce qu'il corrige. Le serveur en déduit la journée — l'EOD franchit minuit. */
              />
            </label>
          </>
        )}

        <label className={styles.champ}>
          <span>{natureObs === 'incident' ? 'Ce qui a été fait' : 'Observation'}</span>
          <textarea
            className={styles.note}
            rows={3}
            value={texteObs}
            onChange={(e) => setTexteObs(e.target.value)}
            placeholder={
              natureObs === 'incident'
                ? 'Ex. POSTEOPD3 bloqué, session purgée puis relancée — reprise OK.'
                : 'Ex. Batch terminé sans rejet.'
            }
          />
        </label>
        <p className={styles.mesureDetail}>
          Une fois consignée, une observation ne se corrige ni ne s’efface : elle est signée et
          horodatée. Ce qu’il faut rectifier se dit dans la suivante.
        </p>
      </Modale>

      <Modale
        ouverte={ajout}
        onFermer={() => setAjout(false)}
        titre="Ajouter une étape"
        pied={
          <>
            <Button variante="secondaire" onClick={() => setAjout(false)}>
              Annuler
            </Button>
            <Button
              disabled={libelleNouveau.trim().length < 2}
              onClick={() => {
                void agir('ajout', () =>
                  eodApi.ajouterEtape(id, {
                    section: sectionNouvelle,
                    libelle: libelleNouveau.trim(),
                  }),
                ).then(() => {
                  setAjout(false);
                  setLibelleNouveau('');
                });
              }}
            >
              Ajouter
            </Button>
          </>
        }
      >
        <label className={styles.champ}>
          <span>Section</span>
          <input value={sectionNouvelle} onChange={(e) => setSectionNouvelle(e.target.value)} />
        </label>
        <label className={styles.champ}>
          <span>Intitulé</span>
          <input
            value={libelleNouveau}
            onChange={(e) => setLibelleNouveau(e.target.value)}
            placeholder="Ex. Relance du batch EMS_OUT"
          />
        </label>
      </Modale>

      <Modale
        ouverte={transitionVisee !== null}
        onFermer={() => {
          setTransitionVisee(null);
          setNoteTransition('');
        }}
        titre={`Clore la soirée en « ${transitionVisee ?? ''} »`}
        pied={
          <>
            <Button
              variante="secondaire"
              onClick={() => {
                setTransitionVisee(null);
                setNoteTransition('');
              }}
            >
              Annuler
            </Button>
            <Button
              variante="danger"
              disabled={noteTransition.trim().length < 3}
              onClick={() => {
                if (transitionVisee !== null) void transitionner(transitionVisee);
              }}
            >
              Clore la soirée
            </Button>
          </>
        }
      >
        <p className={styles.mesureDetail}>
          {soiree.reste} étape(s) ne sont pas réglées. Dites pourquoi la soirée s’arrête là : sans
          cette note, les étapes restées «&nbsp;À faire&nbsp;» ne se reliront pas.
        </p>
        <textarea
          className={styles.note}
          rows={3}
          value={noteTransition}
          onChange={(e) => setNoteTransition(e.target.value)}
          placeholder="Ex. Reprise reportée au matin, batch EMS relancé par l'éditeur."
        />
      </Modale>

      <ModaleConfirmation
        demande={
          aSupprimer === null
            ? null
            : {
                titre: 'Retirer cette étape',
                message: `« ${aSupprimer.libelle} » sera retirée de cette soirée.`,
                libelleConfirmer: 'Retirer',
                variante: 'danger',
                action: () => agir('suppression', () => eodApi.supprimerEtape(id, aSupprimer.id)),
              }
        }
        onFermer={() => setASupprimer(null)}
      />
    </div>
  );
}
