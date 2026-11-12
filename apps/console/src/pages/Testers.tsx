import type { CallDoc, TesterDoc } from '@yeogiro/contracts'
import QRCode from 'qrcode'
import { useEffect, useState } from 'react'
import { PHONE_ORIGIN } from '../app/firebase'
import ui from '../components/ui.module.css'
import { toDate, when } from '../data/format'
import { useCalls, useTesters, type WithId } from '../data/hooks'
import styles from './testers.module.css'

export function Testers() {
  const testers = useTesters()
  const calls = useCalls()
  const [qrFor, setQrFor] = useState<WithId<TesterDoc> | null>(null)
  const [copied, setCopied] = useState<string | null>(null)

  const copy = (tester: WithId<TesterDoc>) => {
    void navigator.clipboard.writeText(linkOf(tester))
    setCopied(tester.id)
    window.setTimeout(() => setCopied((id) => (id === tester.id ? null : id)), 1500)
  }

  const rows = [...(testers ?? [])].sort((a, b) => a.id.localeCompare(b.id, 'en', { numeric: true }))

  return (
    <div className={ui.page}>
      <header className={ui.pageHead}>
        <div>
          <h1 className={ui.pageTitle}>테스터</h1>
          <p className={ui.pageSub}>설치 링크를 테스터 폰에서 열고 홈 화면에 추가하면 여기로 앱이 생겨요. QR을 띄워 바로 찍게 해도 돼요.</p>
        </div>
      </header>

      {testers === null ? (
        <div className={ui.empty}>불러오는 중</div>
      ) : rows.length === 0 ? (
        <div className={`${ui.card} ${ui.empty}`}>아직 테스터가 없어요.</div>
      ) : (
        <div className={`${ui.card} ${styles.list}`}>
          <div className={styles.head}>
            <span>테스터</span>
            <span>출발역</span>
            <span>경로 우대</span>
            <span>통화</span>
            <span />
          </div>
          {rows.map((tester) => {
            const mine = (calls ?? []).filter((c) => c.testerId === tester.id || c.testerLabel === tester.label)
            return (
              <div key={tester.id} className={styles.row}>
                <span className={styles.who}>
                  <strong>{tester.label}</strong>
                  <em>{tester.alias}</em>
                </span>
                <span className={styles.cell}>{tester.homeStation ?? '–'}</span>
                <span className={styles.cell}>
                  <span className={`${ui.chip} ${tester.senior ? ui.chipGood : ''}`}>
                    {tester.senior === null ? '모름' : tester.senior ? '대상' : '아님'}
                  </span>
                </span>
                <span className={`${styles.cell} ${styles.calls}`}>{summary(mine)}</span>
                <span className={styles.actions}>
                  <button className={styles.action} onClick={() => copy(tester)}>
                    {copied === tester.id ? '복사됨' : '링크 복사'}
                  </button>
                  <button className={styles.action} onClick={() => setQrFor(tester)}>
                    QR
                  </button>
                </span>
              </div>
            )
          })}
        </div>
      )}

      {qrFor && <QrDialog tester={qrFor} onClose={() => setQrFor(null)} />}
    </div>
  )
}

function QrDialog({ tester, onClose }: { tester: WithId<TesterDoc>; onClose: () => void }) {
  const link = linkOf(tester)
  const [src, setSrc] = useState('')
  useEffect(() => {
    void QRCode.toDataURL(link, { margin: 1, width: 560 }).then(setSrc)
  }, [link])
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className={styles.scrim} onClick={onClose} role="presentation">
      <div className={styles.dialog} role="dialog" aria-label={`${tester.label} 설치 QR`} onClick={(e) => e.stopPropagation()}>
        <p className={styles.dialogTitle}>
          {tester.label} <em>{tester.alias}</em>
        </p>
        {src && <img className={styles.qr} src={src} alt="설치 링크 QR" />}
        <p className={styles.link}>{link}</p>
        <button className={ui.button} onClick={onClose}>
          닫기
        </button>
      </div>
    </div>
  )
}

function linkOf(tester: TesterDoc): string {
  return `${PHONE_ORIGIN}/t/${tester.token}`
}

function summary(calls: WithId<CallDoc>[]): string {
  if (calls.length === 0) return '아직 없음'
  const last = calls.reduce((a, b) => ((toDate(a.startedAt)?.getTime() ?? 0) > (toDate(b.startedAt)?.getTime() ?? 0) ? a : b))
  return `${calls.length}회 · 최근 ${when(toDate(last.startedAt))}`
}
