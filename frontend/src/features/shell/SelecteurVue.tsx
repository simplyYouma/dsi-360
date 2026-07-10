import { useEffect, useState } from 'react';
import { Eye, Undo2 } from 'lucide-react';
import { Button, Modale, useToast } from '@/design-system/primitives';
import { chargerAgents, type Agent } from '@/common/agentsApi';
import { ErreurApi } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import styles from './SelecteurVue.module.css';

/** Rappel permanent qu'on regarde l'application avec les yeux d'un autre, et sortie immédiate.
 *  Un tel dispositif ne doit jamais s'oublier. */
export function BandeauIncarnation(): JSX.Element | null {
  const { moi, redevenirSoi, incarnation } = useAuth();
  const [envoi, setEnvoi] = useState(false);

  if (!incarnation || moi === null) return null;

  const revenir = async (): Promise<void> => {
    setEnvoi(true);
    try {
      await redevenirSoi();
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <div className={styles.bandeau}>
      <Eye size={14} />
      <span>
        Vue de{' '}
        <strong>
          {moi.prenom} {moi.nom}
        </strong>
        <span className={styles.bandeauProfil}> — {moi.profil_libelle}</span>
      </span>
      <button
        type="button"
        className={styles.retour}
        onClick={() => void revenir()}
        disabled={envoi}
      >
        <Undo2 size={14} />
        Redevenir moi
      </button>
    </div>
  );
}

/** Éprouver l'application avec les yeux d'un autre profil — **développement seulement**.
 *
 *  Le serveur délivre un vrai jeton du compte choisi : on éprouve les gardes réelles, pas
 *  seulement l'affichage. Hors développement, l'endpoint n'existe pas (404) et cette icône ne
 *  s'affiche pas — l'environnement vient du serveur, jamais d'une supposition du navigateur. */
export function SelecteurVue(): JSX.Element | null {
  const { moi, incarner, incarnation } = useAuth();
  const { notifier } = useToast();
  const [ouvert, setOuvert] = useState(false);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [envoi, setEnvoi] = useState(false);

  useEffect(() => {
    if (ouvert && agents.length === 0) void chargerAgents().then(setAgents);
  }, [ouvert, agents.length]);

  // Pendant l'incarnation, c'est le bandeau qui prend le relais.
  if (moi === null || moi.environnement !== 'dev' || incarnation) return null;

  const choisir = async (id: string): Promise<void> => {
    setEnvoi(true);
    try {
      await incarner(id);
      setOuvert(false);
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'Incarnation impossible.', 'erreur');
    } finally {
      setEnvoi(false);
    }
  };

  // Groupé par profil : on cherche « ce que voit un Réseau télécom », pas un nom précis.
  const parProfil = new Map<string, Agent[]>();
  for (const a of agents) {
    const liste = parProfil.get(a.profil) ?? [];
    liste.push(a);
    parProfil.set(a.profil, liste);
  }

  return (
    <>
      <button
        type="button"
        className={styles.icone}
        onClick={() => setOuvert(true)}
        title="Voir l’application comme un autre profil (développement)"
        aria-label="Changer de vue"
      >
        <Eye size={18} />
      </button>

      <Modale
        ouverte={ouvert}
        onFermer={() => setOuvert(false)}
        titre="Voir comme…"
        pied={
          <Button variante="secondaire" onClick={() => setOuvert(false)}>
            Annuler
          </Button>
        }
      >
        <p className={styles.avertissement}>
          Le serveur vous répondra comme au compte choisi : vous éprouvez les gardes réelles, pas
          seulement l’affichage. Cet outil n’existe qu’en développement, et chaque usage est
          journalisé.
        </p>
        {[...parProfil.entries()].map(([profil, liste]) => (
          <section key={profil} className={styles.groupe}>
            <span className={styles.groupeTitre}>{profil}</span>
            <ul className={styles.comptes}>
              {liste.map((a) => (
                <li key={a.id}>
                  <button
                    type="button"
                    className={styles.compte}
                    onClick={() => void choisir(a.id)}
                    disabled={envoi || a.id === moi.id}
                  >
                    {a.nom}
                    {a.id === moi.id && <span className={styles.soi}>vous</span>}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}
        {agents.length === 0 && <p className={styles.avertissement}>Aucun compte à incarner.</p>}
      </Modale>
    </>
  );
}
