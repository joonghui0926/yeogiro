import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { registerSW } from 'virtual:pwa-register'
import { App } from './app/App'
import { Preview } from './app/Preview'
import './oneui/theme.css'

const preview = new URLSearchParams(window.location.search).get('preview')

if (!preview) registerSW({ immediate: true })

createRoot(document.getElementById('root') as HTMLElement).render(
  <StrictMode>{preview ? <Preview which={preview} /> : <App />}</StrictMode>,
)
