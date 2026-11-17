import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: './',
  plugins: [react()],
  resolve: { dedupe: ['react', 'react-dom', 'three', 'lucide-react'] },
  build: { outDir: 'dist', emptyOutDir: true },
  server: {
    strictPort: true,
    proxy: {
      '/api': 'http://127.0.0.1:8016',
      '/ws': { target: 'ws://127.0.0.1:8016', ws: true },
    },
  },
});
