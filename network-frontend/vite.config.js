import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  base: mode === 'production' ? '/network/' : '/',
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
}));
