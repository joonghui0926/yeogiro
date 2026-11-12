import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'prompt',
      includeAssets: ['icons/icon-64.png', 'icons/icon-180.png'],
      manifest: {
        id: '/',
        name: '여기로',
        short_name: '여기로',
        description: '전화 한 통으로 끝나는 기차 예매',
        lang: 'ko',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        orientation: 'portrait',
        background_color: '#ffffff',
        theme_color: '#ffffff',
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/icons/maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/console/, /^\/api/],
        globPatterns: ['**/*.{js,css,html,png}'],
      },
    }),
  ],
  build: {
    outDir: '../../dist/hosting',
    emptyOutDir: true,
  },
  server: {
    port: 5199,
    proxy: { '/api': process.env.API_PROXY ?? 'http://localhost:8787' },
  },
})
