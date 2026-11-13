import type { InboxMessage, PhoneEvent } from '@yeogiro/contracts'
import { deviceId } from '../app/device'

const BASE = import.meta.env.VITE_API_BASE ?? ''

export interface Me {
  id: string
  label: string
  alias: string
  phoneBand: boolean
}

export interface ClientReport {
  ua: string
  audio: string
  mic: string
}

// Cloud Run can briefly run a second instance and a call lives in one instance's
// memory, so a 404 on a call route may only mean the request reached the other one.
const OTHER_INSTANCE_RETRIES = 8
const RETRY_DELAY_MS = 250

async function post<T>(path: string, body: unknown, retries = 0): Promise<T> {
  for (let attempt = 0; ; attempt += 1) {
    const response = await fetch(`${BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (response.ok) return (await response.json()) as T
    if (response.status !== 404 || attempt >= retries) throw new Error(`${path} ${response.status}`)
    await new Promise((resolve) => window.setTimeout(resolve, RETRY_DELAY_MS))
  }
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE}${path}`)
  if (!response.ok) throw new Error(`${path} ${response.status}`)
  return (await response.json()) as T
}

export const api = {
  me: (token: string) => get<Me>(`/api/me?token=${encodeURIComponent(token)}`),
  inbox: (token: string) =>
    get<{ messages: InboxMessage[] }>(`/api/inbox?token=${encodeURIComponent(token)}&device=${deviceId()}`).then(
      (r) => r.messages,
    ),
  createCall: (token: string, sdp: string) =>
    post<{ callId: string; sdp: string; phoneBand: boolean }>('/api/calls', { token, sdp, device: deviceId() }),
  connected: (token: string, callId: string, client: ClientReport) =>
    post<{ ok: boolean }>(
      `/api/calls/${callId}/connected`,
      { token, client, device: deviceId() },
      OTHER_INSTANCE_RETRIES,
    ),
  hangup: (token: string, callId: string) =>
    post<{ ok: boolean }>(`/api/calls/${callId}/hangup`, { token, device: deviceId() }, OTHER_INSTANCE_RETRIES),
  approvePayment: (token: string, paymentId: string) =>
    post<{ ok: boolean }>(
      `/api/payments/${paymentId}/approve`,
      { token, device: deviceId() },
      OTHER_INSTANCE_RETRIES,
    ),
  events: (token: string, callId: string, onEvent: (event: PhoneEvent) => void): { close: () => void } => {
    const url = `${BASE}/api/calls/${callId}/events?token=${encodeURIComponent(token)}&device=${deviceId()}`
    let source: EventSource | null = null
    let retries = OTHER_INSTANCE_RETRIES
    let closed = false
    const open = () => {
      const current = new EventSource(url)
      source = current
      current.onmessage = (message) => onEvent(JSON.parse(message.data) as PhoneEvent)
      current.onerror = () => {
        if (closed || current.readyState !== EventSource.CLOSED || retries <= 0) return
        retries -= 1
        window.setTimeout(open, RETRY_DELAY_MS)
      }
    }
    open()
    return {
      close: () => {
        closed = true
        source?.close()
      },
    }
  },
}
