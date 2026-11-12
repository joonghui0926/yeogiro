import { useState } from 'react'
import { contactFor } from '../../app/contact'
import type { CallPhase } from '../../call/useCall'
import { tones } from '../../call/tones'
import { Bluetooth, Handset, Keypad, Mute, Person, Record, Speaker, Video } from '../../oneui/icons'
import styles from './call.module.css'

interface Props {
  phase: CallPhase
  digits: string
  elapsed: number
  muted: boolean
  speaker: boolean
  onHangup: () => void
  onMute: () => void
  onSpeaker: () => void
}

export function CallScreen({ phase, digits, elapsed, muted, speaker, onHangup, onMute, onSpeaker }: Props) {
  const [keypad, setKeypad] = useState(false)
  const [tapped, setTapped] = useState('')
  const contact = contactFor(digits)
  const ending = phase === 'ended' || phase === 'failed'

  const status = {
    idle: '',
    dialing: '전화 거는 중…',
    connected: formatElapsed(elapsed),
    ended: '통화 종료',
    failed: '연결할 수 없습니다',
  }[phase]

  return (
    <div className={`screen ${styles.call}`}>
      <div className={styles.head}>
        <h1 className={styles.name}>{contact.name ?? contact.number}</h1>
        {contact.name && <p className={styles.number}>{contact.number}</p>}
        <p className={ending ? styles.statusEnded : styles.status}>{status}</p>
      </div>

      <div className={styles.middle}>
        {keypad ? (
          <div className={styles.inCallKeypad}>
            <div className={styles.tapped}>{tapped}</div>
            {['1', '2', '3', '4', '5', '6', '7', '8', '9', '*', '0', '#'].map((key) => (
              <button
                key={key}
                className={styles.inCallKey}
                onClick={() => {
                  tones.key(key)
                  setTapped((value) => (value + key).slice(-14))
                }}
              >
                {key}
              </button>
            ))}
          </div>
        ) : (
          <div className={styles.avatar}>
            <Person size={72} />
          </div>
        )}
      </div>

      <div className={styles.controls} aria-disabled={phase !== 'connected'}>
        <Control icon={<Record />} label="녹음" />
        <Control icon={<Video />} label="영상통화" />
        <Control icon={<Bluetooth />} label="블루투스" />
        <Control icon={<Speaker />} label="스피커" active={speaker} onClick={onSpeaker} />
        <Control icon={<Mute />} label="음소거" active={muted} onClick={onMute} />
        <Control icon={<Keypad />} label={keypad ? '숨기기' : '키패드'} active={keypad} onClick={() => setKeypad((v) => !v)} />
      </div>

      <div className={styles.endRow}>
        <button className={styles.endButton} onClick={onHangup} disabled={ending} aria-label="통화 종료">
          <Handset size={32} className={styles.endIcon} />
        </button>
      </div>
    </div>
  )
}

function Control({
  icon,
  label,
  active = false,
  onClick,
}: {
  icon: React.ReactNode
  label: string
  active?: boolean
  onClick?: () => void
}) {
  return (
    <button className={styles.control} onClick={onClick}>
      <span className={active ? styles.controlIconActive : styles.controlIcon}>{icon}</span>
      <span className={styles.controlLabel}>{label}</span>
    </button>
  )
}

export function formatElapsed(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  return `${String(minutes).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`
}
