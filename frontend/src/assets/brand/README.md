# Logos & marque — DSI 360

Dépose ici les fichiers de logo. Deux usages :

## 1. Logos importés dans l'interface (recommandé : **SVG**)

Place-les dans **ce dossier** (`frontend/src/assets/brand/`). Noms attendus :

- `logo-dsi360.svg` — logo complet (symbole + texte), pour la sidebar dépliée.
- `logo-mark.svg` — **symbole seul** (carré), pour la sidebar repliée / favicon / petits espaces.
- `logo-dsi360.png` — version PNG (fallback / e-mails / exports), idéalement ≥ 512 px.

Ils s'importent ensuite dans un composant :

```tsx
import logo from '@/assets/brand/logo-dsi360.svg';
<img src={logo} alt="DSI 360" />;
```

## 2. Fichiers statiques bruts (favicon, partage)

Pour le `favicon` et les images servies telles quelles, utilise **`frontend/public/`**
(ex. `public/favicon.svg`) — elles sont servies à la racine sans import.

> Convention : préférer le **SVG** (net à toute taille, léger). Le PNG sert de repli.
> Une fois les fichiers déposés, je branche le logo dans la sidebar (remplace l'actuel « D »).
