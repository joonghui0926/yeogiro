export type RailMode = 'auto' | 'assist' | 'mock'

export type CallState =
  | 'dialing'
  | 'greeting'
  | 'listening'
  | 'searching'
  | 'proposed'
  | 'holding'
  | 'payment_pending'
  | 'paid'
  | 'closing'
  | 'ended'

export type CallOutcome = 'booked' | 'declined' | 'abandoned' | 'no_consent' | 'payment_timeout' | 'cancelled'

export interface TrainSummary {
  trainNo: string
  grade: string
  dep: string
  arr: string
  departsAt: string
  arrivesAt: string
  fare: number
  seatsAvailable: boolean | null
}

export interface ItinerarySummary {
  kind: 'direct' | 'transfer'
  legs: TrainSummary[]
  transferCount: number
  transferStation: string | null
  waitMinutes: number
  durationMinutes: number
  fare: number | null
  seatAvailability: 'unknown' | 'available' | 'unavailable'
}

export interface BookingSummary {
  provider: 'korail' | 'assist' | 'mock'
  pnr: string
  fareTotal: number
  seat: string | null
  train: TrainSummary
  itinerary?: ItinerarySummary | null
  legHolds?: BookingSummary[]
}

export interface FirestoreTimestamp {
  toDate(): Date
}

export interface CallDoc {
  testerId: string
  testerLabel: string
  startedAt: FirestoreTimestamp
  endedAt?: FirestoreTimestamp
  status: 'live' | 'ended'
  state: CallState
  model: string
  voice: string
  railMode: RailMode
  phoneBand: boolean
  durationSec?: number
  outcome?: CallOutcome
  stoppedAt?: CallState | null
  reasks?: number
  interruptions?: number
  gateFailures?: number
  consentMisses?: number
  railSource?: string
  booking?: BookingSummary
  lastGate?: { passed: boolean; verdict: 'yes' | 'no' | 'unclear' }
}

export interface GateCheck {
  code: string
  label: string
  passed: boolean
}

interface EventBase {
  t: number
  at: FirestoreTimestamp
}

export type CallEvent = EventBase &
  (
    | { kind: 'user' | 'ai'; text: string }
    | { kind: 'tool_call'; name: string; args: Record<string, unknown> }
    | { kind: 'tool_result'; name: string; result: Record<string, unknown> | null; ms: number }
    | {
        kind: 'gate'
        passed: boolean
        verdict: 'yes' | 'no' | 'unclear'
        reason: string
        replies: string[]
        checks: GateCheck[]
      }
    | { kind: 'state'; state: CallState }
    | ({ kind: 'hold' } & BookingSummary)
    | { kind: 'hold_failed'; reason: string }
    | { kind: 'payment'; status: 'requested' | 'approved' | 'expired'; amount?: number }
    | { kind: 'message'; body: string }
    | { kind: 'cancel'; reason: string; provider: string }
    | { kind: 'interrupt' }
    | { kind: 'silence'; action: 'nudge' | 'hangup' }
    | { kind: 'error'; where: string; message: string }
    | { kind: 'client'; ua?: string; audio?: string; mic?: string }
  )

export interface TesterDoc {
  label: string
  alias: string
  homeStation: string | null
  senior: boolean | null
  token: string
}

export interface RuntimeFlags {
  bookingEnabled: boolean
  railMode: RailMode
  forceSoldOut: boolean
  phoneBand: boolean
}

export interface RailJobDoc {
  kind: 'search' | 'hold' | 'cancel'
  handler: 'worker' | 'operator'
  status: 'pending' | 'claimed' | 'done' | 'failed' | 'expired'
  callId: string
  createdAt?: FirestoreTimestamp
  payload: {
    train?: TrainSummary
    party?: number
    senior?: boolean
    fareTotal?: number
    hold?: { pnr: string; train: TrainSummary; fareTotal: number }
  }
  result?: Record<string, unknown>
}

export interface PaymentRequest {
  id: string
  amount: number
  merchant: string
  item: string
  payer: string
}

export interface InboxMessage {
  id: string
  sender: string
  body: string
  sentAt: string
}

export type PhoneEvent =
  | { type: 'payment.requested'; payment: PaymentRequest }
  | { type: 'payment.expired'; paymentId: string }
  | { type: 'message.received'; message: InboxMessage }
  | { type: 'call.ended'; by: string }

export const RAIL_MODE_LABEL: Record<RailMode, string> = {
  auto: '코레일 실예약',
  assist: '운영자 대리',
  mock: '모의',
}

export const STATE_LABEL: Record<CallState, string> = {
  dialing: '발신',
  greeting: '첫마디',
  listening: '듣는 중',
  searching: '조회',
  proposed: '제안',
  holding: '좌석 확보',
  payment_pending: '결제 대기',
  paid: '결제 완료',
  closing: '마무리',
  ended: '종료',
}

export const OUTCOME_LABEL: Record<CallOutcome, string> = {
  booked: '예약 완료',
  declined: '예약 안 함',
  abandoned: '중단',
  no_consent: '동의 없음',
  payment_timeout: '결제 안 함',
  cancelled: '취소',
}
