import type { InboxMessage, PaymentRequest } from '@yeogiro/contracts'
import { useCallback, useEffect, useMemo, useState, type CSSProperties } from 'react'
import { useCall } from '../call/useCall'
import { tones } from '../call/tones'
import { api, type Me } from '../data/api'
import { CallScreen } from '../screens/call/CallScreen'
import { Dialer, type DialerTab } from '../screens/dialer/Dialer'
import { Messages } from '../screens/messages/Messages'
import { CallBanner, HeadsUp, type Notice } from '../screens/overlay/Overlays'
import { PaySheet } from '../screens/pay/PaySheet'
import { CONTACT } from './contact'
import { addRecent, loadRecents, type RecentCall } from './recents'
import { resolveTesterToken } from './tester'

type Screen = 'phone' | 'messages'

export function App() {
  const token = useMemo(resolveTesterToken, [])
  const [me, setMe] = useState<Me | null>(null)
  const [screen, setScreen] = useState<Screen>('phone')
  const [tab, setTab] = useState<DialerTab>('keypad')
  const [thread, setThread] = useState(false)
  const [messages, setMessages] = useState<InboxMessage[]>([])
  const [recents, setRecents] = useState<RecentCall[]>(loadRecents)
  const [payment, setPayment] = useState<PaymentRequest | null>(null)
  const [payOpen, setPayOpen] = useState(false)
  const [notice, setNotice] = useState<Notice | null>(null)
  const [callHidden, setCallHidden] = useState(false)

  useEffect(() => {
    if (!token) return
    api.me(token).then(setMe).catch(() => setMe(null))
    api.inbox(token).then(setMessages).catch(() => undefined)
  }, [token])

  const call = useCall(token, me?.phoneBand ?? false, {
    onPayment: (next) => {
      setPayment(next)
      if (next) {
        tones.notification()
        setNotice({ kind: 'payment', id: next.id, amount: next.amount, item: next.item })
      } else {
        setPayOpen(false)
        setNotice((current) => (current?.kind === 'payment' ? null : current))
      }
    },
    onMessage: (message) => {
      setMessages((current) => [...current, message])
      tones.notification()
      setNotice({ kind: 'message', id: message.id, sender: message.sender, body: message.body })
    },
    onFinished: (recent) => setRecents(addRecent(recent)),
  })

  const inCall = call.phase !== 'idle'
  useEffect(() => {
    if (!inCall) {
      setCallHidden(false)
      setPayOpen(false)
    }
  }, [inCall])

  const dial = useCallback(
    (digits: string) => {
      setScreen('phone')
      setCallHidden(false)
      void call.dial(digits)
    },
    [call],
  )

  const openNotice = () => {
    if (!notice) return
    if (notice.kind === 'payment' && payment) {
      setPayOpen(true)
    } else if (notice.kind === 'message') {
      setScreen('messages')
      setThread(true)
      if (inCall) setCallHidden(true)
    }
    setNotice(null)
  }

  const dismissNotice = useCallback(() => setNotice(null), [])

  if (!token) {
    return (
      <div className="app">
        <div className="screen" style={{ justifyContent: 'center', alignItems: 'center', gap: 8 }}>
          <img src="/icons/icon-192.png" width={72} height={72} alt="" style={{ borderRadius: 18 }} />
          <p style={{ margin: '12px 0 0', fontSize: 17, fontWeight: 600 }}>여기로</p>
          <p style={{ margin: 0, color: 'var(--ui-muted)', fontSize: 15 }}>테스터 링크로 열어 주세요</p>
        </div>
      </div>
    )
  }

  const bannerVisible = inCall && (callHidden || payOpen) && call.phase === 'connected'
  const appStyle = bannerVisible ? ({ '--call-banner': '34px' } as CSSProperties) : undefined

  return (
    <div className="app" style={appStyle}>
      {screen === 'phone' && (
        <Dialer
          tab={tab}
          recents={recents}
          onTab={setTab}
          onDial={dial}
          onOpenMessages={() => {
            setScreen('messages')
            setThread(false)
          }}
        />
      )}
      {screen === 'messages' && (
        <Messages
          messages={messages}
          thread={thread}
          onOpenThread={() => setThread(true)}
          onBack={() => (thread ? setThread(false) : setScreen('phone'))}
          onCall={() => dial(CONTACT.digits)}
        />
      )}

      {inCall && !callHidden && (
        <CallScreen
          phase={call.phase}
          digits={call.digits}
          elapsed={call.elapsed}
          muted={call.muted}
          speaker={call.speaker}
          onHangup={call.hangup}
          onMute={call.toggleMute}
          onSpeaker={call.toggleSpeaker}
        />
      )}

      {payOpen && payment && (
        <PaySheet
          payment={payment}
          onApprove={call.approvePayment}
          onClose={() => {
            setPayOpen(false)
            setPayment(null)
            setCallHidden(false)
          }}
        />
      )}

      {bannerVisible && (
        <CallBanner
          elapsed={call.elapsed}
          onReturn={() => {
            setCallHidden(false)
            setPayOpen(false)
          }}
        />
      )}

      {notice && <HeadsUp notice={notice} onOpen={openNotice} onDismiss={dismissNotice} />}

    </div>
  )
}
