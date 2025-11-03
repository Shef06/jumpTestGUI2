import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

export default defineConfig({
  plugins: [svelte()],
  // Move Vite cache out of node_modules to avoid OneDrive/lock EPERM on Windows
  cacheDir: './.vite',
  server: {
    port: 3000,
    watch: {
      // More robust watching on network/OneDrive filesystems
      usePolling: true,
      interval: 200
    },
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true
      }
    }
  }
})