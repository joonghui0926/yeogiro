const STORAGE_KEY = 'yeogiro.tester'
const DEFAULT_TOKEN: string | undefined = import.meta.env.VITE_DEFAULT_TESTER

export function resolveTesterToken(): string | null {
  const match = window.location.pathname.match(/^\/t\/([\w-]+)/)
  const fromQuery = new URLSearchParams(window.location.search).get('t')
  const fromUrl = match?.[1] ?? fromQuery
  if (fromUrl) {
    try {
      localStorage.setItem(STORAGE_KEY, fromUrl)
    } catch {
      return fromUrl
    }
    window.history.replaceState(null, '', '/')
    return fromUrl
  }
  try {
    return localStorage.getItem(STORAGE_KEY) ?? DEFAULT_TOKEN ?? null
  } catch {
    return DEFAULT_TOKEN ?? null
  }
}
