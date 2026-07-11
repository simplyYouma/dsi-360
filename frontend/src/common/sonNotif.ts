// Petit carillon de notification, synthétisé à la volée (aucun fichier, aucune requête réseau).
// Deux notes brèves et douces — présent sans être strident, jamais répété en boucle.

let ctx: AudioContext | null = null;

type AudioCtor = typeof AudioContext;

/** Joue un bref carillon à deux notes. Silencieux si l'audio n'est pas disponible. */
export function jouerSonNotif(): void {
  try {
    const Ctor: AudioCtor | undefined =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext?: AudioCtor }).webkitAudioContext;
    if (Ctor === undefined) return;
    ctx ??= new Ctor();
    // Débloqué au premier geste de l'utilisateur ; avant cela, le navigateur suspend l'audio.
    if (ctx.state === 'suspended') void ctx.resume();

    const base = ctx.currentTime;
    // La (A5) puis Ré (D6) : un intervalle montant, discret et chaleureux.
    const notes: Array<[number, number]> = [
      [880, 0],
      [1174.66, 0.09],
    ];
    for (const [freq, retard] of notes) {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      const t = base + retard;
      osc.type = 'sine';
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.0001, t);
      gain.gain.exponentialRampToValueAtTime(0.12, t + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.28);
      osc.connect(gain).connect(ctx.destination);
      osc.start(t);
      osc.stop(t + 0.3);
    }
  } catch {
    /* audio indisponible : on reste silencieux. */
  }
}
