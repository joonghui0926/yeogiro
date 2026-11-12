export const CONTACT = {
  name: '여기로 기차예약',
  number: '1666-0926',
  digits: '16660926',
  initial: '여',
}

export function formatDialed(digits: string): string {
  if (/^1\d{7}$/.test(digits)) return `${digits.slice(0, 4)}-${digits.slice(4)}`
  if (/^01\d{8,9}$/.test(digits)) {
    const middle = digits.length === 11 ? 4 : 3
    return `${digits.slice(0, 3)}-${digits.slice(3, 3 + middle)}-${digits.slice(3 + middle)}`
  }
  if (/^02\d{7,8}$/.test(digits)) {
    const middle = digits.length === 10 ? 4 : 3
    return `02-${digits.slice(2, 2 + middle)}-${digits.slice(2 + middle)}`
  }
  return digits
}

export function contactFor(digits: string): { name: string | null; number: string } {
  if (digits === CONTACT.digits) return { name: CONTACT.name, number: CONTACT.number }
  return { name: null, number: formatDialed(digits) }
}
