import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Check,
  FileSpreadsheet,
  Play,
  Plus,
  RotateCcw,
  SlashSquare,
  TriangleAlert,
  X,
} from 'lucide-react';
import { Button, Modale, StatusBadge, useToast } from '@/design-system/primitives';
import { BarreAvancement } from '@/common/BarreAvancement';
import { ChampInline } from '@/common/ChampInline';
import { ModaleConfirmation } from '@/common/ModaleConfirmation';
import { BadgeStatut } from '@/common/statuts';
import { ErreurApi, telecharger } from '@/lib/api';
import { eodApi, heure, jour, type DetailEod, type EtapeEod, type StatutEtape } from './eodApi';
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

/** Amorce d'observation posée avec un verdict qui, sans explication, serait refusé.
 *
 *  Le serveur exige une justification pour « Anomalie » et « Non applicable » — à juste titre :
 *  six semaines plus tard, un verdict nu ne se relit pas. Mais renvoyer une erreur à l'opérateur
 *  pour un geste légitime, en pleine nuit, serait le punir d'avoir bien fait. On écrit donc une
 *  amorce qu'il remplace, et l'observation reste à sa main. Une note déjà écrite n'est jamais
 *  touchée. */
function amorceNotes(statut: StatutEtape, notes: string | null): { notes?: string } {
  if ((notes ?? '').trim() !== '') return {};
  if (statut === 'Anomalie') return { notes: 'À préciser' };
  if (statut === 'Non applicable') return { notes: 'Sans objet ce soir' };
  return {};
}

function sections(etapes: EtapeEod[]): { titre: string; etapes: EtapeEod[] }[] {
  const groupes: { titre: string; etapes: EtapeEod[] }[] = [];
  for (const e of etapes) {
    const dernier = groupes[groupes.length - 1];
    if (dernier !== undefined && dernier.titre === e.section) dernier.etapes.push(e);
    else groupes.push({ titre: e.section, etapes: [e] });
  }
  return groupes;
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
              Fin de journée — {jour(soiree.journee)}
              <BadgeStatut statut={soiree.statut} module="eod" />
              {soiree.categorie !== null && (
                <StatusBadge couleur="var(--cat-6)">{soiree.categorie}</StatusBadge>
              )}
            </h1>
          </div>
        </div>
        <div className={styles.actions}>
          <Button
            variante="secondaire"
            onClick={() => void telecharger(`/eod/${id}/rapport?format=xlsx`)}
          >
            <FileSpreadsheet size={16} />
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

      {sections(soiree.etapes).map((groupe) => (
        <section key={groupe.titre} className={styles.section}>
          <h2 className={styles.sectionTitre}>{groupe.titre}</h2>
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
                            onClick={() =>
                              void agir(`statut:${e.id}`, () =>
                                eodApi.majEtape(id, e.id, {
                                  statut: v.statut,
                                  ...amorceNotes(v.statut, e.notes),
                                }),
                              )
                            }
                          >
                            <v.icone size={13} />
                          </button>
                        ))}
                      </div>
                    )}
                  </td>

                  <td>
                    <ChampInline
                      valeur={e.notes ?? ''}
                      multiligne
                      indication="Ce qu'il faut retenir de cette étape…"
                      lectureSeule={!peutEcrire}
                      repliable={2}
                      onValider={(v) =>
                        void agir(`notes:${e.id}`, () => eodApi.majEtape(id, e.id, { notes: v }))
                      }
                      aria-label={`Observations — ${e.libelle}`}
                    />
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
      ))}

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
