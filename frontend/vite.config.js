import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

export default defineConfig({
  plugins: [svelte()],
  // Move Vite cache out of node_modules to avoid OneDrive/lock EPERM on Windows
  cacheDir: './.vite',
  // Use relative paths for assets so index.html works when opened directly
  base: './',
  build: {
    // Use relative paths for assets
    base: './',
    // Disable code splitting - create a single bundle
    cssCodeSplit: false,
    // Output directory
    outDir: 'dist',
    // Disable module preload for file:// compatibility
    modulePreload: false,
    rollupOptions: {
      input: {
        main: './index.html'
      },
      output: {
        // Single bundle file named bundle.js
        entryFileNames: 'bundle.js',
        // CSS in separate file (will be linked in HTML)
        assetFileNames: (assetInfo) => {
          if (assetInfo.name === 'style.css') {
            return 'bundle.css';
          }
          return 'assets/[name].[ext]';
        },
        // No chunks - everything in one file
        chunkFileNames: 'bundle.js',
        // IIFE format for file:// compatibility
        format: 'iife',
        // Global variable name
        name: 'JumpAnalyzerApp',
        // Inline all dynamic imports
        inlineDynamicImports: true,
        // No manual chunks - single bundle
        manualChunks: undefined
      },
      // No external dependencies
      external: []
    }
  },
  server: {
    port: 3000,
    watch: {
      // More robust watching on network/OneDrive filesystems
      usePolling: true,
      interval: 200
    },
    
    proxy: {
      "/api/players": {
        target: "http://94.177.160.183",
        changeOrigin: true,
        rewrite: (p) => p
      },
      "/api": {
        target: "http://localhost:5000",
        changeOrigin: true
      }
    }
  },
  preview: {
    port: 4173,
    host: true,
    open: true,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true
      }
    }
  }
})