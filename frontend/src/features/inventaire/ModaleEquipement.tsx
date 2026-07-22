import { useState } from 'react';
import { Button, Modale } from '@/design-system/primitives';
import { SelecteurCategorie } from '@/common/SelecteurCategorie';
import { SelecteurDate } from '@/common/SelecteurDate';
import styles from '@/features/incidents/IncidentsPage.module.css';
import local from './Inventaire.module.css';
import {
  inventaireApi,
  type EquipementDetail,
  type NouvelEquipement,
  type ReferentielItem,
} from './inventaireApi';

interface Props {
  ouverte: boolean;
  /** L'administrateur peut créer un emplacement ou un département sans quitter la modale. */
  gerable: boolean;
  onReferentiels: () => void;
  emplacements: ReferentielItem[];
  departements: ReferentielItem[];
  onFermer: () => void;
  onCree: (cree: EquipementDetail) => void;
  onErreur: (e: unknown) => void;
}

const VIDE: NouvelEquipement = { designation: '' };

/** Saisie d'un équipement. Seule la désignation est exigée : le reste se complète au fil de l'eau. */
export function ModaleEquipement({
  ouverte,
  emplacements,
  departements,
  gerable,
  onReferentiels,
  onFermer,
  onCree,
  onErreur,
}: Props): JSX.Element {
  const [v, setV] = useState<NouvelEquipement>(VIDE);
  const [envoi, setEnvoi] = useState(false);

  const nombre = (brut: string): number | null => {
    const chiffres = brut.replace(/[^\d]/g, '');
    return chiffres === '' ? null : Number(chiffres);
  };

  const creer = async (): Promise<void> => {
    setEnvoi(true);
    try {
      const cree = await inventaireApi.creer(v);
      setV(VIDE);
      onCree(cree);
    } catch (e) {
      onErreur(e);
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <Modale
      ouverte={ouverte}
      onFermer={onFermer}
      titre="Nouvel équipement"
      pied={
        <>
          <Button variante="secondaire" onClick={onFermer}>
            Annuler
          </Button>
          <Button onClick={() => void creer()} disabled={envoi || v.designation.trim().length < 2}>
            {envoi ? 'Création…' : 'Créer'}
          </Button>
        </>
      }
    >
      <label className={styles.champ}>
        <span>Désignation</span>
        <input
          value={v.designation}
          onChange={(e) => setV({ ...v, designation: e.target.value })}
          placeholder="Ex. GAB NCR SelfServ 25"
        />
      </label>

      <div className={local.paire}>
        <label className={styles.champ}>
          <span>Code d'immobilisation</span>
          <input
            value={v.code_immo ?? ''}
            onChange={(e) => setV({ ...v, code_immo: e.target.value })}
            placeholder="INF00208"
          />
        </label>
        <label className={styles.champ}>
          <span>N° de série</span>
          <input
            value={v.numero_serie ?? ''}
            onChange={(e) => setV({ ...v, numero_serie: e.target.value })}
            placeholder="Constructeur"
          />
        </label>
      </div>

      <label className={styles.champ}>
        <span>Modèle</span>
        <input
          value={v.modele ?? ''}
          onChange={(e) => setV({ ...v, modele: e.target.value })}
          placeholder="Ex. Latitude 5540"
        />
      </label>

      {/* Emplacement et département se créent à la volée, comme les catégories : on ne quitte
          pas la saisie pour aller déclarer une agence. */}
      <div className={styles.champ}>
        <span>Emplacement</span>
        <SelecteurCategorie
          categories={emplacements}
          valeur={v.emplacement_id ?? null}
          onChange={(x) => setV({ ...v, emplacement_id: x })}
          gerable={gerable}
          entite="emplacement"
          onAjouter={(libelle) => inventaireApi.ajouterReferentiel('emplacements', libelle)}
          onModifie={onReferentiels}
        />
      </div>
      <div className={styles.champ}>
        <span>Département</span>
        <SelecteurCategorie
          categories={departements}
          valeur={v.departement_id ?? null}
          onChange={(x) => setV({ ...v, departement_id: x })}
          gerable={gerable}
          entite="département"
          onAjouter={(libelle) => inventaireApi.ajouterReferentiel('departements', libelle)}
          onModifie={onReferentiels}
        />
      </div>

      {/* Bloc comptable : c'est lui qui donne la valeur nette. Facultatif à la saisie. */}
      <div className={local.paire}>
        <div className={styles.champ}>
          <span>Date d'acquisition</span>
          <SelecteurDate
            valeur={v.date_acquisition ?? null}
            onChange={(d) => setV({ ...v, date_acquisition: d })}
            placeholder="jj/mm/aaaa"
          />
        </div>
        <label className={styles.champ}>
          <span>Valeur d'acquisition (FCFA)</span>
          <input
            value={v.valeur_acquisition?.toLocaleString('fr-FR') ?? ''}
            onChange={(e) => setV({ ...v, valeur_acquisition: nombre(e.target.value) })}
            placeholder="0"
          />
        </label>
      </div>

      <div className={local.paire}>
        <label className={styles.champ}>
          <span>Taux d'amortissement (%)</span>
          <input
            value={v.taux ?? ''}
            onChange={(e) => setV({ ...v, taux: nombre(e.target.value) })}
            placeholder="25"
          />
        </label>
        <label className={styles.champ}>
          <span>Durée (années)</span>
          <input
            value={v.duree_annees ?? ''}
            onChange={(e) => setV({ ...v, duree_annees: nombre(e.target.value) })}
            placeholder="4"
          />
        </label>
      </div>
    </Modale>
  );
}
