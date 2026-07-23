import { useEffect, useState } from 'react';
import { Check, UserPlus, X } from 'lucide-react';
import { SelecteurListe } from '@/common/SelecteurListe';
import type { Agent } from '@/common/agentsApi';
import local from './Inventaire.module.css';

interface Props {
  agents: Agent[];
  detenteurId: string | null;
  detenteurExterne: string | null;
  /** Un seul des deux est renseigné : l'autre est effacé par le serveur comme par l'écran. */
  onCompte: (id: string | null) => void;
  onExterne: (nom: string | null) => void;
  desactive?: boolean;
  titreDesactive?: string | undefined;
}

/** Détenteur d'un équipement : un compte de l'annuaire, ou un nom libre.
 *
 *  Tout le matériel n'est pas détenu par un agent de la DSI — un GAB l'est par une agence, un
 *  poste par un prestataire. Sans ce second chemin, ces matériels restaient « non attribués »
 *  et le parc paraissait moins suivi qu'il ne l'est.
 */
export function ChampDetenteur({
  agents,
  detenteurId,
  detenteurExterne,
  onCompte,
  onExterne,
  desactive = false,
  titreDesactive,
}: Props): JSX.Element {
  const [saisie, setSaisie] = useState(false);
  const [nom, setNom] = useState(detenteurExterne ?? '');
  useEffect(() => setNom(detenteurExterne ?? ''), [detenteurExterne]);

  const valider = (): void => {
    const propre = nom.trim();
    setSaisie(false);
    if (propre !== (detenteurExterne ?? '')) onExterne(propre === '' ? null : propre);
  };

  if (saisie) {
    return (
      <span className={local.detenteurSaisie}>
        <input
          autoFocus
          className={local.detenteurInput}
          value={nom}
          placeholder="Nom du détenteur (agence, prestataire…)"
          onChange={(e) => setNom(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') valider();
            if (e.key === 'Escape') {
              setNom(detenteurExterne ?? '');
              setSaisie(false);
            }
          }}
        />
        <button type="button" className={local.detenteurOk} onClick={valider} aria-label="Valider">
          <Check size={14} />
        </button>
        <button
          type="button"
          className={local.detenteurAnnuler}
          onClick={() => {
            setNom(detenteurExterne ?? '');
            setSaisie(false);
          }}
          aria-label="Annuler"
        >
          <X size={14} />
        </button>
      </span>
    );
  }

  return (
    <span className={local.detenteur}>
      {/* Le nom libre se saisit depuis la liste elle-même : le geste vit là où l'on cherche
          un détenteur, plutôt qu'à côté du champ où il faut penser à le trouver. */}
      <SelecteurListe
        options={agents.map((a) => ({ valeur: a.id, libelle: a.nom }))}
        valeur={detenteurId}
        onChange={onCompte}
        placeholder={detenteurExterne ?? 'Non attribué'}
        permettreVide
        libelleVide="Non attribué"
        indiceReaffectation="Réassigner"
        desactive={desactive}
        titreDesactive={titreDesactive}
        {...(desactive
          ? {}
          : {
              action: {
                libelle:
                  detenteurExterne !== null
                    ? 'Modifier le détenteur hors système…'
                    : 'Détenteur hors système (agence, prestataire)…',
                icone: UserPlus,
                onClick: () => setSaisie(true),
              },
            })}
      />
    </span>
  );
}
