import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// В dev-режиме API и фото проксируются на FastAPI (python -m app.main)
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/uploads': 'http://localhost:8000',
    },
  },
})
