import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Built under /due-brew/ (Caddy strips that prefix); dev runs at / and
// proxies /api to a local API.
export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/due-brew/' : '/',
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
}))
