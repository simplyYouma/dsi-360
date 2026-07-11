import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { ThemeProvider } from '@/design-system/ThemeProvider';
import { enregistrerSW } from '@/pwa/enregistrerSW';
import '@/design-system/tokens.css';
import '@/design-system/reset.css';
import { App } from './App';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <App />
    </ThemeProvider>
  </StrictMode>,
);

enregistrerSW();
