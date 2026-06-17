import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5290, // décalé pour cohabiter avec d'autres projets
    proxy: {
      '/api': { target: 'http://localhost:8011', changeOrigin: true },
    },
  },
  build: { outDir: 'dist', sourcemap: false },
});
