// Petit carillon de notification, synthétisé à la volée (aucun fichier, aucune requête réseau).
// Deux notes brèves et douces — présent sans être strident, jamais répété en boucle.
//
// Les navigateurs interdisent de produire du son tant que l'utilisateur n'a pas interagi avec la
// page : un AudioContext créé hors geste naît « suspended », et resume() est alors refusé sans
// erreur. C'est pourquoi il faut le débloquer explicitement au premier clic (cf. `armerSonNotif`)
// — sans quoi le carillon reste inaudible pour toujours, silencieusement.

let ctx: AudioContext | null = null;

type AudioCtor = typeof AudioContext;

function creerContexte(): AudioContext | null {
  if (ctx !== null) return ctx;
  const Ctor: AudioCtor | undefined =
    window.AudioContext ??
    (window as unknown as { webkitAudioContext?: AudioCtor }).webkitAudioContext;
  if (Ctor === undefined) return null;
  try {
    ctx = new Ctor();
  } catch {
    return null;
  }
  return ctx;
}

/**
 * Débloque l'audio au tout premier geste de l'utilisateur (clic ou touche).
 *
 * À appeler une seule fois au démarrage. Sans cela, le navigateur garde le contexte suspendu et
 * aucune notification ne s'entend — c'était le cas jusqu'ici.
 */
export function armerSonNotif(): () => void {
  const debloquer = (): void => {
    const c = creerContexte();
    if (c !== null && c.state === 'suspended') void c.resume().catch(() => undefined);
    retirer();
  };
  const retirer = (): void => {
    window.removeEventListener('pointerdown', debloquer);
    window.removeEventListener('keydown', debloquer);
  };
  window.addEventListener('pointerdown', debloquer);
  window.addEventListener('keydown', debloquer);
  return retirer;
}

/** Planifie les deux notes à partir de l'instant courant du contexte (donc jamais dans le passé). */
function planifier(c: AudioContext): void {
  const base = c.currentTime;
  // La (A5) puis Ré (D6) : un intervalle montant, discret et chaleureux.
  const notes: Array<[number, number]> = [
    [880, 0],
    [1174.66, 0.09],
  ];
  for (const [freq, retard] of notes) {
    const osc = c.createOscillator();
    const gain = c.createGain();
    const t = base + retard;
    osc.type = 'sine';
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0.0001, t);
    gain.gain.exponentialRampToValueAtTime(0.14, t + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.28);
    osc.connect(gain).connect(c.destination);
    osc.start(t);
    osc.stop(t + 0.3);
  }
}

/** Joue un bref carillon à deux notes. Silencieux si l'audio n'est pas disponible ou pas débloqué. */
export function jouerSonNotif(): void {
  try {
    const c = creerContexte();
    if (c === null) return;
    if (c.state === 'suspended') {
      // Le contexte peut avoir été débloqué entre-temps : on retente, et on ne planifie les notes
      // qu'une fois la reprise effective — sinon elles tomberaient sur une horloge encore figée.
      void c
        .resume()
        .then(() => planifier(c))
        .catch(() => undefined);
      return;
    }
    planifier(c);
  } catch {
    /* audio indisponible : on reste silencieux. */
  }
}
