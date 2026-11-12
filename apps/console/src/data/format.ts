import type { FirestoreTimestamp } from '@yeogiro/contracts'

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토']

export function toDate(value: FirestoreTimestamp | undefined | null): Date | null {
  return value ? value.toDate() : null
}

export function clock(date: Date | null): string {
  if (!date) return '–'
  const hour = date.getHours()
  return `${hour < 12 ? '오전' : '오후'} ${hour % 12 || 12}:${String(date.getMinutes()).padStart(2, '0')}`
}

export function day(date: Date | null): string {
  if (!date) return '–'
  return `${date.getMonth() + 1}월 ${date.getDate()}일 (${WEEKDAYS[date.getDay()]})`
}

export function when(date: Date | null): string {
  if (!date) return '–'
  const today = new Date()
  const sameDay = date.toDateString() === today.toDateString()
  return sameDay ? clock(date) : `${date.getMonth() + 1}/${date.getDate()} ${clock(date)}`
}

export function duration(seconds: number | undefined): string {
  if (seconds === undefined) return '–'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m ? `${m}분 ${String(s).padStart(2, '0')}초` : `${s}초`
}

export function offset(ms: number): string {
  const total = Math.floor(ms / 1000)
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}

export function won(amount: number | undefined): string {
  return amount === undefined ? '–' : `${amount.toLocaleString('ko-KR')}원`
}

export function hhmm(iso: string | undefined): string {
  if (!iso) return '–'
  const date = new Date(iso)
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}
