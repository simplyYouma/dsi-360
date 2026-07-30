/**
 * Préparation des logos pour les dossiers de présentation.
 *
 * Les cinq logos ne se ressemblent pas : YUMIAM est noir sur fond blanc
 * OPAQUE, The-Tailor est blanc sur transparent, GlowUp est en couleur.
 * Posés tels quels dans une maquette, ils donnent respectivement un carré
 * blanc sur le papier crème, un logo invisible sur page claire, et un logo
 * illisible sur page sombre.
 *
 * D'où ce module : il décode le PNG, détoure le fond blanc, recadre sur la
 * boîte englobante réelle (les fichiers ont 25 à 40 % de marge vide, ce qui
 * rapetissait le logo d'autant), et sait produire une variante recolorée
 * pour les pages sombres quand le logo est monochrome.
 *
 * Zéro dépendance : zlib suffit à lire et réécrire un PNG.
 */
import { readFileSync } from "node:fs";
import { inflateSync, deflateSync } from "node:zlib";

const SIG = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

// ── Décodage ────────────────────────────────────────────────────────────

function chunks(buf) {
    if (!buf.subarray(0, 8).equals(SIG)) throw new Error("PNG attendu");
    const out = [];
    let p = 8;
    while (p < buf.length) {
        const len = buf.readUInt32BE(p);
        const type = buf.toString("ascii", p + 4, p + 8);
        out.push({ type, data: buf.subarray(p + 8, p + 8 + len) });
        p += 12 + len; // longueur + type + données + CRC
    }
    return out;
}

/** Reconstruit les lignes brutes : chaque scanline porte son filtre PNG. */
function unfilter(raw, width, height, bpp) {
    const stride = width * bpp;
    const out = Buffer.alloc(height * stride);
    let p = 0;
    for (let y = 0; y < height; y++) {
        const filter = raw[p++];
        const line = raw.subarray(p, p + stride);
        p += stride;
        const cur = out.subarray(y * stride, (y + 1) * stride);
        const prev = y > 0 ? out.subarray((y - 1) * stride, y * stride) : null;
        for (let x = 0; x < stride; x++) {
            const a = x >= bpp ? cur[x - bpp] : 0;
            const b = prev ? prev[x] : 0;
            const c = prev && x >= bpp ? prev[x - bpp] : 0;
            let v = line[x];
            switch (filter) {
                case 1: v += a; break;
                case 2: v += b; break;
                case 3: v += (a + b) >> 1; break;
                case 4: {
                    const pa = Math.abs(b - c), pb = Math.abs(a - c), pc = Math.abs(a + b - 2 * c);
                    v += pa <= pb && pa <= pc ? a : pb <= pc ? b : c;
                    break;
                }
            }
            cur[x] = v & 0xff;
        }
    }
    return out;
}

/**
 * PNG → {width, height, px:RGBA}. Profondeur 8 bits uniquement (suffit ici).
 * Accepte un chemin ou un Buffer déjà en mémoire — les logos SVG sont
 * rasterisés avant d'entrer ici et n'ont pas de fichier sur le disque.
 */
export function decodePng(source) {
    const cs = chunks(Buffer.isBuffer(source) ? source : readFileSync(source));
    const ihdr = cs.find((c) => c.type === "IHDR").data;
    const width = ihdr.readUInt32BE(0), height = ihdr.readUInt32BE(4);
    const depth = ihdr[8], colorType = ihdr[9], interlace = ihdr[12];
    if (depth !== 8) throw new Error(`Profondeur ${depth} bits non gérée`);
    if (interlace) throw new Error("PNG entrelacé non géré");

    const channels = { 0: 1, 2: 3, 3: 1, 4: 2, 6: 4 }[colorType];
    const idat = inflateSync(Buffer.concat(cs.filter((c) => c.type === "IDAT").map((c) => c.data)));
    const flat = unfilter(idat, width, height, channels);

    const plte = cs.find((c) => c.type === "PLTE")?.data;
    const trns = cs.find((c) => c.type === "tRNS")?.data;

    const px = Buffer.alloc(width * height * 4);
    for (let i = 0; i < width * height; i++) {
        const s = i * channels, d = i * 4;
        let r, g, b, a = 255;
        switch (colorType) {
            case 0: r = g = b = flat[s]; break;
            case 2: r = flat[s]; g = flat[s + 1]; b = flat[s + 2]; break;
            case 3: {
                const k = flat[s];
                r = plte[k * 3]; g = plte[k * 3 + 1]; b = plte[k * 3 + 2];
                if (trns && k < trns.length) a = trns[k];
                break;
            }
            case 4: r = g = b = flat[s]; a = flat[s + 1]; break;
            case 6: r = flat[s]; g = flat[s + 1]; b = flat[s + 2]; a = flat[s + 3]; break;
        }
        px[d] = r; px[d + 1] = g; px[d + 2] = b; px[d + 3] = a;
    }
    return { width, height, px };
}

// ── Encodage ────────────────────────────────────────────────────────────

function crc32(buf) {
    let c = ~0;
    for (let i = 0; i < buf.length; i++) {
        c ^= buf[i];
        for (let k = 0; k < 8; k++) c = (c >>> 1) ^ (0xedb88320 & -(c & 1));
    }
    return ~c >>> 0;
}

function chunk(type, data) {
    const head = Buffer.alloc(8);
    head.writeUInt32BE(data.length, 0);
    head.write(type, 4, "ascii");
    const crc = Buffer.alloc(4);
    crc.writeUInt32BE(crc32(Buffer.concat([head.subarray(4), data])), 0);
    return Buffer.concat([head, data, crc]);
}

/** {width,height,px} → PNG RGBA (filtre 0 : la compression fait le reste). */
export function encodePng({ width, height, px }) {
    const raw = Buffer.alloc(height * (1 + width * 4));
    for (let y = 0; y < height; y++) {
        raw[y * (1 + width * 4)] = 0;
        px.copy(raw, y * (1 + width * 4) + 1, y * width * 4, (y + 1) * width * 4);
    }
    const ihdr = Buffer.alloc(13);
    ihdr.writeUInt32BE(width, 0); ihdr.writeUInt32BE(height, 4);
    ihdr[8] = 8; ihdr[9] = 6; // 8 bits, RGBA
    return Buffer.concat([
        SIG,
        chunk("IHDR", ihdr),
        chunk("IDAT", deflateSync(raw, { level: 9 })),
        chunk("IEND", Buffer.alloc(0)),
    ]);
}

// ── Traitements ─────────────────────────────────────────────────────────

/**
 * Le fichier a-t-il déjà un fond transparent ?
 *
 * Question vitale avant de détourer : un logo BLANC sur fond transparent
 * (The Tailor) serait intégralement effacé par un détourage du blanc. On
 * regarde les quatre coins — le fond, s'il y en a un, y est forcément.
 */
export function dejaDetoure(img) {
    const { width: w, height: h, px } = img;
    const coins = [[0, 0], [w - 1, 0], [0, h - 1], [w - 1, h - 1]];
    return coins.some(([x, y]) => px[(y * w + x) * 4 + 3] < 8);
}

/**
 * Détoure le fond clair — sauf si le fichier est déjà détouré, auquel cas on
 * n'y touche pas. Le seuil est doux (240) et l'alpha progressif entre 240 et
 * 255 : un détourage binaire crènerait les bords antialiasés du logo.
 */
export function detourer(img, seuil = 240) {
    if (dejaDetoure(img)) return img;
    const { width, height, px } = img;
    const out = Buffer.from(px);
    for (let i = 0; i < width * height; i++) {
        const d = i * 4;
        if (out[d + 3] === 0) continue;
        const min = Math.min(out[d], out[d + 1], out[d + 2]);
        if (min >= 255) out[d + 3] = 0;
        else if (min > seuil) out[d + 3] = Math.round(out[d + 3] * (255 - min) / (255 - seuil));
    }
    return { width, height, px: out };
}

/** Recadre sur les pixels visibles + une marge d'air proportionnelle. */
export function recadrer(img, airPct = 0) {
    const { width, height, px } = img;
    let x0 = width, y0 = height, x1 = -1, y1 = -1;
    for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
            if (px[(y * width + x) * 4 + 3] > 8) {
                if (x < x0) x0 = x; if (x > x1) x1 = x;
                if (y < y0) y0 = y; if (y > y1) y1 = y;
            }
        }
    }
    if (x1 < 0) return img; // entièrement transparent : on n'y touche pas
    const air = Math.round(Math.max(x1 - x0, y1 - y0) * airPct);
    x0 = Math.max(0, x0 - air); y0 = Math.max(0, y0 - air);
    x1 = Math.min(width - 1, x1 + air); y1 = Math.min(height - 1, y1 + air);

    const w = x1 - x0 + 1, h = y1 - y0 + 1;
    const out = Buffer.alloc(w * h * 4);
    for (let y = 0; y < h; y++) {
        px.copy(out, y * w * 4, ((y + y0) * width + x0) * 4, ((y + y0) * width + x1 + 1) * 4);
    }
    return { width: w, height: h, px: out };
}

/** Repeint le logo dans une couleur unie, en gardant sa silhouette (alpha). */
export function repeindre(img, hex) {
    const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
    const out = Buffer.from(img.px);
    for (let i = 0; i < img.width * img.height; i++) {
        const d = i * 4;
        if (out[d + 3] === 0) continue;
        out[d] = r; out[d + 1] = g; out[d + 2] = b;
    }
    return { ...img, px: out };
}

/** Vrai si le logo n'a qu'une teinte (→ il peut être repeint sans mentir). */
export function estMonochrome(img) {
    const { width, height, px } = img;
    for (let i = 0; i < width * height; i++) {
        const d = i * 4;
        if (px[d + 3] < 128) continue;
        const max = Math.max(px[d], px[d + 1], px[d + 2]);
        const min = Math.min(px[d], px[d + 1], px[d + 2]);
        if (max - min > 24) return false; // saturation réelle → logo en couleur
    }
    return true;
}

export const versDataUri = (img) => `data:image/png;base64,${encodePng(img).toString("base64")}`;
