import type { CallDoc, CallEvent, RailJobDoc, RuntimeFlags, TesterDoc } from '@yeogiro/contracts'
import {
  collection,
  doc,
  limit,
  onSnapshot,
  orderBy,
  query,
  setDoc,
  updateDoc,
  where,
  type DocumentData,
  type Query,
} from 'firebase/firestore'
import { useEffect, useState } from 'react'
import { auth, db } from '../app/firebase'
import { demoCalls, demoEvents, demoOperatorJobs, demoTesters, isDemo } from './demo'

export type WithId<T> = T & { id: string }

function useQuery<T>(build: () => Query<DocumentData> | null, deps: unknown[]): WithId<T>[] | null {
  const [rows, setRows] = useState<WithId<T>[] | null>(null)
  useEffect(() => {
    const q = build()
    if (!q) return
    return onSnapshot(
      q,
      (snapshot) => setRows(snapshot.docs.map((d) => ({ id: d.id, ...(d.data() as T) }))),
      () => setRows([]),
    )
  }, deps)
  return rows
}

export function useCalls(max = 300) {
  const live = useQuery<CallDoc>(
    () => (isDemo() ? null : query(collection(db, 'calls'), orderBy('startedAt', 'desc'), limit(max))),
    [max],
  )
  return isDemo() ? demoCalls.slice(0, max) : live
}

export function useCallDoc(callId: string | undefined) {
  const [call, setCall] = useState<WithId<CallDoc> | null | undefined>(undefined)
  useEffect(() => {
    if (!callId || isDemo()) return
    return onSnapshot(doc(db, 'calls', callId), (snapshot) =>
      setCall(snapshot.exists() ? { id: snapshot.id, ...(snapshot.data() as CallDoc) } : null),
    )
  }, [callId])
  if (isDemo()) return demoCalls.find((c) => c.id === callId) ?? null
  return call
}

export function useEvents(callId: string | undefined) {
  const live = useQuery<CallEvent>(
    () => (callId && !isDemo() ? query(collection(db, 'calls', callId, 'events'), orderBy('t', 'asc')) : null),
    [callId],
  )
  return isDemo() ? (callId ? demoEvents(callId) : []) : live
}

export function useTesters() {
  const live = useQuery<TesterDoc>(() => (isDemo() ? null : query(collection(db, 'testers'), orderBy('label'))), [])
  return isDemo() ? demoTesters : live
}

export function useOperatorJobs() {
  const live = useQuery<RailJobDoc>(
    () =>
      isDemo()
        ? null
        : query(
        collection(db, 'railJobs'),
        where('handler', '==', 'operator'),
        where('status', '==', 'pending'),
        orderBy('createdAt', 'asc'),
      ),
    [],
  )
  return isDemo() ? demoOperatorJobs : live
}

const DEFAULT_FLAGS: RuntimeFlags = { bookingEnabled: true, railMode: 'mock', forceSoldOut: false, phoneBand: false }

export function useFlags(): [RuntimeFlags, (patch: Partial<RuntimeFlags>) => Promise<void>] {
  const [flags, setFlags] = useState<RuntimeFlags>(DEFAULT_FLAGS)
  useEffect(
    () =>
      onSnapshot(doc(db, 'config', 'runtime'), (snapshot) =>
        setFlags({ ...DEFAULT_FLAGS, ...(snapshot.data() as Partial<RuntimeFlags> | undefined) }),
      ),
    [],
  )
  const update = (patch: Partial<RuntimeFlags>) => setDoc(doc(db, 'config', 'runtime'), patch, { merge: true })
  return [flags, update]
}

export async function completeOperatorJob(
  jobId: string,
  outcome: { pnr: string; seat?: string; fareTotal?: number } | { error: string },
) {
  const operator = auth.currentUser?.email ?? 'unknown'
  if ('error' in outcome) {
    await updateDoc(doc(db, 'railJobs', jobId), { status: 'failed', error: outcome.error, operator })
    return
  }
  await updateDoc(doc(db, 'railJobs', jobId), { status: 'done', result: outcome, operator })
}
