import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * O che do dev, Vite phuc vu giao dien o port rieng va proxy /api sang Fastify.
 * Nho vay khong phai build lai moi lan sua giao dien.
 *
 * Khi build (`npm run build:web`), ket qua nam o web/dist va Fastify tu phuc vu —
 * luc do khong con proxy, tat ca cung mot origin.
 */
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: '127.0.0.1', // D17: chi localhost
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:3000',
        changeOrigin: true,
        // SSE khong duoc buffer, neu khong cau tra loi chi hien khi ket noi dong.
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            proxyRes.headers['cache-control'] = 'no-cache';
          });
        },
      },
    },
  },
  build: { outDir: 'dist', emptyOutDir: true },
});
