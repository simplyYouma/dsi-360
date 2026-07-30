/**
 * Préparation des images de couverture.
 *
 * Les visuels de marque sont des fichiers d'application : 2 Mo pour le décor
 * BOUTIKII, 9 Mo pour une prestation Barber. Embarqués tels quels en base64
 * (+33 %), ils rendraient le dossier impossible à envoyer par mail.
 *
 * On les redimensionne donc à la taille réellement utile — une couverture A4
 * imprimée à 150 dpi n'a pas besoin de plus de ~1400 px de large — et on
 * choisit le format selon la nature de l'image :
 *   • photo opaque    → JPEG (compression adaptée aux dégradés continus) ;
 *   • sujet détouré   → PNG palettisé (l'alpha doit survivre).
 */
import sharp from "sharp";

/**
 * @param {string} fichier   chemin absolu
 * @param {object} opts      {largeur, qualite, transparent}
 * @returns {Promise<{uri:string, ko:number, w:number, h:number}>}
 */
export async function preparerImage(fichier, { largeur = 1400, qualite = 78, transparent = false } = {}) {
    const base = sharp(fichier).resize({ width: largeur, withoutEnlargement: true });
    const buf = transparent
        ? await base.png({ palette: true, quality: 82, compressionLevel: 9, effort: 8 }).toBuffer()
        : await base.jpeg({ quality: qualite, mozjpeg: true, chromaSubsampling: "4:2:0" }).toBuffer();

    const meta = await sharp(buf).metadata();
    return {
        uri: `data:image/${transparent ? "png" : "jpeg"};base64,${buf.toString("base64")}`,
        ko: Math.round((buf.length * 4) / 3 / 1024), // poids une fois en base64
        w: meta.width,
        h: meta.height,
    };
}

/** SVG → PNG RGBA en mémoire, à la résolution réellement utile au dossier. */
export async function rasteriser(fichier, largeur = 900) {
    return sharp(fichier, { density: 300 })
        .resize({ width: largeur, withoutEnlargement: true })
        .png()
        .toBuffer();
}
