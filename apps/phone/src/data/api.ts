import type { InboxMessage, PhoneEvent } from '@yeogiro/contracts'

const BASE = import.meta.env.VITE_API_BASE ?? ''

export interface Me {
  id: string
  label: string
  alias: string
  phoneBand: boolean
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) throw new Error(`${path} ${response.status}`)
  return (await response.json()) as T
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE}${path}`)
  if (!response.ok) throw new Error(`${path} ${response.status}`)
  return (await response.json()) as T
}

export const api = {
  me: (token: string) => get<Me>(`/api/me?token=${encodeURIComponent(token)}`),
  inbox: (token: string) =>
    get<{ messages: InboxMessage[] }>(`/api/inbox?token=${encodeURIComponent(token)}`).then((r) => r.messages),
  createCall: (token: string, sdp: string) =>
    post<{ callId: string; sdp: string; phoneBand: boolean }>('/api/calls', { token, sdp }),
  connected: (token: string, callId: string) => post<{ ok: boolean }>(`/api/calls/${callId}/connected`, { token }),
  hangup: (token: string, callId: string) => post<{ ok: boolean }>(`/api/calls/${callId}/hangup`, { token }),
  approvePayment: (token: string, paymentId: string) =>
    post<{ ok: boolean }>(`/api/payments/${paymentId}/approve`, { token }),
  events: (token: string, callId: string, onEvent: (event: PhoneEvent) => void): EventSource => {
    const source = new EventSource(`${BASE}/api/calls/${callId}/events?token=${encodeURIComponent(token)}`)
    source.onmessage = (message) => onEvent(JSON.parse(message.data) as PhoneEvent)
    return source
  },
}
