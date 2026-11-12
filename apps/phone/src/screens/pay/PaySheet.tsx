import type { PaymentRequest } from '@yeogiro/contracts'
import { useEffect, useMemo, useState } from 'react'
import { tones } from '../../call/tones'
import { Check, Close, Fingerprint, Store } from '../../oneui/icons'
import styles from './pay.module.css'

export const PAY_BRAND = '카카오페이'
const PIN_LENGTH = 6

type Step = 'review' | 'password' | 'processing' | 'done' | 'failed'

interface Props {
  payment: PaymentRequest
  onApprove: (paymentId: string) => Promise<boolean>
  onClose: () => void
}

export function PaySheet({ payment, onApprove, onClose }: Props) {
  const [step, setStep] = useState<Step>('review')
  const [entered, setEntered] = useState(0)
  const keys = useMemo(shuffledKeys, [])
  const amount = `${payment.amount.toLocaleString('ko-KR')}원`

  const submit = async () => {
    setStep('processing')
    const [ok] = await Promise.all([onApprove(payment.id), wait(900)])
    if (ok) tones.payComplete()
    setStep(ok ? 'done' : 'failed')
  }

  useEffect(() => {
    if (step === 'password' && entered === PIN_LENGTH) void submit()
  }, [entered, step])

  const press = (key: string) => {
    if (key === 'del') return setEntered((n) => Math.max(0, n - 1))
    if (!key) return
    navigator.vibrate?.(10)
    setEntered((n) => Math.min(PIN_LENGTH, n + 1))
  }

  return (
    <div className={`screen ${styles.sheet}`}>
      {step === 'review' && (
        <>
          <header className={styles.bar}>
            <button className={styles.close} onClick={onClose} aria-label="닫기">
              <Close />
            </button>
            <span className={styles.brand}>
              <span className={styles.brandMark}>pay</span>
              {PAY_BRAND}
            </span>
            <span className={styles.close} />
          </header>

          <section className={styles.summary}>
            <p className={styles.merchant}>
              <Store size={18} />
              {payment.merchant}
            </p>
            <p className={styles.amount}>{amount}</p>
            <p className={styles.item}>{payment.item}</p>
          </section>

          <section className={styles.details}>
            <Row label="결제수단" value={`${PAY_BRAND}머니`} sub="잔액 충분" />
            <Row label="할부" value="일시불" />
            <Row label="결제자" value={`${payment.payer}님`} />
          </section>

          <p className={styles.notice}>체험용 결제입니다. 실제로 돈이 빠져나가지 않아요.</p>

          <footer className={styles.footer}>
            <button className={styles.payButton} onClick={() => setStep('password')}>
              {amount} 결제하기
            </button>
          </footer>
        </>
      )}

      {step === 'password' && (
        <>
          <header className={styles.bar}>
            <button className={styles.close} onClick={() => setStep('review')} aria-label="뒤로">
              <Close />
            </button>
            <span />
            <span className={styles.close} />
          </header>
          <section className={styles.password}>
            <h2>
              {PAY_BRAND} 비밀번호를
              <br />
              입력해 주세요
            </h2>
            <div className={styles.dots}>
              {Array.from({ length: PIN_LENGTH }, (_, index) => (
                <span key={index} className={index < entered ? styles.dotOn : styles.dot} />
              ))}
            </div>
            <button className={styles.fingerprint} onClick={() => void submit()}>
              <Fingerprint size={20} />
              지문으로 결제
            </button>
          </section>
          <div className={styles.pinpad}>
            {keys.map((key, index) => (
              <button key={`${key}-${index}`} className={styles.pinKey} onClick={() => press(key)}>
                {key === 'del' ? '←' : key}
              </button>
            ))}
          </div>
        </>
      )}

      {step === 'processing' && (
        <div className={styles.center}>
          <span className={styles.spinner} />
          <p>결제하고 있어요</p>
        </div>
      )}

      {(step === 'done' || step === 'failed') && (
        <>
          <div className={styles.center}>
            <span className={step === 'done' ? styles.doneMark : styles.failMark}>
              {step === 'done' ? <Check size={34} /> : '!'}
            </span>
            <h2>{step === 'done' ? '결제 완료' : '결제하지 못했어요'}</h2>
            {step === 'done' && <p className={styles.doneAmount}>{amount}</p>}
            <p className={styles.doneMerchant}>{payment.merchant}</p>
          </div>
          <footer className={styles.footer}>
            <button className={styles.payButton} onClick={onClose}>
              확인
            </button>
          </footer>
        </>
      )}
    </div>
  )
}

function Row({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className={styles.row}>
      <span className={styles.rowLabel}>{label}</span>
      <span className={styles.rowValue}>
        {value}
        {sub && <em>{sub}</em>}
      </span>
    </div>
  )
}

function shuffledKeys(): string[] {
  const digits = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
  for (let i = digits.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[digits[i], digits[j]] = [digits[j], digits[i]]
  }
  return [...digits.slice(0, 9), '', digits[9], 'del']
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}
