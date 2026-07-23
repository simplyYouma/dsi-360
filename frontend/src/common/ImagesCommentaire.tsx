import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { commentairesApi, type ImageCommentaire } from '@/common/commentairesApi';
import styles from './ImagesCommentaire.module.css';

interface Props {
  commentaireId: number;
  images: ImageCommentaire[];
}

/** Miniatures des images d'un message ; clic = visionneuse plein écran.
 *  Les octets passent par le jeton (URL protégée) : on charge en blob, jamais en `src` nu. */
export function ImagesCommentaire({ commentaireId, images }: Props): JSX.Element | null {
  const [urls, setUrls] = useState<Record<string, string>>({});
  const [agrandie, setAgrandie] = useState<ImageCommentaire | null>(null);

  // Dépendance sur les identifiants, pas sur le tableau : celui-ci change d'identité à chaque
  // rendu du parent. L'effet se rejouait alors sans cesse et le nettoyage révoquait les URL
  // encore affichées — d'où des images brisées quelques instants après leur apparition.
  const cle = images.map((i) => i.id).join(',');

  useEffect(() => {
    if (images.length === 0) return;
    let vivant = true;
    const crees: string[] = [];
    void Promise.all(
      images.map(async (img) => {
        const blob = await commentairesApi.image(commentaireId, img.id);
        return [img.id, URL.createObjectURL(blob)] as const;
      }),
    )
      .then((paires) => {
        if (!vivant) {
          paires.forEach(([, url]) => URL.revokeObjectURL(url));
          return;
        }
        paires.forEach(([, url]) => crees.push(url));
        setUrls(Object.fromEntries(paires));
      })
      // Une image illisible ne doit pas laisser un cadre brisé : la vignette reste en attente.
      .catch(() => undefined);
    return () => {
      vivant = false;
      crees.forEach((url) => URL.revokeObjectURL(url));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `cle` résume `images` de façon stable
  }, [commentaireId, cle]);

  useEffect(() => {
    if (agrandie === null) return;
    const surTouche = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') {
        e.stopPropagation(); // ne referme pas la fiche derrière
        setAgrandie(null);
      }
    };
    document.addEventListener('keydown', surTouche, true);
    return () => document.removeEventListener('keydown', surTouche, true);
  }, [agrandie]);

  if (images.length === 0) return null;

  return (
    <>
      <div className={styles.grille}>
        {images.map((img) => (
          <button
            key={img.id}
            type="button"
            className={styles.vignette}
            onClick={() => setAgrandie(img)}
            title={img.nom}
            aria-label={`Agrandir ${img.nom}`}
          >
            {urls[img.id] !== undefined ? (
              <img src={urls[img.id]} alt={img.nom} />
            ) : (
              <span className={styles.chargement} aria-hidden="true" />
            )}
          </button>
        ))}
      </div>

      {agrandie !== null &&
        urls[agrandie.id] !== undefined &&
        createPortal(
          <div
            className={styles.visionneuse}
            onMouseDown={() => setAgrandie(null)}
            role="dialog"
            aria-label={agrandie.nom}
          >
            <button
              type="button"
              className={styles.fermer}
              onClick={() => setAgrandie(null)}
              aria-label="Fermer"
            >
              <X size={20} />
            </button>
            <img
              src={urls[agrandie.id]}
              alt={agrandie.nom}
              onMouseDown={(e) => e.stopPropagation()}
            />
          </div>,
          document.body,
        )}
    </>
  );
}
