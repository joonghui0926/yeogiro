import type { BookingSummary, CallDoc, CallEvent, RailJobDoc, TesterDoc } from '@yeogiro/contracts'
import type { WithId } from './hooks'

/** Synthetic data for screenshots, offline review, and a presentation fallback. ?demo=1 enables it. */
export function isDemo(): boolean {
  try {
    return new URLSearchParams(window.location.search).get('demo') === '1'
  } catch {
    return false
  }
}

const ts = (d: Date) => ({ toDate: () => d })
const ago = (min: number) => ts(new Date(Date.now() - min * 60_000))

type Row = {
  id: string
  tester: string
  startMin: number
  dur?: number
  outcome?: CallDoc['outcome']
  state: CallDoc['state']
  status: CallDoc['status']
  reasks?: number
  interruptions?: number
  gateFailures?: number
  stoppedAt?: CallDoc['stoppedAt']
  mode?: CallDoc['railMode']
  source?: string
}

const ROWS: Row[] = [
  { id: 'd1', tester: '테스터 3', startMin: 4, state: 'proposed', status: 'live' },
  { id: 'd2', tester: '테스터 1', startMin: 22, dur: 41, outcome: 'booked', state: 'ended', status: 'ended', reasks: 0, source: 'korail' },
  { id: 'd3', tester: '테스터 5', startMin: 58, dur: 63, outcome: 'booked', state: 'ended', status: 'ended', reasks: 1 },
  { id: 'd4', tester: '테스터 2', startMin: 96, dur: 88, outcome: 'booked', state: 'ended', status: 'ended', reasks: 2 },
  { id: 'd5', tester: '테스터 7', startMin: 140, dur: 34, outcome: 'declined', state: 'ended', status: 'ended', reasks: 1 },
  { id: 'd6', tester: '테스터 4', startMin: 190, dur: 52, outcome: 'booked', state: 'ended', status: 'ended', reasks: 0, source: 'korail' },
  { id: 'd7', tester: '테스터 6', startMin: 240, dur: 29, outcome: 'abandoned', state: 'ended', status: 'ended', reasks: 0, stoppedAt: 'searching' },
  { id: 'd8', tester: '테스터 8', startMin: 300, dur: 71, outcome: 'payment_timeout', state: 'ended', status: 'ended', reasks: 1, stoppedAt: 'payment_pending' },
  { id: 'd9', tester: '테스터 1', startMin: 360, dur: 46, outcome: 'booked', state: 'ended', status: 'ended', reasks: 0 },
  { id: 'd10', tester: '테스터 5', startMin: 420, dur: 38, outcome: 'booked', state: 'ended', status: 'ended', reasks: 1, source: 'korail' },
  { id: 'd11', tester: '테스터 2', startMin: 500, dur: 55, outcome: 'cancelled', state: 'ended', status: 'ended', reasks: 0 },
  { id: 'transfer', tester: '환승 모의 테스트', startMin: 600, dur: 120, outcome: 'booked', state: 'ended', status: 'ended' },
]

const TRAIN = {
  trainNo: '119',
  grade: 'KTX',
  dep: '대전',
  arr: '서울',
  departsAt: new Date(Date.now() + 4 * 86_400_000).toISOString(),
  arrivesAt: new Date(Date.now() + 4 * 86_400_000 + 64 * 60_000).toISOString(),
  fare: 23700,
  seatsAvailable: true,
}

const TRANSFER_LEGS = [
  { ...TRAIN, dep: '대전', arr: '서울', departsAt: '2026-11-17T09:00:00+09:00', arrivesAt: '2026-11-17T10:00:00+09:00', fare: 23700, seatsAvailable: null },
  { ...TRAIN, trainNo: '901', dep: '서울', arr: '강릉', departsAt: '2026-11-17T10:30:00+09:00', arrivesAt: '2026-11-17T12:30:00+09:00', fare: 27600, seatsAvailable: null },
]
const TRANSFER_BOOKING: BookingSummary = {
  provider: 'mock', pnr: '구간별 별도 예약', fareTotal: 51300, seat: null, train: TRANSFER_LEGS[0],
  itinerary: { kind: 'transfer', legs: TRANSFER_LEGS, transferCount: 1, transferStation: '서울', waitMinutes: 30, durationMinutes: 210, fare: 51300, seatAvailability: 'unknown' },
  legHolds: TRANSFER_LEGS.map((train, index) => ({ provider: 'mock', pnr: `MOCK-${index + 1}`, fareTotal: train.fare, seat: '모의 3호차 7A', train })),
}

export const demoCalls: WithId<CallDoc>[] = ROWS.map((r) => ({
  id: r.id,
  testerId: r.tester,
  testerLabel: r.tester,
  startedAt: ago(r.startMin),
  endedAt: r.dur ? ago(r.startMin - r.dur / 60) : undefined,
  status: r.status,
  state: r.state,
  model: 'gpt-realtime-2.1',
  voice: 'marin',
  railMode: r.mode ?? 'mock',
  phoneBand: false,
  durationSec: r.dur,
  outcome: r.outcome,
  stoppedAt: r.stoppedAt ?? null,
  reasks: r.reasks,
  interruptions: r.interruptions ?? 0,
  gateFailures: r.gateFailures ?? 0,
  railSource: r.source ?? 'tago',
  booking:
    r.id === 'transfer' ? TRANSFER_BOOKING : r.outcome === 'booked'
      ? { provider: (r.source === 'korail' ? 'korail' : 'mock') as 'korail' | 'mock', pnr: '7429••••03', fareTotal: 16500, seat: '3호차 7A', train: TRAIN }
      : undefined,
  lastGate: r.outcome === 'no_consent' ? { passed: false, verdict: 'unclear' } : undefined,
}))

export function demoEvents(callId: string): WithId<CallEvent>[] {
  if (callId === 'transfer') return [
    ev('t1', 1000, { kind: 'user', text: '대전에서 강릉까지 환승으로 찾아 주세요.' }),
    ev('t1a', 1500, { kind: 'tool_call', name: 'find_trains', args: { departure: '대전', arrival: '강릉', prefer_transfer: true } }),
    ev('t2', 2000, { kind: 'tool_result', name: 'find_trains', ms: 100, result: { status: 'transfer_found', train: TRANSFER_LEGS[0], itinerary: TRANSFER_BOOKING.itinerary, say: '화면 검토용 가상 시간표입니다. 서울역에서 한 번 갈아타며 대기시간은 삼십 분이에요. 첫 열차는 오전 아홉 시 대전 출발, 열 시 서울 도착. 두 번째 열차는 열 시 삼십 분 서울 출발, 오후 열두 시 삼십 분 강릉 도착이에요. 예상 합계 오만 천삼백 원이며 좌석은 미확인이에요. 두 구간을 별도로 모의 예약할까요?' } }),
    ev('t3', 65000, { kind: 'user', text: '네, 두 구간 모두 모의 예약해 주세요.' }),
    ev('t3a', 65500, { kind: 'gate', passed: true, verdict: 'yes', reason: '화면 검토용 모의 동의 결과: 두 구간 전체에 동의', replies: ['네, 두 구간 모두 모의 예약해 주세요.'], checks: [{ code: 'heard', label: '전체 여정을 끝까지 들음', passed: true }, { code: 'consent', label: '전체 여정에 명확한 동의', passed: true }] }),
    ev('t4', 66000, { kind: 'hold', ...TRANSFER_BOOKING }),
    ev('t5', 67000, { kind: 'payment', status: 'approved', amount: 51300 }),
  ]
  if (callId !== 'd4') return baseEvents()
  return baseEvents()
}

function ev(id: string, t: number, e: Record<string, unknown>): WithId<CallEvent> {
  return { id, t, at: ago(96), ...e } as unknown as WithId<CallEvent>
}

function baseEvents(): WithId<CallEvent>[] {
  const G = {
    checks: [
      { code: 'option', label: '이번 통화의 최근 제안, 3분 이내', passed: true },
      { code: 'heard', label: '제안을 끝까지 들음', passed: true },
      { code: 'consent', label: '명확한 동의', passed: true },
      { code: 'tester', label: '등록된 테스터', passed: true },
      { code: 'limits', label: '하루 3건, 동시 1건 이하', passed: true },
      { code: 'lead', label: '출발 20분 전', passed: true },
      { code: 'duplicate', label: '같은 열차 중복 없음', passed: true },
      { code: 'switch', label: '예약 스위치 켜짐', passed: true },
    ],
  }
  return [
    ev('e1', 1200, { kind: 'ai', text: '여기로 기차 예약 AI예요. 어디로, 언제 가세요?' }),
    ev('e2', 9800, { kind: 'user', text: '담주 화요일 오후에 서울 좀 가려고' }),
    ev('e3', 10500, { kind: 'ai', text: '잠시만요, 찾아볼게요.' }),
    ev('e4', 10700, { kind: 'tool_call', name: 'find_trains', args: { arrival: '서울', relative_day: 'next_week', weekday: 'tue', part_of_day: 'afternoon' } }),
    ev('e5', 10760, { kind: 'tool_result', name: 'find_trains', result: { need: 'senior', say: '만 65세 넘으셨어요?' }, ms: 3 }),
    ev('e6', 11800, { kind: 'ai', text: '만 65세 넘으셨어요?' }),
    ev('e7', 17200, { kind: 'user', text: '일흔 셋이여' }),
    ev('e8', 17600, { kind: 'tool_call', name: 'set_senior', args: { is_senior: true } }),
    ev('e9', 17700, { kind: 'tool_result', name: 'set_senior', result: { say: '17일 화요일 대전에서 서울, KTX 오후 두 시 육 분 출발, 오후 세 시 십 분 도착, 경로 할인해서 만 육천오백 원이에요. 예약할까요?', train: { ...TRAIN, fareTotal: 16500 } }, ms: 2 }),
    ev('e10', 20400, { kind: 'ai', text: '17일 화요일 대전에서 서울, KTX 오후 두 시 육 분 출발, 오후 세 시 십 분 도착, 경로 할인해서 만 육천오백 원이에요. 예약할까요?' }),
    ev('e11', 28800, { kind: 'user', text: '응 그렇게 해 줘' }),
    ev('e12', 29100, { kind: 'ai', text: '네.' }),
    ev('e13', 29200, { kind: 'tool_call', name: 'request_booking', args: { option_id: 'opt_7f3a1c' } }),
    ev('e14', 29700, { kind: 'gate', passed: true, verdict: 'yes', reason: "'응 그렇게 해 줘'는 분명한 동의 표현이라 yes로 판정.", replies: ['응 그렇게 해 줘'], ...G }),
    ev('e15', 29760, { kind: 'hold', provider: 'mock', pnr: '7429••••03', fareTotal: 16500, seat: '3호차 7A', train: TRAIN }),
    ev('e16', 29900, { kind: 'payment', status: 'requested', amount: 16500 }),
    ev('e17', 30400, { kind: 'ai', text: '화면에 노란 결제 버튼이 나왔어요. 눌러 주세요.' }),
    ev('e18', 36800, { kind: 'payment', status: 'approved', amount: 16500 }),
    ev('e19', 37600, { kind: 'ai', text: '결제됐어요. 문자로 표 보내드렸어요. 더 필요하신 거 있으세요?' }),
    ev('e20', 39800, { kind: 'message', body: '[여기로] 예약 확인\n11월 17일(화) 대전→서울\nKTX 119 14:06 출발 · 15:10 도착\n3호차 7A · 16,500원' }),
    ev('e21', 44200, { kind: 'user', text: '없어요 고마워요' }),
    ev('e22', 44600, { kind: 'ai', text: '조심히 다녀오세요.' }),
  ]
}

export const demoTesters: WithId<TesterDoc>[] = Array.from({ length: 8 }, (_, i) => ({
  id: `t${i + 1}`,
  label: `테스터 ${i + 1}`,
  alias: ['김순자', '이영수', '박정희', '최명숙', '정만복', '강옥순', '조병철', '윤금자'][i],
  homeStation: '대전',
  senior: i % 2 === 0 ? true : null,
  token: `demo${i + 1}`,
}))

export const demoOperatorJobs: WithId<RailJobDoc>[] = []
