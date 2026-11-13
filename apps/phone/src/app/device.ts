const STORAGE_KEY = 'yeogiro.device'

let current: string | null = null

function fresh(): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(6)), (byte) => byte.toString(16).padStart(2, '0')).join('')
}

export function deviceId(): string {
  if (current) return current
  try {
    current = localStorage.getItem(STORAGE_KEY) ?? fresh()
    localStorage.setItem(STORAGE_KEY, current)
  } catch {
    current = fresh()
  }
  return current
}
