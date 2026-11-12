import type { InboxMessage, PaymentRequest, PhoneEvent } from '@yeogiro/contracts'
import { useCallback, useEffect, useRef, useState } from 'react'
import type { RecentCall } from '../app/recents'
import { api } from '../data/api'
import { openMicrophone, tones } from './tones'

export type CallPhase = 'idle' | 'dialing' | 'connected' | 'ended' | 'failed'

export interface CallHandlers {
  onPayment: (payment: PaymentRequest | null) => void
  onMessage: (message: InboxMessage) => void
  onFinished: (call: RecentCall) => void
}

interface Live {
  pc?: RTCPeerConnection
  events?: EventSource
  stopMic?: () => void
  stopRing?: () => void
  track?: MediaStreamTrack
  wakeLock?: WakeLockSentinel
  callId?: string
  digits: string
  connectedAt?: number
  ended: boolean
}

const MIN_RING_MS = 2600
const CONNECT_TIMEOUT_MS = 15000
const END_SCREEN_MS = 2200

export function useCall(token: string | null, phoneBand: boolean, handlers: CallHandlers) {
  const [phase, setPhase] = useState<CallPhase>('idle')
  const [digits, setDigits] = useState('')
  const [elapsed, setElapsed] = useState(0)
  const [muted, setMuted] = useState(false)
  const [speaker, setSpeaker] = useState(true)
  const live = useRef<Live>({ digits: '', ended: true })
  const handlersRef = useRef(handlers)
  handlersRef.current = handlers

  useEffect(() => {
    if (phase !== 'connected') return
    const timer = window.setInterval(() => {
      const since = live.current.connectedAt
      if (since) setElapsed(Math.floor((Date.now() - since) / 1000))
    }, 250)
    return () => window.clearInterval(timer)
  }, [phase])

  const release = useCallback(() => {
    const current = live.current
    current.stopRing?.()
    current.events?.close()
    current.pc?.close()
    current.stopMic?.()
    void current.wakeLock?.release().catch(() => undefined)
    const audio = remoteAudio()
    audio.srcObject = null
  }, [])

  const finish = useCallback(
    (by: 'caller' | 'remote' | 'error') => {
      const current = live.current
      if (current.ended) return
      current.ended = true
      release()
      if (by === 'caller' && token && current.callId) {
        void api.hangup(token, current.callId).catch(() => undefined)
      }
      tones.hangup()
      handlersRef.current.onPayment(null)
      const durationSec = current.connectedAt ? Math.round((Date.now() - current.connectedAt) / 1000) : 0
      handlersRef.current.onFinished({ digits: current.digits, at: Date.now(), durationSec })
      setPhase(by === 'error' ? 'failed' : 'ended')
      window.setTimeout(() => setPhase('idle'), END_SCREEN_MS)
    },
    [release, token],
  )

  const onEvent = useCallback(
    (event: PhoneEvent) => {
      switch (event.type) {
        case 'payment.requested':
          handlersRef.current.onPayment(event.payment)
          break
        case 'payment.expired':
          handlersRef.current.onPayment(null)
          break
        case 'message.received':
          handlersRef.current.onMessage(event.message)
          break
        case 'call.ended':
          finish('remote')
          break
      }
    },
    [finish],
  )

  const dial = useCallback(
    async (number: string) => {
      if (!token || !live.current.ended) return
      live.current = { digits: number, ended: false }
      setDigits(number)
      setElapsed(0)
      setMuted(false)
      setSpeaker(true)
      setPhase('dialing')

      const startedAt = performance.now()
      tones.unlock()
      live.current.stopRing = tones.ringback()
      live.current.wakeLock = await navigator.wakeLock?.request('screen').catch(() => undefined)

      try {
        const mic = await openMicrophone(phoneBand)
        live.current.stopMic = mic.stop
        live.current.track = mic.track

        const pc = new RTCPeerConnection()
        live.current.pc = pc
        pc.ontrack = (track) => {
          const audio = remoteAudio()
          audio.srcObject = track.streams[0]
          audio.volume = 1
          void audio.play().catch(() => undefined)
        }
        pc.addTrack(mic.track)
        pc.createDataChannel('oai-events')

        const offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        const created = await api.createCall(token, offer.sdp ?? '')
        live.current.callId = created.callId
        live.current.events = api.events(token, created.callId, onEvent)
        await pc.setRemoteDescription({ type: 'answer', sdp: created.sdp })
        await connected(pc)

        const rang = performance.now() - startedAt
        if (rang < MIN_RING_MS) await sleep(MIN_RING_MS - rang)
        if (live.current.ended) return
        live.current.stopRing?.()
        live.current.stopRing = undefined
        live.current.connectedAt = Date.now()
        setPhase('connected')
        pc.onconnectionstatechange = () => {
          if (['failed', 'disconnected', 'closed'].includes(pc.connectionState)) finish('remote')
        }
        await api.connected(token, created.callId)
      } catch (error) {
        console.error(error)
        finish('error')
      }
    },
    [finish, onEvent, phoneBand, token],
  )

  const hangup = useCallback(() => finish('caller'), [finish])

  const toggleMute = useCallback(() => {
    setMuted((value) => {
      const next = !value
      if (live.current.track) live.current.track.enabled = !next
      return next
    })
  }, [])

  const toggleSpeaker = useCallback(() => {
    setSpeaker((value) => {
      const next = !value
      remoteAudio().volume = next ? 1 : 0.45
      return next
    })
  }, [])

  const approvePayment = useCallback(
    async (paymentId: string) => {
      if (!token) return false
      try {
        await api.approvePayment(token, paymentId)
        return true
      } catch {
        return false
      }
    },
    [token],
  )

  useEffect(() => () => release(), [release])

  return { phase, digits, elapsed, muted, speaker, dial, hangup, toggleMute, toggleSpeaker, approvePayment }
}

function remoteAudio(): HTMLAudioElement {
  return document.getElementById('remote-audio') as HTMLAudioElement
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

function connected(pc: RTCPeerConnection): Promise<void> {
  return new Promise((resolve, reject) => {
    if (pc.connectionState === 'connected') return resolve()
    const timer = window.setTimeout(() => reject(new Error('connect timeout')), CONNECT_TIMEOUT_MS)
    pc.addEventListener('connectionstatechange', () => {
      if (pc.connectionState === 'connected') {
        window.clearTimeout(timer)
        resolve()
      } else if (pc.connectionState === 'failed') {
        window.clearTimeout(timer)
        reject(new Error('connect failed'))
      }
    })
  })
}
