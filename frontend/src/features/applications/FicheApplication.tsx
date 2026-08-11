import { useCallback, useEffect, useState } from 'react';
import { History, TriangleAlert } from 'lucide-react';
import { Button, Skeleton, StatusBadge, Modale, useToast } from '@/design-system/primitives';
import { ChampInline } from '@/common/ChampInline';
import { SelecteurCategorie } from '@/common/SelecteurCategorie';
import { SelecteurListe } from '@/common/SelecteurListe';
import { SelecteurDate } from '@/common/SelecteurDate';
import { BoutonSupprimer } from '@/common/BoutonSupprimer';
import { useAuth } from '@/lib/auth';
import { ErreurApi } from '@/lib/api';
import fiche from '@/common/FicheTransition.module.css';
import { COULEUR_ACTION_JOURNAL } from '@/common/FicheTransition';
import local from '@/features/inventaire/Inventaire.module.css';
import {
  applicationsApi,
  COULEUR_HEBERGEMENT,
  COULEUR_STATUT,
  HEBERGEMENTS,
  INTERFACAGES,
  LIBELLE_HEBERGEMENT,
  LIBELLE_STATUT,
  STATUTS,
  type ApplicationDetail,
  type MajApplication,
  type ReferentielItem,
} from './applicationsApi';

interface Props {
  id: string | null;
  editeurs: ReferentielItem[];
  onFermer: () => void;
  onChange: () => void;
  /** Recharge le référentiel des éditeurs après un ajout à la volée. */
  onEditeurs: () => void;
}

const LIBELLE_ACTION: Record<string, string> = {
  CREATION: 'Création',
  MODIFICATION: 'Modification',
  SUPPRESSION: 'Suppression',
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

function versEntier(brut: string): number | null {
  const chiffres = brut.replace(/[^\d]/g, '');
  return chiffres === '' ? null : Number(chiffres);
}

/** Fiche d'une application : ce qu'elle sert, de qui elle dépend, et qui en répond. */
export function FicheApplication({
  id,
  editeurs,
  onFermer,
  onChange,
  onEditeurs,
}: Props): JSX.Element {
  const [detail, setDetail] = useState<ApplicationDetail | null>(null);
  const { moi } = useAuth();
  const { notifier } = useToast();
  const estAdmin = moi?.profil === 'ADMIN';
  // Une application retirée reste corrigible : le journal garde la trace de qui change quoi.
  const modifiable = estAdmin;
  const raisonVerrou = "Réservé à l'administrateur";

  const charger = useCallback(async (): Promise<void> => {
    if (id === null) return;
    setDetail(await applicationsApi.detail(id));
  }, [id]);

  useEffect(() => {
    setDetail(null);
    void charger();
  }, [charger]);

  const patch = async (corps: MajApplication): Promise<void> => {
    if (id === null) return;
    try {
      setDetail(await applicationsApi.modifier(id, corps));
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
      titre={detail?.nom ?? 'Application'}
      largeur={720}
      pied={
        <>
          {detail !== null && modifiable && (
            <div className={local.piedActions}>
              <Button
                variante="secondaire"
                className={detail.actif ? local.btnSortir : local.btnRemettre}
                onClick={() => void patch({ actif: !detail.actif })}
                title={
                  detail.actif
                    ? "Décommissionnée : elle quitte le parc actif, son historique reste"
                    : 'La remettre au parc actif'
                }
              >
                {detail.actif ? 'Retirer du parc' : 'Remettre en service'}
              </Button>
              <BoutonSupprimer
                cible={`l'application « ${detail.nom} »`}
                onSupprimer={async () => {
                  await applicationsApi.supprimer(detail.id);
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
          {/* L'essentiel en badges : ce qui tourne, où, et si ça sort de nos murs. */}
          <div className={local.badges}>
            <span className={local.badgeTitre}>{detail.nom}</span>
            {detail.actif ? (
              <StatusBadge couleur={COULEUR_STATUT[detail.statut] ?? 'var(--text-muted)'}>
                {LIBELLE_STATUT[detail.statut] ?? detail.statut}
              </StatusBadge>
            ) : (
              <StatusBadge statut="danger">Retirée du parc</StatusBadge>
            )}
            {detail.hebergement !== null && (
              <StatusBadge couleur={COULEUR_HEBERGEMENT[detail.hebergement] ?? 'var(--cat-1)'}>
                {LIBELLE_HEBERGEMENT[detail.hebergement] ?? detail.hebergement}
              </StatusBadge>
            )}
            {detail.interfacage === 'OUI' && (
              <StatusBadge couleur="var(--cat-4)">Interfacée</StatusBadge>
            )}
            <StatusBadge couleur="var(--cat-5)">
              {detail.source === 'CHARGEMENT_INITIAL' ? 'Liste initiale' : 'Saisie DSI'}
            </StatusBadge>
          </div>

          {/* Une application administrée par une seule personne s'arrête avec elle. Ce n'est pas
              une faute de saisie, c'est un risque de continuité — on le dit. */}
          {detail.administrateur_secours === null && (
            <p className={local.avertissement}>
              <TriangleAlert size={15} />
              Aucun administrateur de secours : la continuité de cette application tient à une
              seule personne.
            </p>
          )}

          <section className={local.bloc}>
            <span className={local.blocTitre}>Qui en répond</span>
            <div className={local.valeurs}>
              <div className={local.valeur}>
                <span>Administrateur</span>
                <ChampInline
                  valeur={detail.administrateur ?? ''}
                  onValider={(v) => void patch({ administrateur: v })}
                  placeholder="—"
                  lectureSeule={!modifiable}
                  titreLectureSeule={raisonVerrou}
                  classeTexte={local.valeurEdit}
                  aria-label="Administrateur"
                />
              </div>
              <div className={local.valeur}>
                <span>Administrateur de secours</span>
                <ChampInline
                  valeur={detail.administrateur_secours ?? ''}
                  onValider={(v) => void patch({ administrateur_secours: v })}
                  placeholder="—"
                  lectureSeule={!modifiable}
                  titreLectureSeule={raisonVerrou}
                  classeTexte={local.valeurEdit}
                  aria-label="Administrateur de secours"
                />
              </div>
              <div className={local.valeur}>
                <span>Propriétaire métier</span>
                <ChampInline
                  valeur={detail.proprietaire ?? ''}
                  onValider={(v) => void patch({ proprietaire: v })}
                  placeholder="—"
                  lectureSeule={!modifiable}
                  titreLectureSeule={raisonVerrou}
                  classeTexte={local.valeurEdit}
                  aria-label="Propriétaire métier"
                />
              </div>
              <div className={local.valeur}>
                <span>Comptes actifs</span>
                <ChampInline
                  valeur={
                    detail.nb_comptes_actifs === null ? '' : String(detail.nb_comptes_actifs)
                  }
                  onValider={(v) => void patch({ nb_comptes_actifs: versEntier(v) })}
                  placeholder="—"
                  inputMode="numeric"
                  lectureSeule={!modifiable}
                  titreLectureSeule={raisonVerrou}
                  classeTexte={local.valeurEdit}
                  aria-label="Nombre de comptes actifs"
                />
              </div>
            </div>
          </section>

          <dl className={fiche.meta}>
            <div className={`${fiche.metaItem} ${fiche.metaLarge}`}>
              <dt>Nom</dt>
              <dd>
                <ChampInline
                  valeur={detail.nom}
                  onValider={(v) => void patch({ nom: v })}
                  lectureSeule={!modifiable}
                  titreLectureSeule={raisonVerrou}
                />
              </dd>
            </div>
            <div className={fiche.metaItem}>
              <dt>Référence</dt>
              <dd>
                {/* Référence système, attribuée par la plateforme : jamais saisie, jamais modifiée. */}
                <span className={local.technique}>{detail.reference}</span>
              </dd>
            </div>
            <div className={fiche.metaItem}>
              <dt>Version</dt>
              <dd>
                <ChampInline
                  valeur={detail.version ?? ''}
                  onValider={(v) => void patch({ version: v })}
                  placeholder="—"
                  lectureSeule={!modifiable}
                  titreLectureSeule={raisonVerrou}
                  classeTexte={local.technique}
                />
              </dd>
            </div>
            <div className={`${fiche.metaItem} ${fiche.metaLarge}`}>
              <dt>Processus métier servi</dt>
              <dd>
                <ChampInline
                  valeur={detail.processus_metier ?? ''}
                  onValider={(v) => void patch({ processus_metier: v })}
                  placeholder="—"
                  lectureSeule={!modifiable}
                  titreLectureSeule={raisonVerrou}
                />
              </dd>
            </div>
            <div className={`${fiche.metaItem} ${fiche.metaLarge}`}>
              <dt>Principales fonctionnalités</dt>
              <dd>
                <ChampInline
                  valeur={detail.fonctionnalites ?? ''}
                  onValider={(v) => void patch({ fonctionnalites: v })}
                  placeholder="—"
                  multiligne
                  lectureSeule={!modifiable}
                  titreLectureSeule={raisonVerrou}
                />
              </dd>
            </div>
            <div className={`${fiche.metaItem} ${fiche.metaLarge}`}>
              <dt>Éditeur</dt>
              <dd>
                <SelecteurCategorie
                  categories={editeurs}
                  valeur={detail.editeur_id}
                  onChange={(v) => void patch({ editeur_id: v })}
                  gerable={modifiable}
                  compact
                  accent="var(--cat-2)"
                  entite="éditeur"
                  onAjouter={(l) => applicationsApi.ajouterEditeur(l)}
                  onSupprimer={(eid) => applicationsApi.supprimerEditeur(eid)}
                  onModifie={onEditeurs}
                  desactive={!modifiable}
                  titreDesactive={raisonVerrou}
                />
              </dd>
            </div>
            <div className={fiche.metaItem}>
              <dt>Statut</dt>
              <dd>
                <SelecteurListe
                  options={STATUTS.map((s) => ({ valeur: s.valeur, libelle: s.libelle }))}
                  valeur={detail.statut}
                  onChange={(v) => v !== null && void patch({ statut: v })}
                  couleurs={COULEUR_STATUT}
                  desactive={!modifiable}
                  titreDesactive={raisonVerrou}
                />
              </dd>
            </div>
            <div className={fiche.metaItem}>
              <dt>Hébergement</dt>
              <dd>
                <SelecteurListe
                  options={HEBERGEMENTS.map((h) => ({ valeur: h.valeur, libelle: h.libelle }))}
                  valeur={detail.hebergement}
                  onChange={(v) => void patch({ hebergement: v })}
                  placeholder="Non renseigné"
                  permettreVide
                  libelleVide="Non renseigné"
                  couleurs={COULEUR_HEBERGEMENT}
                  desactive={!modifiable}
                  titreDesactive={raisonVerrou}
                />
              </dd>
            </div>
            <div className={fiche.metaItem}>
              <dt>Interfaçage</dt>
              <dd>
                <SelecteurListe
                  options={INTERFACAGES.map((i) => ({ valeur: i.valeur, libelle: i.libelle }))}
                  valeur={detail.interfacage}
                  onChange={(v) => void patch({ interfacage: v })}
                  placeholder="Non renseigné"
                  permettreVide
                  libelleVide="Non renseigné"
                  desactive={!modifiable}
                  titreDesactive={raisonVerrou}
                />
              </dd>
            </div>
            <div className={fiche.metaItem}>
              <dt>Pays des données</dt>
              <dd>
                <ChampInline
                  valeur={detail.pays_donnees ?? ''}
                  onValider={(v) => void patch({ pays_donnees: v })}
                  placeholder="—"
                  lectureSeule={!modifiable}
                  titreLectureSeule={raisonVerrou}
                />
              </dd>
            </div>
            <div className={fiche.metaItem}>
              <dt>Mise en service</dt>
              <dd>
                <SelecteurDate
                  valeur={detail.date_debut}
                  onChange={(d) => void patch({ date_debut: d })}
                  placeholder="jj/mm/aaaa"
                  desactive={!modifiable}
                />
              </dd>
            </div>
            <div className={fiche.metaItem}>
              <dt>Fin de service</dt>
              <dd>
                <SelecteurDate
                  valeur={detail.date_fin}
                  onChange={(d) => void patch({ date_fin: d })}
                  placeholder="jj/mm/aaaa"
                  desactive={!modifiable}
                />
              </dd>
            </div>
            <div className={fiche.metaItem}>
              <dt>Serveur d'application</dt>
              <dd>
                <ChampInline
                  valeur={detail.serveur_application ?? ''}
                  onValider={(v) => void patch({ serveur_application: v })}
                  placeholder="—"
                  lectureSeule={!modifiable}
                  titreLectureSeule={raisonVerrou}
                  classeTexte={local.technique}
                />
              </dd>
            </div>
            <div className={fiche.metaItem}>
              <dt>Serveur de base de données</dt>
              <dd>
                <ChampInline
                  valeur={detail.serveur_base ?? ''}
                  onValider={(v) => void patch({ serveur_base: v })}
                  placeholder="—"
                  lectureSeule={!modifiable}
                  titreLectureSeule={raisonVerrou}
                  classeTexte={local.technique}
                />
              </dd>
            </div>
            <div className={fiche.metaItem}>
              <dt>Port</dt>
              <dd>
                <ChampInline
                  valeur={detail.port ?? ''}
                  onValider={(v) => void patch({ port: v })}
                  placeholder="—"
                  lectureSeule={!modifiable}
                  titreLectureSeule={raisonVerrou}
                  classeTexte={local.technique}
                />
              </dd>
            </div>
            <div className={`${fiche.metaItem} ${fiche.metaLarge}`}>
              <dt>Lien d'accès</dt>
              <dd>
                <ChampInline
                  valeur={detail.lien ?? ''}
                  onValider={(v) => void patch({ lien: v })}
                  placeholder="—"
                  lectureSeule={!modifiable}
                  titreLectureSeule={raisonVerrou}
                />
              </dd>
            </div>
          </dl>

          {/* La mémoire administrative de l'application : qui a fait quoi, quand. */}
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
