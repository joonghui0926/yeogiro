import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  base: '/console/',
  plugins: [
    react(),
    VitePWA({
      registerType: 'prompt',
      manifest: {
        id: '/console/',
        name: '여기로 운영',
        short_name: '여기로 운영',
        description: '여기로 통화 기록과 운영',
        lang: 'ko',
        start_url: '/console/',
        scope: '/console/',
        display: 'standalone',
        background_color: '#f7f6f2',
        theme_color: '#f7f6f2',
        icons: [
          { src: '/console/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/console/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/console/icons/maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        navigateFallback: '/console/index.html',
        navigateFallbackAllowlist: [/^\/console/],
        globPatterns: ['**/*.{js,css,html,png}'],
        maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
      },
    }),
  ],
  build: {
    outDir: '../../dist/hosting/console',
    emptyOutDir: true,
    rollupOptions: {
      output: { manualChunks: { firebase: ['firebase/app', 'firebase/auth', 'firebase/firestore'] } },
    },
  },
  server: { port: 5174 },
})
