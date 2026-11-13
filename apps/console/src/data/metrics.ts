import type { CallDoc, CallOutcome, CallState } from '@yeogiro/contracts'
import type { WithId } from './hooks'

export interface Summary {
  total: number
  booked: number
  completionRate: number | null
  avgReasks: number | null
  unconsented: number
  gateBlocks: number
  avgDuration: number | null
  outcomes: Array<[CallOutcome, number]>
  stops: Array<[CallState, number]>
}

const OUTCOME_ORDER: CallOutcome[] = ['booked', 'declined', 'abandoned', 'no_consent', 'payment_timeout', 'cancelled']

export function summarize(calls: WithId<CallDoc>[]): Summary {
  const ended = calls.filter((c) => c.status === 'ended')
  const booked = ended.filter((c) => c.outcome === 'booked')
  const outcomes = new Map<CallOutcome, number>()
  const stops = new Map<CallState, number>()
  for (const call of ended) {
    if (call.outcome) outcomes.set(call.outcome, (outcomes.get(call.outcome) ?? 0) + 1)
    if (call.stoppedAt) stops.set(call.stoppedAt, (stops.get(call.stoppedAt) ?? 0) + 1)
  }
  const average = (values: number[]) => (values.length ? values.reduce((a, b) => a + b, 0) / values.length : null)

  return {
    total: ended.length,
    booked: booked.length,
    completionRate: ended.length ? booked.length / ended.length : null,
    avgReasks: average(booked.map((c) => c.reasks ?? 0)),
    unconsented: ended.filter((c) => c.booking && c.lastGate && c.lastGate.verdict !== 'yes').length,
    gateBlocks: ended.reduce((sum, c) => sum + (c.gateFailures ?? 0), 0),
    avgDuration: average(ended.map((c) => c.durationSec ?? 0)),
    outcomes: OUTCOME_ORDER.filter((o) => outcomes.has(o)).map((o) => [o, outcomes.get(o) ?? 0]),
    stops: [...stops.entries()].sort((a, b) => b[1] - a[1]),
  }
}
