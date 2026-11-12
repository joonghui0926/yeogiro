import type { InboxMessage, PaymentRequest } from '@yeogiro/contracts'
import { useState } from 'react'
import { Dialer } from '../screens/dialer/Dialer'
import { CallScreen } from '../screens/call/CallScreen'
import { Messages } from '../screens/messages/Messages'
import { HeadsUp } from '../screens/overlay/Overlays'
import { PaySheet } from '../screens/pay/PaySheet'

const PAYMENT: PaymentRequest = {
  id: 'preview',
  amount: 16500,
  merchant: '여기로 기차예약',
  item: '대전→서울 KTX 14:06',
  payer: '김순자',
}

const MESSAGE: InboxMessage = {
  id: 'm1',
  sender: '여기로',
  body: '[여기로] 예약 확인\n11월 17일(화) 대전→서울\nKTX 119 14:06 출발 · 15:10 도착\n3호차 7A · 16,500원\n체험용 예약입니다. 실제 결제는 되지 않았고 곧 자동 취소됩니다.',
  sentAt: new Date().toISOString(),
}

/** Renders a single screen in isolation for visual QA. Enabled by ?preview=<name>. */
export function Preview({ which }: { which: string }) {
  const [, force] = useState(0)
  return (
    <div className="app">
      {which === 'keypad' && <Dialer tab="keypad" recents={[]} onTab={() => {}} onDial={() => {}} onOpenMessages={() => {}} />}
      {which === 'recents' && (
        <Dialer
          tab="recents"
          recents={[{ digits: '16660926', at: Date.now() - 3_600_000, durationSec: 46 }]}
          onTab={() => {}}
          onDial={() => {}}
          onOpenMessages={() => {}}
        />
      )}
      {which === 'contacts' && <Dialer tab="contacts" recents={[]} onTab={() => {}} onDial={() => {}} onOpenMessages={() => {}} />}
      {(which === 'dialing' || which === 'ended') && (
        <CallScreen
          phase={which}
          digits="16660926"
          elapsed={52}
          muted={false}
          speaker
          onHangup={() => {}}
          onMute={() => {}}
          onSpeaker={() => {}}
        />
      )}
      {which === 'sms-notice' && (
        <>
          <CallScreen
            phase="connected"
            digits="16660926"
            elapsed={44}
            muted={false}
            speaker
            onHangup={() => {}}
            onMute={() => {}}
            onSpeaker={() => {}}
          />
          <HeadsUp
            notice={{ kind: 'message', id: 'm', sender: MESSAGE.sender, body: MESSAGE.body }}
            onOpen={() => {}}
            onDismiss={() => {}}
          />
        </>
      )}
      {which === 'call' && (
        <CallScreen
          phase="connected"
          digits="16660926"
          elapsed={27}
          muted={false}
          speaker
          onHangup={() => {}}
          onMute={() => {}}
          onSpeaker={() => {}}
        />
      )}
      {which === 'pay' && <PaySheet payment={PAYMENT} onApprove={async () => true} onClose={() => {}} />}
      {which === 'pay-notice' && (
        <>
          <CallScreen
            phase="connected"
            digits="16660926"
            elapsed={36}
            muted={false}
            speaker
            onHangup={() => {}}
            onMute={() => {}}
            onSpeaker={() => {}}
          />
          <HeadsUp
          notice={{ kind: 'payment', id: 'p', amount: 16500, item: '대전→서울 KTX 14:06' }}
          onOpen={() => {}}
          onDismiss={() => {}}
          />
        </>
      )}
      {which === 'sms' && (
        <Messages messages={[MESSAGE]} thread onOpenThread={() => {}} onBack={() => {}} onCall={() => force((n) => n + 1)} />
      )}
      {which === 'sms-list' && (
        <Messages messages={[MESSAGE]} thread={false} onOpenThread={() => {}} onBack={() => {}} onCall={() => {}} />
      )}
    </div>
  )
}
