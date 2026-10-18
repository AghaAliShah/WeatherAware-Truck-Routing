import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development the Django API runs on :8000; in production Django serves this build itself.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } } },
  build: { target: 'es2022' },
})
