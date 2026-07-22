import { useCallback, useEffect, useState } from 'react';
import { History, TriangleAlert } from 'lucide-react';
import { Button, Modale, Skeleton, StatusBadge, useToast } from '@/design-system/primitives';
import { ChampInline } from '@/common/ChampInline';
import { SelecteurListe } from '@/common/SelecteurListe';
import { SelecteurCategorie } from '@/common/SelecteurCategorie';
import { SelecteurDate } from '@/common/SelecteurDate';
import { BoutonSupprimer } from '@/common/BoutonSupprimer';
import { chargerAgents, type Agent } from '@/common/agentsApi';
import { useAuth } from '@/lib/auth';
import { ErreurApi } from '@/lib/api';
import fiche from '@/common/FicheTransition.module.css';
import { COULEUR_ACTION_JOURNAL } from '@/common/FicheTransition';
import local from './Inventaire.module.css';
import { CurseurTaux } from './CurseurTaux';
import { DiscussionEquipement } from './DiscussionEquipement';
import {
  CONSTATS,
  inventaireApi,
  type EquipementDetail,
  type EtatConstat,
  type MajEquipement,
  type ReferentielItem,
} from './inventaireApi';

interface Props {
  id: string | null;
  emplacements: ReferentielItem[];
  departements: ReferentielItem[];
  onFermer: () => void;
  onChange: () => void;
  /** Recharge les référentiels après un ajout à la volée. */
  onReferentiels: () => void;
  /** Campagne ouverte : la fiche permet aussi de poser le constat, comme la liste. */
  recensement?: {
    libelle: string;
    etat: string | null;
    onConstat: (etat: EtatConstat) => void;
  } | null;
}

function montant(valeur: number | null): string {
  return valeur === null ? '—' : Math.round(valeur).toLocaleString('fr-FR');
}

function versEntier(brut: string): number | null {
  const chiffres = brut.replace(/[^\d]/g, '');
  return chiffres === '' ? null : Number(chiffres);
}


const LIBELLE_ACTION: Record<string, string> = {
  CREATION: 'Création',
  MODIFICATION: 'Modification',
  SUPPRESSION: 'Suppression',
  IMPORT: 'Import comptable',
  COMMENTAIRE: 'Commentaire',
  CONSTAT: "Constat d'inventaire",
};

function horodatage(iso: string): string {
  return new Date(iso).toLocaleString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function jour(iso: string | null): string {
  if (iso === null) return '—';
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

/** Fiche d'un équipement, dans la même modale à deux volets que les activités : le dossier à
 *  gauche, la discussion interne à droite. */
export function FicheEquipement({
  id,
  emplacements,
  departements,
  onFermer,
  onChange,
  onReferentiels,
  recensement = null,
}: Props): JSX.Element {
  const [detail, setDetail] = useState<EquipementDetail | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const { moi } = useAuth();
  const { notifier } = useToast();
  const estAdmin = moi?.profil === 'ADMIN';
  // Sorti du parc = dossier clos : la fiche se relit, elle ne s'édite plus. Le serveur
  // refuse de toute façon (409) — ici on évite juste de proposer l'impossible.
  const modifiable = estAdmin && detail?.actif === true;
  const raisonVerrou = !estAdmin
    ? "Réservé à l'administrateur"
    : 'Sorti du parc : remettez-le en service pour modifier';

  const charger = useCallback(async (): Promise<void> => {
    if (id === null) return;
    setDetail(await inventaireApi.detail(id));
  }, [id]);

  useEffect(() => {
    setDetail(null);
    void charger();
  }, [charger]);
  useEffect(() => {
    void chargerAgents().then(setAgents);
  }, []);

  const patch = async (corps: MajEquipement): Promise<void> => {
    if (id === null) return;
    try {
      setDetail(await inventaireApi.modifier(id, corps));
      onChange();
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Modification impossible.', 'erreur');
      void charger();
    }
  };

  return (
    <Modale
      ouverte={id !== null}
      onFermer={onFermer}
      titre={detail?.code_immo ?? detail?.designation ?? 'Équipement'}
      largeur={640}
      largeurPanneau={450}
      panneau={<DiscussionEquipement equipementId={id} agents={agents} />}
      etiquettes={
        // Les constats de la campagne ouverte, collés au bord du dossier comme des stickers :
        // ce qu'on voit du matériel, on le dit sans quitter la fiche.
        recensement !== null && detail !== null && detail.actif ? (
          <>
            {CONSTATS.map(({ etat, libelle, couleur }) => (
              <button
                key={etat}
                type="button"
                className={recensement.etat === etat ? local.stickerOn : local.sticker}
                // La couleur sémantique en variable : posée elle remplit le sticker,
                // sinon elle s'annonce au survol.
                style={
                  {
                    '--constat': couleur,
                    ...(recensement.etat === etat
                      ? { background: couleur, borderColor: couleur }
                      : {}),
                  } as React.CSSProperties
                }
                onClick={() => recensement.onConstat(etat)}
                title={`Constat — ${recensement.libelle}`}
              >
                {libelle}
              </button>
            ))}
          </>
        ) : undefined
      }
      pied={
        <>
          {/* Les actions sur le matériel à gauche, la sortie de l'écran à droite : même
              niveau, deux intentions distinctes. */}
          {estAdmin && detail !== null && (
            <div className={local.piedActions}>
              {/* La couleur dit le sens : rouge pour sortir du parc, vert pour y revenir. */}
              <Button
                variante="secondaire"
                className={detail.actif ? local.btnSortir : local.btnRemettre}
                onClick={() => void patch({ actif: !detail.actif })}
              >
                {detail.actif ? 'Sortir du parc' : 'Remettre en service'}
              </Button>
              <BoutonSupprimer
                cible={`l'équipement « ${detail.designation} »`}
                onSupprimer={async () => {
                  await inventaireApi.supprimer(detail.id);
                  onChange();
                  onFermer();
                }}
              />
            </div>
          )}
          <Button variante="secondaire" onClick={onFermer}>
            Fermer
          </Button>
        </>
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
          {/* L'essentiel en badges, d'un coup d'œil : l'état, la provenance, le verdict du bilan.
              La couleur porte le sens — vert en service, rouge sorti ou amorti. */}
          <div className={local.badges}>
            <span className={local.badgeTitre}>{detail.designation}</span>
            {detail.actif ? (
              <StatusBadge statut="ok">En service</StatusBadge>
            ) : (
              <StatusBadge statut="danger">Sorti du parc</StatusBadge>
            )}
            <StatusBadge couleur="var(--cat-5)">
              {detail.source === 'IMPORT_IMMO' ? 'Import comptable' : 'Saisie DSI'}
            </StatusBadge>
            {detail.totalement_amorti && (
              <StatusBadge couleur="var(--text-muted)">Totalement amorti</StatusBadge>
            )}
          </div>

          {detail.amortissement_incoherent && (
            <p className={local.avertissement}>
              <TriangleAlert size={15} />
              Le taux ({detail.taux} %) et la durée ({detail.duree_annees} ans) se contredisent. Le
              calcul retient le taux — à vérifier auprès de la comptabilité.
            </p>
          )}

          {/* Valeur au bilan : le chiffre que l'on vient chercher ici. Les trois paramètres du
              calcul (valeur, taux, durée) se corrigent sur place — l'administrateur n'a pas à
              chercher un autre écran pour rectifier une donnée comptable. */}
          <section className={local.bloc}>
            <span className={local.blocTitre}>Amortissement</span>
            <div className={local.valeurs}>
              <div className={local.valeur}>
                <span>Valeur d'acquisition (FCFA)</span>
                <ChampInline
                  valeur={
                    detail.valeur_acquisition === null
                      ? ''
                      : Math.round(detail.valeur_acquisition).toLocaleString('fr-FR')
                  }
                  onValider={(v) => void patch({ valeur_acquisition: versEntier(v) })}
                  placeholder="—"
                  lectureSeule={!modifiable}
                  titreLectureSeule={raisonVerrou}
                  classeTexte={local.valeurEdit}
                  aria-label="Valeur d'acquisition"
                />
              </div>
              <div className={local.valeur}>
                <span>Valeur nette comptable</span>
                <b className={detail.totalement_amorti ? local.amortiFini : undefined}>
                  {montant(detail.valeur_nette)}
                </b>
              </div>
              <div className={local.valeur}>
                <span>Taux d'amortissement</span>
                <CurseurTaux
                  valeur={detail.taux}
                  onValider={(t) => void patch({ taux: t })}
                  desactive={!modifiable}
                />
              </div>
              <div className={local.valeur}>
                <span>Durée (années)</span>
                <ChampInline
                  valeur={detail.duree_annees !== null ? String(detail.duree_annees) : ''}
                  onValider={(v) => void patch({ duree_annees: versEntier(v) })}
                  placeholder="—"
                  lectureSeule={!modifiable}
                  titreLectureSeule={raisonVerrou}
                  classeTexte={local.valeurEdit}
                  aria-label="Durée d'amortissement"
                />
              </div>
              <div className={local.valeur}>
                <span>Dotation annuelle</span>
                <b>{montant(detail.dotation_annuelle)}</b>
              </div>
              <div className={local.valeur}>
                <span>Fin d'amortissement</span>
                <b>{jour(detail.fin_amortissement)}</b>
              </div>
            </div>
            {detail.amorti_pct !== null && (
              <div className={local.jaugeAmorti}>
                <span className={local.avanceePiste}>
                  <span
                    className={local.avanceePlein}
                    style={{
                      width: `${Math.min(100, detail.amorti_pct)}%`,
                      // La couleur suit l'usure : vert tant que le bien vaut, rouge à zéro.
                      background:
                        detail.amorti_pct >= 100
                          ? 'var(--status-danger)'
                          : detail.amorti_pct >= 75
                            ? 'var(--status-warn)'
                            : 'var(--secondary)',
                    }}
                  />
                </span>
                <span className={local.amortiTexte}>{detail.amorti_pct} % amorti</span>
              </div>
            )}
          </section>

          <dl className={fiche.meta}>
            <div className={`${fiche.metaItem} ${fiche.metaLarge}`}>
              <dt>Désignation</dt>
              <dd>
                <ChampInline
                  valeur={detail.designation}
                  onValider={(v) => void patch({ designation: v })}
                  lectureSeule={!modifiable}
                  titreLectureSeule={raisonVerrou}
                />
              </dd>
            </div>
            <div className={fiche.metaItem}>
              <dt>Code d'immobilisation</dt>
              <dd>
                <ChampInline
                  valeur={detail.code_immo ?? ''}
                  onValider={(v) => void patch({ code_immo: v })}
                  placeholder="—"
                  lectureSeule={!modifiable}
                  titreLectureSeule={raisonVerrou}
                  classeTexte={local.technique}
                />
              </dd>
            </div>
            <div className={fiche.metaItem}>
              <dt>N° de série</dt>
              <dd>
                <ChampInline
                  valeur={detail.numero_serie ?? ''}
                  onValider={(v) => void patch({ numero_serie: v })}
                  placeholder="—"
                  lectureSeule={!modifiable}
                  titreLectureSeule={raisonVerrou}
                  classeTexte={local.technique}
                />
              </dd>
            </div>
            <div className={fiche.metaItem}>
              <dt>Modèle</dt>
              <dd>
                <ChampInline
                  valeur={detail.modele ?? ''}
                  onValider={(v) => void patch({ modele: v })}
                  placeholder="—"
                  lectureSeule={!modifiable}
                  titreLectureSeule={raisonVerrou}
                />
              </dd>
            </div>
            <div className={fiche.metaItem}>
              <dt>Date d'acquisition</dt>
              <dd>
                <SelecteurDate
                  valeur={detail.date_acquisition}
                  onChange={(d) => void patch({ date_acquisition: d })}
                  placeholder="jj/mm/aaaa"
                  desactive={!modifiable}
                />
              </dd>
            </div>
            <div className={`${fiche.metaItem} ${fiche.metaLarge}`}>
              <dt>Emplacement</dt>
              <dd>
                <SelecteurCategorie
                  categories={emplacements}
                  valeur={detail.emplacement_id}
                  onChange={(v) => void patch({ emplacement_id: v })}
                  gerable={modifiable}
                  compact
                  accent="var(--cat-1)"
                  entite="emplacement"
                  onAjouter={(l) => inventaireApi.ajouterReferentiel('emplacements', l)}
                  onModifie={onReferentiels}
                  desactive={!modifiable}
                  titreDesactive={raisonVerrou}
                />
              </dd>
            </div>
            <div className={`${fiche.metaItem} ${fiche.metaLarge}`}>
              <dt>Département</dt>
              <dd>
                <SelecteurCategorie
                  categories={departements}
                  valeur={detail.departement_id}
                  onChange={(v) => void patch({ departement_id: v })}
                  gerable={modifiable}
                  compact
                  accent="var(--cat-2)"
                  entite="département"
                  onAjouter={(l) => inventaireApi.ajouterReferentiel('departements', l)}
                  onModifie={onReferentiels}
                  desactive={!modifiable}
                  titreDesactive={raisonVerrou}
                />
              </dd>
            </div>
            <div className={`${fiche.metaItem} ${fiche.metaLarge}`}>
              <dt>Détenteur</dt>
              <dd>
                <SelecteurListe
                  options={agents.map((a) => ({ valeur: a.id, libelle: a.nom }))}
                  valeur={detail.detenteur_id}
                  onChange={(v) => void patch({ detenteur_id: v })}
                  placeholder="Non attribué"
                  permettreVide
                  libelleVide="Non attribué"
                  indiceReaffectation="Réassigner"
                  desactive={!modifiable}
                />
                {/* Le fichier nomme un matricule qu'aucun compte ne porte : à rattacher. */}
                {detail.detenteur === null && detail.matricule !== null && (
                  <span className={local.brut}>
                    Matricule au fichier : {detail.matricule} — aucun compte ne le porte
                  </span>
                )}
              </dd>
            </div>
          </dl>

          {/* La mémoire administrative du matériel : qui a fait quoi, quand. */}
          {detail.historique.length > 0 && (
            <section className={local.histo}>
              <span className={local.blocTitre}>
                <History size={13} /> Historique
              </span>
              <ul className={local.histoListe}>
                {detail.historique.map((h, i) => (
                  <li key={i} className={local.histoLigne}>
                    <span
                      className={local.histoAction}
                      style={{ color: COULEUR_ACTION_JOURNAL[h.action] ?? 'var(--text)' }}
                    >
                      {LIBELLE_ACTION[h.action] ?? h.action}
                    </span>
                    <span className={local.histoActeur}>{h.acteur ?? '—'}</span>
                    <span className={local.histoDate}>{horodatage(h.horodatage)}</span>
                    {/* L'acheminement du matériel : ce qui a changé, en clair. */}
                    {h.detail !== null && (
                      <span className={local.histoDetail}>{h.detail}</span>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}

        </div>
      )}
    </Modale>
  );
}
