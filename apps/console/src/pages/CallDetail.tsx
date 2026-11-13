import { STATE_LABEL, type CallEvent, type GateCheck, type TrainSummary } from '@yeogiro/contracts'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ModeChip, OutcomeChip } from '../components/Chips'
import ui from '../components/ui.module.css'
import { deleteCallRecord } from '../data/actions'
import { isDemo } from '../data/demo'
import { clock, day, duration, hhmm, offset, toDate, won } from '../data/format'
import { useCallDoc, useEvents, type WithId } from '../data/hooks'
import styles from './detail.module.css'

type Item =
  | { type: 'speech'; key: string; t: number; who: 'ai' | 'user'; text: string }
  | { type: 'tool'; key: string; t: number; name: string; args: Record<string, unknown>; result?: Record<string, unknown> | null; ms?: number }
  | { type: 'gate'; key: string; t: number; event: Extract<CallEvent, { kind: 'gate' }> }
  | { type: 'mark'; key: string; t: number; tone: 'plain' | 'good' | 'warn' | 'bad'; text: string }

export function CallDetail() {
  const { callId } = useParams()
  const call = useCallDoc(callId)
  const events = useEvents(callId)
  const [pane, setPane] = useState<'timeline' | 'summary'>('timeline')
  const navigate = useNavigate()

  if (call === undefined || events === null) return <div className={ui.empty}>불러오는 중</div>
  if (call === null) return <div className={ui.empty}>통화를 찾을 수 없어요</div>

  const items = toItems(events)
  const gate = [...events].reverse().find((e): e is WithId<Extract<CallEvent, { kind: 'gate' }>> => e.kind === 'gate')
  const proposal = lastProposal(events)
  const train = call.booking?.train ?? proposal?.train
  const payment = [...events].reverse().find((e) => e.kind === 'payment') as Extract<CallEvent, { kind: 'payment' }> | undefined
  const started = toDate(call.startedAt)

  return (
    <div className={ui.page}>
      <header className={styles.head}>
        <Link to="/calls" className={styles.back}>
          ← 통화
        </Link>
        <h1 className={ui.pageTitle}>
          {call.testerLabel} · {day(started)} {clock(started)}
        </h1>
        <div className={styles.headRow}>
          <div className={styles.headChips}>
            <OutcomeChip call={call} />
            <ModeChip call={call} />
            {call.status === 'ended' && <span className={ui.chip}>{duration(call.durationSec)}</span>}
          </div>
          {call.status === 'ended' && !isDemo() && (
            <DeleteCall callId={call.id} onDeleted={() => navigate('/calls', { replace: true })} />
          )}
        </div>
      </header>

      <div className={styles.segment}>
        <button className={pane === 'timeline' ? styles.segmentOn : ''} onClick={() => setPane('timeline')}>
          대화
        </button>
        <button className={pane === 'summary' ? styles.segmentOn : ''} onClick={() => setPane('summary')}>
          판정과 요약
        </button>
      </div>

      <div className={styles.layout} data-pane={pane}>
        <section className={styles.timeline}>
          {items.length === 0 && <p className={ui.empty}>아직 기록이 없어요</p>}
          {items.map((item) => (
            <TimelineItem key={item.key} item={item} />
          ))}
        </section>

        <aside className={styles.summary}>
          <Panel title="열차">
            {train ? (
              <TrainCard train={train} fare={call.booking?.fareTotal ?? proposal?.fareTotal} />
            ) : (
              <p className={ui.muted}>제안 전에 끝났어요</p>
            )}
            {call.booking && (
              <dl className={styles.facts}>
                <dt>예약번호</dt>
                <dd className="num">{call.booking.pnr}</dd>
                <dt>좌석</dt>
                <dd>{call.booking.seat ?? '배정 전'}</dd>
              </dl>
            )}
          </Panel>

          <Panel title="동의 판정">
            {gate ? <GateList checks={gate.checks} /> : <p className={ui.muted}>예약 요청이 없었어요</p>}
            {gate && (
              <p className={styles.verdict}>
                “{gate.replies.join(' / ') || '발화 없음'}” → {verdictLabel(gate.verdict)}
                <span>{gate.reason}</span>
              </p>
            )}
          </Panel>

          <Panel title="결제">
            <p className={payment?.status === 'approved' ? ui.good : ui.muted} style={{ margin: 0 }}>
              {payment ? paymentLabel(payment.status) : '요청 없음'}
              {payment?.amount ? ` · ${won(payment.amount)}` : ''}
            </p>
          </Panel>

          <Panel title="지표">
            <dl className={styles.facts}>
              <dt>되묻기</dt>
              <dd className="num">{call.reasks ?? 0}회</dd>
              <dt>끼어들기</dt>
              <dd className="num">{call.interruptions ?? 0}회</dd>
              <dt>게이트 차단</dt>
              <dd className="num">{call.gateFailures ?? 0}회</dd>
              <dt>멈춘 지점</dt>
              <dd>{call.stoppedAt ? STATE_LABEL[call.stoppedAt] : call.status === 'live' ? '진행 중' : '없음'}</dd>
            </dl>
          </Panel>

          <Panel title="설정">
            <dl className={styles.facts}>
              <dt>음성 모델</dt>
              <dd>{call.model}</dd>
              <dt>목소리</dt>
              <dd>{call.voice}</dd>
              <dt>전화 음질</dt>
              <dd>{call.phoneBand ? '켜짐' : '꺼짐'}</dd>
            </dl>
          </Panel>
        </aside>
      </div>
    </div>
  )
}

function TimelineItem({ item }: { item: Item }) {
  const time = <span className={styles.time}>{offset(item.t)}</span>
  if (item.type === 'speech') {
    return (
      <div className={item.who === 'user' ? styles.userLine : styles.aiLine}>
        {time}
        <span className={styles.who}>{item.who === 'user' ? '어르신' : 'AI'}</span>
        <p className={styles.text}>{item.text}</p>
      </div>
    )
  }
  if (item.type === 'tool') {
    const say = typeof item.result?.say === 'string' ? item.result.say : null
    return (
      <div className={styles.block}>
        {time}
        <div className={styles.blockBody}>
          <div className={styles.blockHead}>
            <code>{item.name}</code>
            {item.ms !== undefined && <span className={ui.muted}>{item.ms.toLocaleString()}ms</span>}
          </div>
          <ArgList args={item.args} />
          {say && <p className={styles.say}>“{say}”</p>}
          {item.result && (
            <details className={styles.raw}>
              <summary>응답 원문</summary>
              <pre>{JSON.stringify(item.result, null, 2)}</pre>
            </details>
          )}
        </div>
      </div>
    )
  }
  if (item.type === 'gate') {
    return (
      <div className={`${styles.block} ${item.event.passed ? styles.blockGood : styles.blockBad}`}>
        {time}
        <div className={styles.blockBody}>
          <div className={styles.blockHead}>
            <strong>{item.event.passed ? '동의 게이트 통과' : '동의 게이트에서 막힘'}</strong>
            <span className={ui.muted}>{verdictLabel(item.event.verdict)}</span>
          </div>
          <GateList checks={item.event.checks} compact />
        </div>
      </div>
    )
  }
  return (
    <div className={`${styles.mark} ${styles[`mark_${item.tone}`]}`}>
      {time}
      <span>{item.text}</span>
    </div>
  )
}

function ArgList({ args }: { args: Record<string, unknown> }) {
  const entries = Object.entries(args).filter(([, value]) => value !== null && value !== '' && value !== undefined)
  if (entries.length === 0) return null
  return (
    <div className={styles.args}>
      {entries.map(([key, value]) => (
        <span key={key} className={styles.arg}>
          <em>{key}</em> {String(value)}
        </span>
      ))}
    </div>
  )
}

function GateList({ checks, compact = false }: { checks: GateCheck[]; compact?: boolean }) {
  return (
    <ul className={compact ? styles.gateCompact : styles.gate}>
      {checks.map((check) => (
        <li key={check.code} className={check.passed ? styles.pass : styles.fail}>
          <span aria-hidden="true">{check.passed ? '✓' : '✕'}</span>
          {check.label}
        </li>
      ))}
    </ul>
  )
}

function TrainCard({ train, fare }: { train: TrainSummary; fare?: number }) {
  return (
    <div className={styles.train}>
      <div className={styles.trainRoute}>
        <span>
          <strong className="num">{hhmm(train.departsAt)}</strong>
          {train.dep}
        </span>
        <span className={styles.trainLine} />
        <span>
          <strong className="num">{hhmm(train.arrivesAt)}</strong>
          {train.arr}
        </span>
      </div>
      <p className={styles.trainMeta}>
        {train.grade} {train.trainNo} · {new Date(train.departsAt).getMonth() + 1}/{new Date(train.departsAt).getDate()} ·{' '}
        {won(fare ?? train.fare)}
      </p>
    </div>
  )
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className={styles.panel}>
      <h3>{title}</h3>
      {children}
    </section>
  )
}

const AUDIO_LABEL: Record<string, string> = {
  element: '소리 재생됨',
  webaudio: '소리 재생됨(대체 경로)',
  waiting: '소리 아직 안 나옴',
  failed: '소리 재생 막힘',
}

const MIC_LABEL: Record<string, string> = {
  live: '마이크 켜짐',
  muted: '마이크 신호 없음',
  ended: '마이크 끊김',
}

function browserLabel(ua = ''): string {
  if (/KAKAOTALK/i.test(ua)) return '카카오톡 안 브라우저'
  if (/SamsungBrowser/i.test(ua)) return '삼성 인터넷'
  if (/; wv\)/.test(ua)) return '앱 안 브라우저'
  if (/CriOS|Chrome/i.test(ua)) return '크롬'
  if (/Safari/i.test(ua)) return '사파리'
  return '알 수 없는 브라우저'
}

function DeleteCall({ callId, onDeleted }: { callId: string; onDeleted: () => void }) {
  const [step, setStep] = useState<'idle' | 'confirm' | 'busy' | 'failed'>('idle')

  const remove = async () => {
    setStep('busy')
    try {
      await deleteCallRecord(callId)
      onDeleted()
    } catch {
      setStep('failed')
    }
  }

  if (step === 'idle') {
    return (
      <button className={styles.deleteLink} onClick={() => setStep('confirm')}>
        기록 삭제
      </button>
    )
  }

  return (
    <div className={styles.confirm} role="alertdialog" aria-label="통화 기록 삭제">
      <span>{step === 'failed' ? '지우지 못했어요. 다시 해 볼까요?' : '이 통화 기록을 지울까요? 되돌릴 수 없어요.'}</span>
      <button className={ui.buttonDanger} disabled={step === 'busy'} onClick={() => void remove()}>
        {step === 'busy' ? '지우는 중' : '지우기'}
      </button>
      <button className={ui.button} disabled={step === 'busy'} onClick={() => setStep('idle')}>
        취소
      </button>
    </div>
  )
}

function toItems(events: WithId<CallEvent>[]): Item[] {
  const items: Item[] = []
  const openTools = new Map<string, Extract<Item, { type: 'tool' }>>()
  for (const event of events) {
    const key = event.id
    switch (event.kind) {
      case 'ai':
      case 'user':
        items.push({ type: 'speech', key, t: event.t, who: event.kind, text: event.text })
        break
      case 'tool_call': {
        const item: Extract<Item, { type: 'tool' }> = { type: 'tool', key, t: event.t, name: event.name, args: event.args }
        openTools.set(event.name, item)
        items.push(item)
        break
      }
      case 'tool_result': {
        const open = openTools.get(event.name)
        if (open) {
          open.result = event.result
          open.ms = event.ms
          openTools.delete(event.name)
        }
        break
      }
      case 'gate':
        items.push({ type: 'gate', key, t: event.t, event })
        break
      case 'state':
        if (['proposed', 'holding', 'payment_pending', 'paid'].includes(event.state)) {
          items.push({ type: 'mark', key, t: event.t, tone: 'plain', text: `단계 · ${STATE_LABEL[event.state]}` })
        }
        break
      case 'hold':
        items.push({ type: 'mark', key, t: event.t, tone: 'good', text: `좌석 확보 · 예약번호 ${event.pnr} · ${providerLabel(event.provider)}` })
        break
      case 'hold_failed':
        items.push({ type: 'mark', key, t: event.t, tone: 'bad', text: `좌석 확보 실패 · ${event.reason}` })
        break
      case 'payment':
        items.push({
          type: 'mark',
          key,
          t: event.t,
          tone: event.status === 'approved' ? 'good' : event.status === 'expired' ? 'warn' : 'plain',
          text: `${paymentLabel(event.status)}${event.amount ? ` · ${won(event.amount)}` : ''}`,
        })
        break
      case 'message':
        items.push({ type: 'mark', key, t: event.t, tone: 'plain', text: `문자 발송 · ${event.body.split('\n')[0]}` })
        break
      case 'cancel':
        items.push({ type: 'mark', key, t: event.t, tone: 'warn', text: `예약 취소 · ${cancelLabel(event.reason)}` })
        break
      case 'trip_dropped':
        items.push({ type: 'mark', key, t: event.t, tone: 'warn', text: `안 가기로 함${event.heard ? ` · “${event.heard}”` : ''}` })
        break
      case 'interrupt':
        items.push({ type: 'mark', key, t: event.t, tone: 'plain', text: '어르신이 말을 끊음' })
        break
      case 'silence':
        items.push({ type: 'mark', key, t: event.t, tone: 'warn', text: event.action === 'nudge' ? '침묵 7초 · 안내' : '침묵 · 종료' })
        break
      case 'error':
        items.push({ type: 'mark', key, t: event.t, tone: 'bad', text: `오류 · ${event.where} · ${event.message.slice(0, 120)}` })
        break
      case 'client': {
        const healthy = (event.audio === 'element' || event.audio === 'webaudio') && event.mic === 'live'
        const text = `단말 · ${browserLabel(event.ua)} · ${AUDIO_LABEL[event.audio ?? ''] ?? '재생 상태 모름'} · ${MIC_LABEL[event.mic ?? ''] ?? '마이크 상태 모름'}`
        items.push({ type: 'mark', key, t: event.t, tone: healthy ? 'plain' : 'bad', text })
        break
      }
    }
  }
  return items
}

function lastProposal(events: CallEvent[]): { train: TrainSummary; fareTotal?: number } | null {
  for (const event of [...events].reverse()) {
    if (event.kind === 'tool_result' && event.name === 'find_trains' && event.result?.train) {
      const train = event.result.train as TrainSummary & { fareTotal?: number }
      return { train, fareTotal: train.fareTotal }
    }
  }
  return null
}

function verdictLabel(verdict: 'yes' | 'no' | 'unclear'): string {
  return { yes: '동의', no: '거절', unclear: '불분명' }[verdict]
}

function paymentLabel(status: 'requested' | 'approved' | 'expired'): string {
  return { requested: '결제 요청', approved: '결제 승인', expired: '결제 시간 초과' }[status]
}

function providerLabel(provider: string): string {
  return provider === 'korail' ? '코레일 실예약' : provider === 'assist' ? '운영자 대리' : '모의'
}

function cancelLabel(reason: string): string {
  return (
    { call_ended: '통화 종료 후 자동', caller_request: '어르신 요청', caller_dropped_trip: '어르신이 안 가기로 함', payment_timeout: '결제 안 함' }[reason] ?? reason
  )
}
