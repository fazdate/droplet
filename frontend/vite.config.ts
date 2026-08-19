import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    proxy: {
      // During `npm run dev`, forward API calls to the FastAPI backend so the
      // SPA can be developed standalone without the Docker static-file mount.
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
});
