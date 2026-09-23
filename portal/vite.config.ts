import path from 'path'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import frappeui from 'frappe-ui/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    // frontendRoute builds into ../vuna_sourcing/public/frontend and copies
    // index.html to ../vuna_sourcing/www/portal.html (served at /portal)
    frappeui({ frontendRoute: '/vuna-sourcing' }),
    vue(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, 'src'),
    },
  },
})
