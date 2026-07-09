import { useEffect, useRef, useState } from 'react';
import { ImagePlus, Send, X } from 'lucide-react';
import { Button } from '@/design-system/primitives';
import { ChampMention } from '@/common/ChampMention';
import type { AgentRef } from '@/common/useAgents';
import styles from './ComposeurDiscussion.module.css';

/** Nombre d'images maximum par message (aligné sur la limite du serveur). */
const MAX_IMAGES = 6;

interface Props {
  valeur: string;
  onChange: (v: string) => void;
  agents: AgentRef[];
  placeholder?: string;
  envoi: boolean;
  /** Envoie le message ; les images jointes sont passées telles quelles. */
  onEnvoyer: (images: File[]) => Promise<void>;
  className?: string | undefined;
}

/** Zone de rédaction d'un message : texte (@ mentions, Maj+Entrée = saut de ligne) et images
 *  jointes — collées au presse-papier (Ctrl+V) ou choisies — prévisualisées avant l'envoi. */
export function ComposeurDiscussion({
  valeur,
  onChange,
  agents,
  placeholder,
  envoi,
  onEnvoyer,
  className,
}: Props): JSX.Element {
  const [images, setImages] = useState<File[]>([]);
  const [apercus, setApercus] = useState<string[]>([]);
  const champFichier = useRef<HTMLInputElement>(null);

  // Aperçus locaux : révoqués dès que la liste change (aucune fuite d'objet URL).
  useEffect(() => {
    const urls = images.map((f) => URL.createObjectURL(f));
    setApercus(urls);
    return () => urls.forEach((u) => URL.revokeObjectURL(u));
  }, [images]);

  const ajouter = (fichiers: File[]): void => {
    const seulementImages = fichiers.filter((f) => f.type.startsWith('image/'));
    if (seulementImages.length === 0) return;
    setImages((liste) => [...liste, ...seulementImages].slice(0, MAX_IMAGES));
  };

  const vide = valeur.trim() === '' && images.length === 0;

  const envoyer = async (): Promise<void> => {
    if (vide || envoi) return;
    try {
      await onEnvoyer(images);
      setImages([]);
    } catch {
      // L'appelant a déjà signalé l'erreur : on conserve les images pour ne pas les perdre.
    }
  };

  return (
    <div className={styles.composeur}>
      {apercus.length > 0 && (
        <ul className={styles.apercus}>
          {apercus.map((url, i) => (
            <li key={url} className={styles.apercu}>
              <img src={url} alt={images[i]?.name ?? 'Image jointe'} />
              <button
                type="button"
                className={styles.retirer}
                onClick={() => setImages((liste) => liste.filter((_, j) => j !== i))}
                aria-label="Retirer l’image"
              >
                <X size={13} />
              </button>
            </li>
          ))}
        </ul>
      )}

      <ChampMention
        valeur={valeur}
        onChange={onChange}
        agents={agents}
        className={className}
        placeholder={placeholder}
        onEnvoyer={() => void envoyer()}
        onImagesCollees={ajouter}
      />

      <div className={styles.actions}>
        <button
          type="button"
          className={styles.joindre}
          onClick={() => champFichier.current?.click()}
          disabled={images.length >= MAX_IMAGES}
          title={
            images.length >= MAX_IMAGES
              ? `${MAX_IMAGES} images au maximum`
              : 'Joindre une image (ou collez une capture avec Ctrl+V)'
          }
          aria-label="Joindre une image"
        >
          <ImagePlus size={16} />
        </button>
        <input
          ref={champFichier}
          type="file"
          accept="image/png,image/jpeg,image/gif,image/webp"
          multiple
          hidden
          onChange={(e) => {
            ajouter([...(e.target.files ?? [])]);
            e.target.value = ''; // permet de re-choisir le même fichier
          }}
        />
        <span className={styles.aide}>Maj+Entrée pour un saut de ligne</span>
        <Button onClick={() => void envoyer()} disabled={envoi || vide}>
          <Send size={15} />
          {envoi ? 'Envoi…' : 'Commenter'}
        </Button>
      </div>
    </div>
  );
}
