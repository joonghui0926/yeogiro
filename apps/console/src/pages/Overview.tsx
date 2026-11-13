import { OUTCOME_LABEL, STATE_LABEL } from '@yeogiro/contracts'
import { useNavigate } from 'react-router-dom'
import { CallerName, ModeChip, OutcomeChip } from '../components/Chips'
import ui from '../components/ui.module.css'
import { Donut, Meter, MiniStat, Sparkline, StatusStrip } from '../components/viz'
import styles from './overview.module.css'
import { day, duration, toDate, when } from '../data/format'
import { useCalls } from '../data/hooks'
import { summarize } from '../data/metrics'

export function Overview() {
  const calls = useCalls()
  const navigate = useNavigate()
  if (!calls) return <div className={ui.empty}>불러오는 중</div>

  const summary = summarize(calls)
  const recent = calls.slice(0, 6)
  const durations = calls
    .filter((c) => c.status === 'ended' && typeof c.durationSec === 'number')
    .slice(0, 14)
    .reverse()
    .map((c) => c.durationSec as number)
  const maxOutcome = Math.max(1, ...summary.outcomes.map(([, n]) => n))
  const maxStop = Math.max(1, ...summary.stops.map(([, n]) => n))
  const pct = summary.completionRate === null ? null : Math.round(summary.completionRate * 100)

  return (
    <div className={ui.page}>
      <header className={ui.pageHead}>
        <div>
          <h1 className={ui.pageTitle}>개요</h1>
          <p className={ui.pageSub}>
            {day(new Date())} 기준 · 끝난 통화 {summary.total}건
          </p>
        </div>
      </header>

      <section className={styles.hero}>
        <div className={styles.heroMain}>
          <Donut value={pct} goal={75} />
          <div className={styles.heroText}>
            <h2>예약까지 완주</h2>
            <p>
              {summary.total === 0
                ? '안내 없이 예약 확정까지 간 비율'
                : `끝난 통화 ${summary.total}건 중 ${summary.booked}건이 예약까지 갔어요`}
            </p>
          </div>
        </div>

        <div className={styles.heroSide}>
          <MiniStat
            label="예약당 되묻기"
            value={summary.avgReasks === null ? '–' : summary.avgReasks.toFixed(1)}
            unit={summary.avgReasks === null ? '' : '회'}
          >
            <Meter value={summary.avgReasks} max={6} goal={3} met={(summary.avgReasks ?? 0) <= 3} goalLabel="3회" />
          </MiniStat>

          <MiniStat label="동의 없는 예약" value={String(summary.unconsented)} unit="건">
            <StatusStrip
              good={summary.unconsented === 0}
              goodText={`동의 누락 0 · 게이트 차단 ${summary.gateBlocks}회`}
              badText={`동의 누락 ${summary.unconsented}건 — 확인 필요`}
            />
          </MiniStat>

          <MiniStat
            label="평균 통화 시간"
            value={summary.avgDuration === null ? '–' : duration(Math.round(summary.avgDuration))}
          >
            <Sparkline values={durations} />
          </MiniStat>
        </div>
      </section>

      <div className={ui.split}>
        <section className={ui.section}>
          <h2 className={ui.sectionTitle}>최근 통화</h2>
          <div className={`${ui.card} ${styles.recent}`} style={{ padding: recent.length ? '14px 8px' : '0' }}>
            {recent.length === 0 ? (
              <p className={ui.empty}>아직 통화가 없어요. 테스터 폰에서 전화를 걸어 보세요.</p>
            ) : (
              <table className={ui.table}>
                <tbody>
                  {recent.map((call) => (
                    <tr key={call.id} onClick={() => navigate(`/calls/${call.id}`)}>
                      <td className="num">{when(toDate(call.startedAt))}</td>
                      <td>
                        <CallerName call={call} />
                      </td>
                      <td>
                        <OutcomeChip call={call} />
                      </td>
                      <td className={ui.muted}>{call.status === 'ended' ? duration(call.durationSec) : ''}</td>
                      <td>
                        <ModeChip call={call} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>

        <section className={ui.section}>
          <h2 className={ui.sectionTitle}>결과와 멈춘 지점</h2>
          <div className={ui.card}>
            {summary.outcomes.length === 0 ? (
              <p className={ui.empty}>통화가 쌓이면 결과 분포가 보여요.</p>
            ) : (
              <div className={ui.barList}>
                {summary.outcomes.map(([outcome, count]) => (
                  <Bar key={outcome} label={OUTCOME_LABEL[outcome]} value={count} max={maxOutcome} />
                ))}
              </div>
            )}
            {summary.stops.length > 0 && (
              <>
                <p className={ui.muted} style={{ margin: '28px 0 14px', fontSize: 14 }}>
                  예약 전에 끝난 통화가 멈춘 단계
                </p>
                <div className={ui.barList}>
                  {summary.stops.map(([state, count]) => (
                    <Bar key={state} label={STATE_LABEL[state]} value={count} max={maxStop} tone="warn" />
                  ))}
                </div>
              </>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}

function Bar({ label, value, max, tone }: { label: string; value: number; max: number; tone?: 'warn' }) {
  return (
    <div className={ui.barRow}>
      <span>{label}</span>
      <span className={ui.barTrack}>
        <span
          className={ui.barFill}
          style={{ width: `${(value / max) * 100}%`, background: tone === 'warn' ? 'var(--warn)' : undefined }}
        />
      </span>
      <span className={ui.barValue}>{value}</span>
    </div>
  )
}
