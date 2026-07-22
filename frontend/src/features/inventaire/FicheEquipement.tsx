import { useCallback, useEffect, useState } from 'react';
import { TriangleAlert, X } from 'lucide-react';
import { Button, Skeleton, useToast } from '@/design-system/primitives';
import { ChampInline } from '@/common/ChampInline';
import { SelecteurListe } from '@/common/SelecteurListe';
import { SelecteurCategorie } from '@/common/SelecteurCategorie';
import { SelecteurDate } from '@/common/SelecteurDate';
import { BoutonSupprimer } from '@/common/BoutonSupprimer';
import { chargerAgents, type Agent } from '@/common/agentsApi';
import { useAuth } from '@/lib/auth';
import { ErreurApi } from '@/lib/api';
import fiche from '@/common/FicheTransition.module.css';
import local from './Inventaire.module.css';
import {
  inventaireApi,
  type EquipementDetail,
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
}

function montant(valeur: number | null): string {
  return valeur === null ? '—' : Math.round(valeur).toLocaleString('fr-FR');
}

function jour(iso: string | null): string {
  if (iso === null) return '—';
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

/** Fiche d'un équipement : identification, localisation, détenteur, et sa valeur au bilan. */
export function FicheEquipement({
  id,
  emplacements,
  departements,
  onFermer,
  onChange,
  onReferentiels,
}: Props): JSX.Element | null {
  const [detail, setDetail] = useState<EquipementDetail | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const { moi } = useAuth();
  const { notifier } = useToast();
  const estAdmin = moi?.profil === 'ADMIN';

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

  if (id === null) return null;

  return (
    <>
      <div className={fiche.voile} onClick={onFermer} />
      <aside className={fiche.panneau}>
        <header className={fiche.tete}>
          <div>
            <span className={fiche.reference}>{detail?.code_immo ?? 'Sans code immo'}</span>
            <h2 className={fiche.titre}>{detail?.designation ?? ''}</h2>
          </div>
          <button className={fiche.fermer} onClick={onFermer} aria-label="Fermer">
            <X size={18} />
          </button>
        </header>

        {detail === null ? (
          <div className={fiche.corps}>
            <Skeleton />
          </div>
        ) : (
          <div className={fiche.corps}>
            {detail.amortissement_incoherent && (
              <p className={local.avertissement}>
                <TriangleAlert size={15} />
                Le taux ({detail.taux} %) et la durée ({detail.duree_annees} ans) se contredisent.
                Le calcul retient le taux — à vérifier auprès de la comptabilité.
              </p>
            )}

            {/* Valeur au bilan : le chiffre que l'on vient chercher ici. */}
            <section className={local.bloc}>
              <span className={local.blocTitre}>Amortissement</span>
              <div className={local.valeurs}>
                <div className={local.valeur}>
                  <span>Valeur d'acquisition</span>
                  <b>{montant(detail.valeur_acquisition)}</b>
                </div>
                <div className={local.valeur}>
                  <span>Valeur nette comptable</span>
                  <b className={detail.totalement_amorti ? local.amortiFini : undefined}>
                    {montant(detail.valeur_nette)}
                  </b>
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
                <span className={local.amortiTexte}>
                  {detail.amorti_pct} % amorti
                  {detail.totalement_amorti && ' — ne vaut plus rien au bilan'}
                </span>
              )}
            </section>

            <dl className={fiche.meta}>
              <div className={fiche.metaItem}>
                <dt>Désignation</dt>
                <dd>
                  <ChampInline
                    valeur={detail.designation}
                    onValider={(v) => void patch({ designation: v })}
                    lectureSeule={!estAdmin}
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
                    lectureSeule={!estAdmin}
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
                    lectureSeule={!estAdmin}
                  />
                </dd>
              </div>
              <div className={fiche.metaItem}>
                <dt>Emplacement</dt>
                <dd>
                  <SelecteurCategorie
                    categories={emplacements}
                    valeur={detail.emplacement_id}
                    onChange={(v) => void patch({ emplacement_id: v })}
                    gerable={estAdmin}
                    entite="emplacement"
                    onAjouter={(l) => inventaireApi.ajouterReferentiel('emplacements', l)}
                    onModifie={onReferentiels}
                    desactive={!estAdmin}
                  />
                </dd>
              </div>
              <div className={fiche.metaItem}>
                <dt>Département</dt>
                <dd>
                  <SelecteurCategorie
                    categories={departements}
                    valeur={detail.departement_id}
                    onChange={(v) => void patch({ departement_id: v })}
                    gerable={estAdmin}
                    entite="département"
                    onAjouter={(l) => inventaireApi.ajouterReferentiel('departements', l)}
                    onModifie={onReferentiels}
                    desactive={!estAdmin}
                  />
                </dd>
              </div>
              <div className={fiche.metaItem}>
                <dt>Détenteur</dt>
                <dd>
                  <SelecteurListe
                    options={agents.map((a) => ({ valeur: a.id, libelle: a.nom }))}
                    valeur={detail.detenteur_id}
                    onChange={(v) => void patch({ detenteur_id: v })}
                    placeholder="Non attribué"
                    permettreVide
                    libelleVide="Non attribué"
                    desactive={!estAdmin}
                  />
                  {/* Le fichier nomme un matricule qu'aucun compte ne porte : à rattacher. */}
                  {detail.detenteur === null && detail.matricule !== null && (
                    <span className={local.brut}>
                      Matricule au fichier : {detail.matricule} — aucun compte ne le porte
                    </span>
                  )}
                </dd>
              </div>
              <div className={fiche.metaItem}>
                <dt>Date d'acquisition</dt>
                <dd>
                  <SelecteurDate
                    valeur={detail.date_acquisition}
                    onChange={(d) => void patch({ date_acquisition: d })}
                    placeholder="jj/mm/aaaa"
                    desactive={!estAdmin}
                  />
                </dd>
              </div>
              <div className={fiche.metaItem}>
                <dt>Provenance</dt>
                <dd>{detail.source === 'IMPORT_IMMO' ? 'Import comptable' : 'Saisie DSI'}</dd>
              </div>
            </dl>

            {estAdmin && (
              <div className={local.actions}>
                {/* Sortir du parc plutôt que supprimer : l'historique compte. */}
                <Button variante="secondaire" onClick={() => void patch({ actif: !detail.actif })}>
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
          </div>
        )}
      </aside>
    </>
  );
}
