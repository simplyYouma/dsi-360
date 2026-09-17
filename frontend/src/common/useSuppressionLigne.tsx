import { useState, type ReactNode } from 'react';
import { useToast, type SuppressionTable } from '@/design-system/primitives';
import { ModaleConfirmation } from '@/common/ModaleConfirmation';
import { api, ErreurApi } from '@/lib/api';
import { useAuth } from '@/lib/auth';

/** Le profil qui administre. Le serveur porte la même constante et refuse de toute façon les
 *  autres : l'écran ne fait que ne pas proposer un geste qui serait rejeté. */
const PROFIL_ADMIN = 'ADMIN';

interface Options<T> {
  /** Base REST du module — « /incidents », « /eod », « /inventaire »… */
  base: string;
  id: (ligne: T) => string;
  /** Ce que la confirmation nomme : « INC-2026-00042 », « EOD du 15/09/2026 ». */
  libelle: (ligne: T) => string;
  /** Recharger la liste : la ligne effacée doit disparaître sans que l'on rafraîchisse la page. */
  onSupprime: () => void;
}

interface Resultat<T> {
  /** À passer au `Table`. `undefined` pour qui n'administre pas : pas de colonne, pas de place
   *  perdue, et surtout aucun bouton qui promettrait un geste refusé par le serveur. */
  suppression: SuppressionTable<T> | undefined;
  /** À rendre dans la page — la confirmation vit hors du tableau. */
  modaleSuppression: ReactNode;
}

/**
 * La suppression d'une ligne de liste, partout pareille.
 *
 * Trois choses lui donnent son poids, et elles sont ici plutôt que recopiées dans neuf pages :
 *
 * 1. **Réservée à l'administrateur.** Le serveur le garantit (403) ; l'écran se contente de ne
 *    pas proposer ce qu'il refuserait — un bouton qui échoue toujours vaut moins que pas de bouton.
 * 2. **Confirmée, et la confirmation NOMME la ligne.** « Supprimer cet élément ? » fait cliquer
 *    sans regarder ; « Supprimer INC-2026-00042 ? » fait relire.
 * 3. **Définitive, et l'écran le dit — en une phrase.** Ce qui part ne revient pas, seul le
 *    journal d'audit en garde la trace. Un paragraphe d'explications se saute dès la deuxième
 *    fois : ce qui doit être lu tient en une ligne.
 */
export function useSuppressionLigne<T>({ base, id, libelle, onSupprime }: Options<T>): Resultat<T> {
  const { moi } = useAuth();
  const { notifier } = useToast();
  const [cible, setCible] = useState<T | null>(null);

  const administre = moi?.profil === PROFIL_ADMIN;

  const supprimer = async (ligne: T): Promise<void> => {
    try {
      await api.del(`${base}/${id(ligne)}`);
      notifier(`${libelle(ligne)} a été supprimé.`, 'succes');
      onSupprime();
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : 'La suppression a échoué.', 'erreur');
    }
  };

  return {
    suppression: administre
      ? { onSupprimer: setCible, titre: (ligne) => `Supprimer ${libelle(ligne)}` }
      : undefined,
    modaleSuppression: (
      <ModaleConfirmation
        demande={
          cible === null
            ? null
            : {
                titre: `Supprimer ${libelle(cible)}`,
                // Court, parce qu'on le relit à chaque suppression : le titre nomme la fiche, la
                // phrase dit ce qui compte — c'est définitif, et l'audit en garde la trace. Le
                // reste (ce qui part avec elle, comment arrêter un dossier sans l'effacer) est du
                // cours, pas une information de décision.
                message: 'Suppression définitive. Seul le journal d’audit en gardera la trace.',
                libelleConfirmer: 'Supprimer définitivement',
                variante: 'danger',
                action: () => supprimer(cible),
              }
        }
        onFermer={() => setCible(null)}
      />
    ),
  };
}
