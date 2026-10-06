import fs from 'fs'
import path from 'path'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import frappeui from 'frappe-ui/vite'

function socketioPort() {
  try {
    const config = path.resolve(import.meta.dirname, '../../../sites/common_site_config.json')
    return JSON.parse(fs.readFileSync(config, 'utf8')).socketio_port ?? 9000
  } catch {
    return 9000
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    // frontendRoute builds into ../vuna_sourcing/public/frontend and copies
    // index.html to ../vuna_sourcing/www/portal.html (served at /portal)
    frappeui({ frontendRoute: '/vuna-sourcing' }),
    vue(),
  ],
  server: {
    proxy: {
      '/socket.io': { target: `http://127.0.0.1:${socketioPort()}`, ws: true },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, 'src'),
    },
  },
})
