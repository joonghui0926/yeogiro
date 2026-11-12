import { STATE_LABEL, type CallOutcome } from '@yeogiro/contracts'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ModeChip, OutcomeChip } from '../components/Chips'
import ui from '../components/ui.module.css'
import { duration, toDate, when } from '../data/format'
import { useCalls } from '../data/hooks'
import styles from './calls.module.css'

type Filter = 'all' | 'live' | CallOutcome

const FILTERS: Array<[Filter, string]> = [
  ['all', '전체'],
  ['live', '진행 중'],
  ['booked', '예약 완료'],
  ['abandoned', '중단'],
  ['no_consent', '동의 없음'],
  ['payment_timeout', '결제 안 함'],
]

export function Calls() {
  const calls = useCalls()
  const [filter, setFilter] = useState<Filter>('all')
  const navigate = useNavigate()

  const rows = (calls ?? []).filter((call) => {
    if (filter === 'all') return true
    if (filter === 'live') return call.status === 'live'
    return call.status === 'ended' && (call.outcome ?? 'abandoned') === filter
  })

  return (
    <div className={ui.page}>
      <header className={ui.pageHead}>
        <div>
          <h1 className={ui.pageTitle}>통화</h1>
          <p className={ui.pageSub}>통화를 누르면 자막, 도구 호출, 동의 판정을 시간순으로 볼 수 있어요.</p>
        </div>
      </header>

      <div className={ui.filters}>
        {FILTERS.map(([key, label]) => (
          <button key={key} className={filter === key ? ui.filterOn : ui.filter} onClick={() => setFilter(key)}>
            {label}
          </button>
        ))}
      </div>

      {calls === null ? (
        <div className={ui.empty}>불러오는 중</div>
      ) : rows.length === 0 ? (
        <div className={ui.empty}>해당하는 통화가 없어요</div>
      ) : (
        <>
          <div className={`${ui.card} ${styles.tableCard}`}>
            <table className={ui.table}>
              <thead>
                <tr>
                  <th>시각</th>
                  <th>테스터</th>
                  <th>결과</th>
                  <th>길이</th>
                  <th>되묻기</th>
                  <th>멈춘 지점</th>
                  <th>방식</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((call) => (
                  <tr key={call.id} onClick={() => navigate(`/calls/${call.id}`)}>
                    <td className="num">{when(toDate(call.startedAt))}</td>
                    <td>{call.testerLabel}</td>
                    <td>
                      <OutcomeChip call={call} />
                    </td>
                    <td className="num">{call.status === 'ended' ? duration(call.durationSec) : ''}</td>
                    <td className="num">{call.reasks ?? (call.status === 'live' ? '' : 0)}</td>
                    <td className={ui.muted}>{call.stoppedAt ? STATE_LABEL[call.stoppedAt] : ''}</td>
                    <td>
                      <ModeChip call={call} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className={styles.cards}>
            {rows.map((call) => (
              <button key={call.id} className={styles.callCard} onClick={() => navigate(`/calls/${call.id}`)}>
                <span className={styles.cardTop}>
                  <strong>{call.testerLabel}</strong>
                  <OutcomeChip call={call} />
                </span>
                <span className={styles.cardMeta}>
                  {when(toDate(call.startedAt))}
                  {call.status === 'ended' && ` · ${duration(call.durationSec)} · 되묻기 ${call.reasks ?? 0}회`}
                </span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
