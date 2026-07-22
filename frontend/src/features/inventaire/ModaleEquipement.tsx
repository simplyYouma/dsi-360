import { useState } from 'react';
import { Button, Modale } from '@/design-system/primitives';
import { SelecteurListe } from '@/common/SelecteurListe';
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

      <div className={local.paire}>
        <div className={styles.champ}>
          <span>Emplacement</span>
          <SelecteurListe
            options={emplacements.map((e) => ({ valeur: e.id, libelle: e.libelle }))}
            valeur={v.emplacement_id ?? null}
            onChange={(x) => setV({ ...v, emplacement_id: x })}
            placeholder="Non renseigné"
            permettreVide
            libelleVide="Non renseigné"
          />
        </div>
        <div className={styles.champ}>
          <span>Département</span>
          <SelecteurListe
            options={departements.map((d) => ({ valeur: d.id, libelle: d.libelle }))}
            valeur={v.departement_id ?? null}
            onChange={(x) => setV({ ...v, departement_id: x })}
            placeholder="Non renseigné"
            permettreVide
            libelleVide="Non renseigné"
          />
        </div>
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
