export interface RecentCall {
  digits: string
  at: number
  durationSec: number
}

const KEY = 'yeogiro.recents'

export function loadRecents(): RecentCall[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? '[]') as RecentCall[]
  } catch {
    return []
  }
}

export function addRecent(call: RecentCall): RecentCall[] {
  const next = [call, ...loadRecents()].slice(0, 30)
  try {
    localStorage.setItem(KEY, JSON.stringify(next))
  } catch {
    return next
  }
  return next
}
