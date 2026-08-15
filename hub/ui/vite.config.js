import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import { resolve } from 'node:path'

// Dev: the UI runs here, the data comes from the real hub on the homelab.
// OIKOS_DEV_API points at it (default: the box itself, port 8100).
const api = process.env.OIKOS_DEV_API || 'http://homelab:8100'

// Everything the Python hub owns. Anything not listed falls through to Vite,
// which is what serves the UI itself in dev.
const proxied = ['/api', '/jf', '/jfbd', '/acover', '/cover', '/img', '/wallpaper', '/steamhero']

export default defineConfig({
  plugins: [svelte()],
  server: {
    host: true,
    proxy: Object.fromEntries(
      proxied.map((p) => [p, { target: api, changeOrigin: true }])
    ),
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        // two surfaces, one design system
        phone: resolve(__dirname, 'index.html'),
        tv: resolve(__dirname, 'tv.html'),
      },
    },
  },
})
