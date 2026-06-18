import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, CornerDownLeft } from 'lucide-react';
import { api } from '@/lib/api';
import { BadgeStatut } from '@/common/statuts';
import { LIBELLE_MODULE, lienActivite } from '@/common/routesModule';
import styles from './RechercheGlobale.module.css';

interface Resultat {
  module: string;
  id: string;
  reference: string;
  titre: string;
  statut: string;
}

/**
 * Recherche globale de la topbar : interroge /recherche (référence ou titre, cloisonné côté
 * API), avec anti-rebond, navigation clavier et lien profond ouvrant directement la fiche.
 */
export function RechercheGlobale(): JSX.Element {
  const navigate = useNavigate();
  const [q, setQ] = useState('');
  const [resultats, setResultats] = useState<Resultat[]>([]);
  const [ouvert, setOuvert] = useState(false);
  const [actif, setActif] = useState(0);
  const [chargement, setChargement] = useState(false);
  const conteneur = useRef<HTMLDivElement>(null);

  // Anti-rebond 220 ms ; on ignore la réponse d'une requête devenue obsolète.
  useEffect(() => {
    const terme = q.trim();
    if (terme.length === 0) {
      setResultats([]);
      setOuvert(false);
      return;
    }
    let annule = false;
    setChargement(true);
    const minuteur = setTimeout(() => {
      api
        .get<Resultat[]>(`/recherche?q=${encodeURIComponent(terme)}`)
        .then((d) => {
          if (annule) return;
          setResultats(d);
          setActif(0);
          setOuvert(true);
        })
        .catch(() => {
          if (!annule) setResultats([]);
        })
        .finally(() => {
          if (!annule) setChargement(false);
        });
    }, 220);
    return () => {
      annule = true;
      clearTimeout(minuteur);
    };
  }, [q]);

  // Fermeture au clic en dehors du composant.
  useEffect(() => {
    const surClic = (e: MouseEvent): void => {
      if (conteneur.current && !conteneur.current.contains(e.target as Node)) setOuvert(false);
    };
    document.addEventListener('mousedown', surClic);
    return () => document.removeEventListener('mousedown', surClic);
  }, []);

  const aller = (r: Resultat): void => {
    const lien = lienActivite(r.module, r.id);
    if (lien === null) return;
    setOuvert(false);
    setQ('');
    setResultats([]);
    navigate(lien);
  };

  const surTouche = (e: KeyboardEvent<HTMLInputElement>): void => {
    if (e.key === 'Escape') {
      setOuvert(false);
      return;
    }
    if (!ouvert || resultats.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActif((i) => Math.min(i + 1, resultats.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActif((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const r = resultats[actif];
      if (r) aller(r);
    }
  };

  return (
    <div className={styles.conteneur} ref={conteneur}>
      <label className={styles.champ}>
        <Search size={18} />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onFocus={() => {
            if (resultats.length > 0) setOuvert(true);
          }}
          onKeyDown={surTouche}
          placeholder="Rechercher une activité, une référence…"
          aria-label="Recherche globale"
        />
      </label>

      {ouvert && (
        <div className={styles.panneau}>
          {resultats.length === 0 ? (
            <div className={styles.vide}>{chargement ? 'Recherche…' : 'Aucun résultat.'}</div>
          ) : (
            <ul className={styles.liste}>
              {resultats.map((r, i) => (
                <li key={`${r.module}-${r.id}`}>
                  <button
                    type="button"
                    className={i === actif ? styles.itemActif : styles.item}
                    onMouseEnter={() => setActif(i)}
                    onClick={() => aller(r)}
                  >
                    <span className={styles.ref}>{r.reference}</span>
                    <span className={styles.titre}>{r.titre}</span>
                    <span className={styles.meta}>
                      <span className={styles.module}>{LIBELLE_MODULE[r.module] ?? r.module}</span>
                      <BadgeStatut statut={r.statut} />
                    </span>
                    {i === actif && <CornerDownLeft size={14} className={styles.entree} />}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
