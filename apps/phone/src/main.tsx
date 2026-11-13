import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './app/App'
import { leaveInAppBrowser } from './app/inapp'
import { Preview } from './app/Preview'
import { watchForUpdates } from './app/updates'
import './oneui/theme.css'

const preview = new URLSearchParams(window.location.search).get('preview')

if (!preview) {
  leaveInAppBrowser()
  watchForUpdates()
}

createRoot(document.getElementById('root') as HTMLElement).render(
  <StrictMode>{preview ? <Preview which={preview} /> : <App />}</StrictMode>,
)
