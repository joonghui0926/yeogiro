import { useEffect } from 'react'
import { MessageBubble } from '../../oneui/icons'
import { formatElapsed } from '../call/CallScreen'
import { PAY_BRAND } from '../pay/PaySheet'
import styles from './overlays.module.css'

export type Notice =
  | { kind: 'message'; id: string; sender: string; body: string }
  | { kind: 'payment'; id: string; amount: number; item: string }

interface HeadsUpProps {
  notice: Notice
  onOpen: () => void
  onDismiss: () => void
}

const AUTO_DISMISS_MS = 7000

export function HeadsUp({ notice, onOpen, onDismiss }: HeadsUpProps) {
  useEffect(() => {
    if (notice.kind !== 'message') return
    const timer = window.setTimeout(onDismiss, AUTO_DISMISS_MS)
    return () => window.clearTimeout(timer)
  }, [notice, onDismiss])

  const isPayment = notice.kind === 'payment'
  return (
    <div className={styles.headsUpWrap}>
      <button key={notice.id} className={styles.headsUp} onClick={onOpen}>
        <span className={styles.meta}>
          {isPayment ? (
            <span className={styles.payIcon}>pay</span>
          ) : (
            <span className={styles.messageIcon}>
              <MessageBubble size={13} />
            </span>
          )}
          <span>{isPayment ? PAY_BRAND : '메시지'}</span>
          <span className={styles.dot}>•</span>
          <span>지금</span>
        </span>
        {isPayment ? (
          <>
            <strong className={styles.title}>{notice.amount.toLocaleString('ko-KR')}원 결제 요청</strong>
            <span className={styles.body}>{notice.item} · 눌러서 결제하기</span>
          </>
        ) : (
          <>
            <strong className={styles.title}>{notice.sender}</strong>
            <span className={styles.body}>{notice.body}</span>
          </>
        )}
      </button>
    </div>
  )
}

export function CallBanner({ elapsed, onReturn }: { elapsed: number; onReturn: () => void }) {
  return (
    <button className={styles.callBanner} onClick={onReturn}>
      통화 중 {formatElapsed(elapsed)} · 화면으로 돌아가기
    </button>
  )
}
