const STORAGE_KEY = 'yeogiro.tester'

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
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}
