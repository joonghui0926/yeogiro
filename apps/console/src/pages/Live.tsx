import { RAIL_MODE_LABEL, STATE_LABEL, type RailMode } from '@yeogiro/contracts'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { CallerName } from '../components/Chips'
import ui from '../components/ui.module.css'
import { clock, hhmm, offset, toDate, won } from '../data/format'
import { completeOperatorJob, useCalls, useEvents, useFlags, useOperatorJobs, type WithId } from '../data/hooks'
import type { CallDoc, RailJobDoc } from '@yeogiro/contracts'
import styles from './live.module.css'

export function Live() {
  const [flags, update] = useFlags()
  const jobs = useOperatorJobs()
  const calls = useCalls(30)
  const live = (calls ?? []).filter((call) => call.status === 'live')

  return (
    <div className={ui.page}>
      <header className={ui.pageHead}>
        <div>
          <h1 className={ui.pageTitle}>실시간</h1>
          <p className={ui.pageSub}>진행 중인 통화와 대리 예약 요청, 운영 설정을 한곳에서 다뤄요.</p>
        </div>
      </header>

      {jobs && jobs.length > 0 && (
        <section className={ui.section}>
          <h2 className={ui.sectionTitle}>대리 예약 요청</h2>
          <p className={ui.sectionHint}>코레일+ 앱에서 이 열차를 예약하고 예약번호를 넣어 주세요. 어르신은 통화 중에 기다리고 있어요.</p>
          {jobs.map((job) => (
            <AssistCard key={job.id} job={job} />
          ))}
        </section>
      )}

      <section className={ui.section}>
        <h2 className={ui.sectionTitle}>진행 중인 통화</h2>
        {live.length === 0 ? (
          <div className={`${ui.card} ${ui.empty}`}>지금 진행 중인 통화가 없어요</div>
        ) : (
          live.map((call) => <LiveCall key={call.id} call={call} />)
        )}
      </section>

      <section className={ui.section}>
        <h2 className={ui.sectionTitle}>운영 설정</h2>
        <div className={`${ui.card} ${styles.settings}`}>
          <Setting title="예약 받기" detail="끄면 동의를 받아도 좌석을 잡지 않고 열차 정보만 문자로 보내요.">
            <Switch on={flags.bookingEnabled} onChange={(value) => void update({ bookingEnabled: value })} />
          </Setting>
          <Setting title="코레일 방식" detail="실예약은 조중휘 노트북의 작업자가 켜져 있어야 해요. 막히면 자동으로 모의로 내려가요.">
            <div className={styles.segmented}>
              {(['auto', 'assist', 'mock'] as RailMode[]).map((mode) => (
                <button
                  key={mode}
                  className={flags.railMode === mode ? styles.segmentOn : ''}
                  onClick={() => void update({ railMode: mode })}
                >
                  {RAIL_MODE_LABEL[mode]}
                </button>
              ))}
            </div>
          </Setting>
          <Setting title="매진 상황 만들기" detail="원하는 시간대 열차를 매진으로 보고 가장 가까운 대안을 제안해요. 시나리오 카드용.">
            <Switch on={flags.forceSoldOut} onChange={(value) => void update({ forceSoldOut: value })} />
          </Setting>
          <Setting title="전화 음질 모드" detail="테스터 마이크를 300~3400Hz로 깎아 실제 통화 조건에서 인식률을 봐요. 다음 통화부터 적용돼요.">
            <Switch on={flags.phoneBand} onChange={(value) => void update({ phoneBand: value })} />
          </Setting>
        </div>
      </section>
    </div>
  )
}

function LiveCall({ call }: { call: WithId<CallDoc> }) {
  const events = useEvents(call.id)
  const lines = (events ?? []).filter((e) => e.kind === 'user' || e.kind === 'ai').slice(-6)
  return (
    <Link to={`/calls/${call.id}`} className={`${ui.card} ${styles.liveCall}`}>
      <div className={styles.liveHead}>
        <strong>
          <CallerName call={call} />
        </strong>
        <span className={`${ui.chip} ${ui.chipInfo}`}>
          <span className={ui.liveDot} />
          {STATE_LABEL[call.state]}
        </span>
        <span className={ui.muted}>{clock(toDate(call.startedAt))} 시작</span>
      </div>
      <div className={styles.lines}>
        {lines.length === 0 && <p className={ui.muted}>연결 중</p>}
        {lines.map((line) =>
          line.kind === 'user' || line.kind === 'ai' ? (
            <p key={line.id} className={line.kind === 'user' ? styles.userLine : styles.aiLine}>
              <span>{offset(line.t)}</span>
              <b>{line.kind === 'user' ? '어르신' : 'AI'}</b>
              {line.text}
            </p>
          ) : null,
        )}
      </div>
    </Link>
  )
}

function AssistCard({ job }: { job: WithId<RailJobDoc> }) {
  const [pnr, setPnr] = useState('')
  const [seat, setSeat] = useState('')
  const [busy, setBusy] = useState(false)
  const train = job.payload.train

  const finish = async (outcome: Parameters<typeof completeOperatorJob>[1]) => {
    setBusy(true)
    await completeOperatorJob(job.id, outcome).finally(() => setBusy(false))
  }

  return (
    <div className={`${ui.card} ${styles.assist}`}>
      {train && (
        <div className={styles.assistTrain}>
          <span className={styles.assistRoute}>
            {train.dep} → {train.arr}
          </span>
          <span className={styles.assistTime}>
            {new Date(train.departsAt).getMonth() + 1}/{new Date(train.departsAt).getDate()} {hhmm(train.departsAt)} 출발
          </span>
          <span className={ui.muted}>
            {train.grade} {train.trainNo} · {job.payload.party ?? 1}명 {job.payload.senior ? '· 경로' : ''} ·{' '}
            {won(job.payload.fareTotal)}
          </span>
        </div>
      )}
      <div className={styles.assistForm}>
        <input className={ui.input} placeholder="예약번호" value={pnr} onChange={(e) => setPnr(e.target.value.trim())} inputMode="numeric" />
        <input className={ui.input} placeholder="좌석 (예: 3호차 7A)" value={seat} onChange={(e) => setSeat(e.target.value)} />
        <button className={ui.buttonPrimary} disabled={!pnr || busy} onClick={() => void finish({ pnr, seat: seat || undefined })}>
          예약 완료
        </button>
        <button className={ui.buttonDanger} disabled={busy} onClick={() => void finish({ error: '운영자가 예약하지 못함' })}>
          자리 없음
        </button>
      </div>
    </div>
  )
}

function Setting({ title, detail, children }: { title: string; detail: string; children: React.ReactNode }) {
  return (
    <div className={styles.setting}>
      <div>
        <strong>{title}</strong>
        <p>{detail}</p>
      </div>
      {children}
    </div>
  )
}

function Switch({ on, onChange }: { on: boolean; onChange: (value: boolean) => void }) {
  return (
    <button role="switch" aria-checked={on} className={on ? styles.switchOn : styles.switch} onClick={() => onChange(!on)}>
      <span />
    </button>
  )
}
