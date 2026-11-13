import { registerSW } from 'virtual:pwa-register'

const CHECK_EVERY_MS = 30 * 60 * 1000

let inCall = false
let applyUpdate: (() => void) | null = null

export function watchForUpdates(): void {
  const update = registerSW({
    immediate: true,
    onNeedRefresh() {
      applyUpdate = () => void update(true)
      if (!inCall) applyUpdate()
    },
    onRegisteredSW(_url, registration) {
      if (!registration) return
      const check = () => void registration.update().catch(() => undefined)
      window.setInterval(check, CHECK_EVERY_MS)
      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') check()
      })
    },
  })
}

export function setInCall(value: boolean): void {
  inCall = value
  if (!inCall && applyUpdate) applyUpdate()
}
