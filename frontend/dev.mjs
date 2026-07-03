// Démarre l'API (FastAPI/uvicorn) ET le frontend (Vite) en une seule commande : `npm run dev`.
// Un seul terminal ; Ctrl+C arrête les deux. Aucune dépendance externe.
import { spawn } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { existsSync } from 'node:fs';

const ici = dirname(fileURLToPath(import.meta.url));
const racine = join(ici, '..');
const win = process.platform === 'win32';

const python = win
  ? join(racine, 'backend', '.venv', 'Scripts', 'python.exe')
  : join(racine, 'backend', '.venv', 'bin', 'python');
const envFile = join(racine, 'infra', 'local', '.env');

if (!existsSync(python)) {
  console.error(`\n[dev] venv introuvable : ${python}\n      Crée-le d'abord (cf. infra/local/README.md).\n`);
  process.exit(1);
}
if (!existsSync(envFile)) {
  console.error(`\n[dev] Config absente : ${envFile}\n      Copie infra/local/.env.example en .env.\n`);
  process.exit(1);
}

const procs = [];
function lancer(cmd, args, opts) {
  // shell:true requis sous Windows (Node ≥ 20) pour lancer .exe/.cmd de façon fiable.
  const p = spawn(`"${cmd}"`, args, { stdio: 'inherit', shell: true, ...opts });
  p.on('exit', (code) => {
    // Si l'un s'arrête, on arrête l'autre pour ne pas laisser de processus orphelin.
    arreter();
    if (code) process.exitCode = code;
  });
  procs.push(p);
  return p;
}
let enArret = false;
function arreter() {
  if (enArret) return;
  enArret = true;
  for (const p of procs) p.kill();
}
process.on('SIGINT', arreter);
process.on('SIGTERM', arreter);

// API : uvicorn avec rechargement à chaud, config chargée depuis infra/local/.env.
lancer(
  python,
  ['-m', 'uvicorn', 'dsi360.interface.app:app', '--host', '127.0.0.1', '--port', '8011',
    '--reload', '--reload-dir', join(racine, 'backend', 'src'), '--env-file', envFile],
  { cwd: join(racine, 'backend') },
);
// Frontend : serveur Vite (HMR).
lancer(win ? 'npm.cmd' : 'npm', ['run', 'web'], { cwd: ici });
