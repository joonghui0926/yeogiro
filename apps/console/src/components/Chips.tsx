import { OUTCOME_LABEL, RAIL_MODE_LABEL, STATE_LABEL, type CallDoc } from '@yeogiro/contracts'
import styles from './ui.module.css'

export function OutcomeChip({ call }: { call: CallDoc }) {
  if (call.status === 'live') {
    return (
      <span className={`${styles.chip} ${styles.chipInfo}`}>
        <span className={styles.liveDot} />
        {STATE_LABEL[call.state]}
      </span>
    )
  }
  const outcome = call.outcome ?? 'abandoned'
  const tone =
    outcome === 'booked'
      ? styles.chipGood
      : outcome === 'declined'
        ? ''
        : outcome === 'no_consent'
          ? styles.chipBad
          : styles.chipWarn
  return <span className={`${styles.chip} ${tone}`}>{OUTCOME_LABEL[outcome]}</span>
}

export function ModeChip({ call }: { call: CallDoc }) {
  const source = call.booking?.provider ?? call.railSource
  const label = source === 'korail' ? '코레일 실예약' : RAIL_MODE_LABEL[call.railMode]
  return <span className={styles.chip}>{label}</span>
}
