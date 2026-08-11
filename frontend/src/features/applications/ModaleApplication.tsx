import { useState } from 'react';
import { Button, Modale } from '@/design-system/primitives';
import { SelecteurCategorie } from '@/common/SelecteurCategorie';
import { SelecteurListe } from '@/common/SelecteurListe';
import styles from '@/features/incidents/IncidentsPage.module.css';
import local from '@/features/inventaire/Inventaire.module.css';
import {
  applicationsApi,
  COULEUR_HEBERGEMENT,
  COULEUR_STATUT,
  HEBERGEMENTS,
  INTERFACAGES,
  STATUTS,
  type ApplicationDetail,
  type NouvelleApplication,
  type ReferentielItem,
} from './applicationsApi';

interface Props {
  ouverte: boolean;
  /** L'administrateur peut créer un éditeur sans quitter la modale. */
  gerable: boolean;
  editeurs: ReferentielItem[];
  onEditeurs: () => void;
  onFermer: () => void;
  onCree: (cree: ApplicationDetail) => void;
  onErreur: (e: unknown) => void;
}

const VIDE: NouvelleApplication = { nom: '', statut: 'EN_SERVICE' };

/** Saisie d'une application. Seul le nom est exigé : le reste se complète au fil de l'eau. */
export function ModaleApplication({
  ouverte,
  gerable,
  editeurs,
  onEditeurs,
  onFermer,
  onCree,
  onErreur,
}: Props): JSX.Element {
  const [v, setV] = useState<NouvelleApplication>(VIDE);
  const [envoi, setEnvoi] = useState(false);

  const creer = async (): Promise<void> => {
    setEnvoi(true);
    try {
      const cree = await applicationsApi.creer(v);
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
      titre="Nouvelle application"
      pied={
        <>
          <Button variante="secondaire" onClick={onFermer}>
            Annuler
          </Button>
          <Button onClick={() => void creer()} disabled={envoi || v.nom.trim().length < 2}>
            {envoi ? 'Création…' : 'Créer'}
          </Button>
        </>
      }
    >
      <label className={styles.champ}>
        <span>Nom de l'application</span>
        <input
          value={v.nom}
          onChange={(e) => setV({ ...v, nom: e.target.value })}
          placeholder="Ex. AFG E-bank (OBDX)"
        />
      </label>

      <label className={styles.champ}>
        <span>Processus métier servi</span>
        <input
          value={v.processus_metier ?? ''}
          onChange={(e) => setV({ ...v, processus_metier: e.target.value })}
          placeholder="Ex. Banque mobile"
        />
      </label>

      <label className={styles.champ}>
        <span>Principales fonctionnalités</span>
        <textarea
          rows={3}
          value={v.fonctionnalites ?? ''}
          onChange={(e) => setV({ ...v, fonctionnalites: e.target.value })}
          placeholder="Ce que l'application permet de faire"
        />
      </label>

      {/* L'éditeur se crée à la volée, comme les catégories : on ne quitte pas la saisie pour
          aller déclarer un fournisseur. */}
      <div className={styles.champ}>
        <span>Éditeur</span>
        <SelecteurCategorie
          categories={editeurs}
          valeur={v.editeur_id ?? null}
          onChange={(x) => setV({ ...v, editeur_id: x })}
          gerable={gerable}
          accent="var(--cat-2)"
          entite="éditeur"
          onAjouter={(libelle) => applicationsApi.ajouterEditeur(libelle)}
          onSupprimer={(eid) => applicationsApi.supprimerEditeur(eid)}
          onModifie={onEditeurs}
        />
      </div>

      <div className={local.paire}>
        <label className={styles.champ}>
          <span>Version</span>
          <input
            value={v.version ?? ''}
            onChange={(e) => setV({ ...v, version: e.target.value })}
            placeholder="Ex. 12.4"
          />
        </label>
        <div className={styles.champ}>
          <span>Statut</span>
          <SelecteurListe
            options={STATUTS.map((s) => ({ valeur: s.valeur, libelle: s.libelle }))}
            valeur={v.statut ?? 'EN_SERVICE'}
            onChange={(x) => x !== null && setV({ ...v, statut: x })}
            couleurs={COULEUR_STATUT}
          />
        </div>
      </div>

      <div className={local.paire}>
        <div className={styles.champ}>
          <span>Hébergement</span>
          <SelecteurListe
            options={HEBERGEMENTS.map((h) => ({ valeur: h.valeur, libelle: h.libelle }))}
            valeur={v.hebergement ?? null}
            onChange={(x) => setV({ ...v, hebergement: x })}
            placeholder="Non renseigné"
            permettreVide
            libelleVide="Non renseigné"
            couleurs={COULEUR_HEBERGEMENT}
          />
        </div>
        <div className={styles.champ}>
          <span>Interfaçage</span>
          <SelecteurListe
            options={INTERFACAGES.map((i) => ({ valeur: i.valeur, libelle: i.libelle }))}
            valeur={v.interfacage ?? null}
            onChange={(x) => setV({ ...v, interfacage: x })}
            placeholder="Non renseigné"
            permettreVide
            libelleVide="Non renseigné"
          />
        </div>
      </div>

      {/* Qui en répond, dès la saisie : sans cela, toute application naît orpheline — et c'est
          précisément ce que l'inventaire cherche à éviter. */}
      <div className={local.paire}>
        <label className={styles.champ}>
          <span>Administrateur</span>
          <input
            value={v.administrateur ?? ''}
            onChange={(e) => setV({ ...v, administrateur: e.target.value })}
            placeholder="Nom, ou support du prestataire"
          />
        </label>
        <label className={styles.champ}>
          <span>Administrateur de secours</span>
          <input
            value={v.administrateur_secours ?? ''}
            onChange={(e) => setV({ ...v, administrateur_secours: e.target.value })}
            placeholder="Le relais, s'il existe"
          />
        </label>
      </div>
    </Modale>
  );
}
