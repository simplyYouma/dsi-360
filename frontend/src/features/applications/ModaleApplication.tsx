import { useEffect, useState } from 'react';
import { Boxes, Server, ShieldCheck, Users } from 'lucide-react';
import { Button, Modale } from '@/design-system/primitives';
import { SelecteurCategorie } from '@/common/SelecteurCategorie';
import { SelecteurListe } from '@/common/SelecteurListe';
import { SelecteurDate } from '@/common/SelecteurDate';
import { OPTIONS_PAYS } from '@/common/pays';
import { chargerAgents, type Agent } from '@/common/agentsApi';
import styles from '@/features/incidents/IncidentsPage.module.css';
import local from './Applications.module.css';
import { ChampResponsables } from './ChampResponsables';
import {
  applicationsApi,
  COULEUR_HEBERGEMENT,
  COULEUR_STATUT,
  HEBERGEMENTS,
  ICONE_HEBERGEMENT,
  ICONE_INTERFACAGE,
  ICONE_STATUT,
  INTERFACAGES,
  STATUTS,
  type ApplicationDetail,
  type NouvelleApplication,
  type ReferentielItem,
  type ResponsableApplication,
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

function versEntier(brut: string): number | null {
  const chiffres = brut.replace(/[^\d]/g, '');
  return chiffres === '' ? null : Number(chiffres);
}

/** Saisie d'une application. Seul le nom est exigé — tout le reste se complète au fil de l'eau.
 *
 *  Les mêmes champs qu'à la fiche, et dans le même ordre : ce qu'on peut corriger plus tard, on
 *  doit pouvoir le dire tout de suite. Un formulaire d'ajout plus pauvre que l'écran de détail
 *  oblige à créer puis rouvrir pour finir — deux gestes pour une seule intention.
 */
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
  const [admins, setAdmins] = useState<ResponsableApplication[]>([]);
  const [secours, setSecours] = useState<ResponsableApplication[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [envoi, setEnvoi] = useState(false);

  useEffect(() => {
    void chargerAgents().then(setAgents);
  }, []);

  const creer = async (): Promise<void> => {
    setEnvoi(true);
    try {
      const cree = await applicationsApi.creer({
        ...v,
        administrateurs: admins.map((p) =>
          p.utilisateur_id !== null ? { utilisateur_id: p.utilisateur_id } : { nom: p.nom },
        ),
        administrateurs_secours: secours.map((p) =>
          p.utilisateur_id !== null ? { utilisateur_id: p.utilisateur_id } : { nom: p.nom },
        ),
      });
      setV(VIDE);
      setAdmins([]);
      setSecours([]);
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
      largeur={760}
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
      {/* --- Ce que c'est ------------------------------------------------------------------ */}
      <section className={local.section}>
        <span className={local.sectionTitre}>
          <Boxes size={13} /> L’application
        </span>

        <label className={styles.champ}>
          <span>Nom</span>
          <input
            value={v.nom}
            onChange={(e) => setV({ ...v, nom: e.target.value })}
            placeholder="Ex. AFG E-bank (OBDX)"
            autoFocus
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
            placeholder="Ce que l’application permet de faire"
          />
        </label>

        <div className={local.trio}>
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
              icones={ICONE_STATUT}
            />
          </div>
        </div>
      </section>

      {/* --- Qui en répond ------------------------------------------------------------------ */}
      <section className={local.section}>
        <span className={local.sectionTitre}>
          <Users size={13} /> Qui en répond
        </span>

        <div className={styles.champ}>
          <span>Administrateurs</span>
          <ChampResponsables
            valeur={admins}
            agents={agents}
            onChange={setAdmins}
            indication="ou saisir un nom (prestataire, support…)"
          />
        </div>
        <div className={styles.champ}>
          <span>Administrateurs de secours</span>
          <ChampResponsables
            valeur={secours}
            agents={agents}
            onChange={setSecours}
            indication="le relais, s’il existe"
          />
        </div>
        <label className={styles.champ}>
          <span>Propriétaire métier</span>
          <input
            value={v.proprietaire ?? ''}
            onChange={(e) => setV({ ...v, proprietaire: e.target.value })}
            placeholder="Le service qui en a l’usage"
          />
        </label>
      </section>

      {/* --- Où ça tourne ------------------------------------------------------------------- */}
      <section className={local.section}>
        <span className={local.sectionTitre}>
          <ShieldCheck size={13} /> Hébergement &amp; données
        </span>

        <div className={local.trio}>
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
              icones={ICONE_HEBERGEMENT}
            />
          </div>
          <div className={styles.champ}>
            <span>Pays des données</span>
            <SelecteurListe
              options={OPTIONS_PAYS}
              valeur={v.pays_donnees ?? null}
              onChange={(x) => setV({ ...v, pays_donnees: x })}
              placeholder="Non renseigné"
              permettreVide
              libelleVide="Non renseigné"
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
              icones={ICONE_INTERFACAGE}
            />
          </div>
        </div>

        <div className={local.trio}>
          <div className={styles.champ}>
            <span>Mise en service</span>
            <SelecteurDate
              valeur={v.date_debut ?? null}
              onChange={(d) => setV({ ...v, date_debut: d })}
              placeholder="jj/mm/aaaa"
            />
          </div>
          <div className={styles.champ}>
            <span>Fin de service</span>
            <SelecteurDate
              valeur={v.date_fin ?? null}
              onChange={(d) => setV({ ...v, date_fin: d })}
              placeholder="jj/mm/aaaa"
            />
          </div>
          <label className={styles.champ}>
            <span>Comptes actifs</span>
            <input
              value={v.nb_comptes_actifs ?? ''}
              inputMode="numeric"
              onChange={(e) => setV({ ...v, nb_comptes_actifs: versEntier(e.target.value) })}
              placeholder="0"
            />
          </label>
        </div>
      </section>

      {/* --- Comment on y accède ------------------------------------------------------------ */}
      <section className={local.section}>
        <span className={local.sectionTitre}>
          <Server size={13} /> Accès &amp; serveurs
        </span>

        <label className={styles.champ}>
          <span>Lien d’accès</span>
          <input
            value={v.lien ?? ''}
            onChange={(e) => setV({ ...v, lien: e.target.value })}
            placeholder="https://…"
          />
        </label>

        <div className={local.trio}>
          <label className={styles.champ}>
            <span>Serveur d’application</span>
            <input
              value={v.serveur_application ?? ''}
              onChange={(e) => setV({ ...v, serveur_application: e.target.value })}
              placeholder="Ex. SRV-APP-01"
            />
          </label>
          <label className={styles.champ}>
            <span>Serveur de base de données</span>
            <input
              value={v.serveur_base ?? ''}
              onChange={(e) => setV({ ...v, serveur_base: e.target.value })}
              placeholder="Ex. SRV-BDD-01"
            />
          </label>
          <label className={styles.champ}>
            <span>Port</span>
            <input
              value={v.port ?? ''}
              onChange={(e) => setV({ ...v, port: e.target.value })}
              placeholder="Ex. 8443"
            />
          </label>
        </div>
      </section>
    </Modale>
  );
}
