import { useState } from 'react'
import { CONTACT, contactFor, formatDialed } from '../../app/contact'
import type { RecentCall } from '../../app/recents'
import { tones } from '../../call/tones'
import { Backspace, Handset, More, Outgoing, Person, Search, Video } from '../../oneui/icons'
import styles from './dialer.module.css'

export type DialerTab = 'keypad' | 'recents' | 'contacts'

const KEYS: Array<[string, string]> = [
  ['1', 'oo'], ['2', 'ABC'], ['3', 'DEF'],
  ['4', 'GHI'], ['5', 'JKL'], ['6', 'MNO'],
  ['7', 'PQRS'], ['8', 'TUV'], ['9', 'WXYZ'],
  ['*', ''], ['0', '+'], ['#', ''],
]

interface Props {
  tab: DialerTab
  recents: RecentCall[]
  onTab: (tab: DialerTab) => void
  onDial: (digits: string) => void
  onOpenMessages: () => void
}

export function Dialer({ tab, recents, onTab, onDial, onOpenMessages }: Props) {
  return (
    <div className={`screen ${styles.dialer}`}>
      {tab === 'keypad' && <KeypadTab onDial={onDial} onOpenMessages={onOpenMessages} />}
      {tab === 'recents' && <RecentsTab recents={recents} onDial={onDial} />}
      {tab === 'contacts' && <ContactsTab onDial={onDial} />}
      <nav className={styles.tabs}>
        {(
          [
            ['keypad', '키패드'],
            ['recents', '최근기록'],
            ['contacts', '연락처'],
          ] as const
        ).map(([key, label]) => (
          <button key={key} className={tab === key ? styles.tabActive : styles.tab} onClick={() => onTab(key)}>
            {label}
          </button>
        ))}
      </nav>
    </div>
  )
}

function KeypadTab({ onDial, onOpenMessages }: { onDial: (digits: string) => void; onOpenMessages: () => void }) {
  const [digits, setDigits] = useState('')
  const [menu, setMenu] = useState(false)
  const suggestion = digits.length >= 2 && CONTACT.digits.startsWith(digits) ? CONTACT : null

  const press = (key: string) => {
    tones.key(key)
    setDigits((value) => (value.length < 15 ? value + key : value))
  }
  const call = () => {
    if (!digits) return
    onDial(digits)
    setDigits('')
  }

  return (
    <>
      <header className={styles.topbar}>
        <span />
        <button className={styles.iconButton} aria-label="더보기" onClick={() => setMenu((open) => !open)}>
          <More />
        </button>
        {menu && (
          <div className={styles.menu} role="menu">
            <button role="menuitem" onClick={() => { setMenu(false); onOpenMessages() }}>
              메시지
            </button>
            <button role="menuitem" onClick={() => setMenu(false)}>
              설정
            </button>
          </div>
        )}
      </header>

      <div className={styles.display}>
        <div className={digits.length > 11 ? styles.numberSmall : styles.number}>{formatDialed(digits)}</div>
        {suggestion ? (
          <button className={styles.suggestion} onClick={() => setDigits(CONTACT.digits)}>
            <span className={styles.suggestionAvatar}>{CONTACT.initial}</span>
            <span>
              <strong>{CONTACT.name}</strong>
              <em>{CONTACT.number}</em>
            </span>
          </button>
        ) : (
          digits && <button className={styles.addContact}>연락처에 추가</button>
        )}
      </div>

      <div className={styles.keypad}>
        {KEYS.map(([key, letters]) => (
          <button key={key} className={styles.key} onClick={() => press(key)}>
            <span className={key === '*' || key === '#' ? styles.symbol : styles.digit}>{key}</span>
            <span className={styles.letters}>{letters}</span>
          </button>
        ))}
      </div>

      <div className={styles.actions}>
        <button className={styles.sideAction} aria-label="영상통화">
          <Video />
        </button>
        <button className={styles.callButton} onClick={call} aria-label="통화">
          <Handset size={30} />
        </button>
        <button
          className={styles.sideAction}
          style={{ visibility: digits ? 'visible' : 'hidden' }}
          onClick={() => setDigits((value) => value.slice(0, -1))}
          onContextMenu={(event) => {
            event.preventDefault()
            setDigits('')
          }}
          aria-label="지우기"
        >
          <Backspace />
        </button>
      </div>
    </>
  )
}

function RecentsTab({ recents, onDial }: { recents: RecentCall[]; onDial: (digits: string) => void }) {
  return (
    <>
      <header className={styles.topbar}>
        <span />
        <span className={styles.topActions}>
          <button className={styles.iconButton} aria-label="검색">
            <Search />
          </button>
          <button className={styles.iconButton} aria-label="더보기">
            <More />
          </button>
        </span>
      </header>
      <div className={styles.list}>
        {recents.length === 0 && <p className={styles.empty}>최근기록 없음</p>}
        {groupByDay(recents).map(([day, calls]) => (
          <section key={day}>
            <h3 className={styles.groupLabel}>{day}</h3>
            <div className={styles.group}>
              {calls.map((call) => {
                const contact = contactFor(call.digits)
                return (
                  <button key={call.at} className={styles.row} onClick={() => onDial(call.digits)}>
                    <Avatar name={contact.name} />
                    <span className={styles.rowText}>
                      <strong>{contact.name ?? contact.number}</strong>
                      <em>
                        <Outgoing size={14} className={styles.outgoing} />
                        {contact.name ? contact.number : '휴대전화'}
                      </em>
                    </span>
                    <span className={styles.rowTime}>{clock(call.at)}</span>
                  </button>
                )
              })}
            </div>
          </section>
        ))}
      </div>
    </>
  )
}

function ContactsTab({ onDial }: { onDial: (digits: string) => void }) {
  return (
    <>
      <div className={styles.largeTitle}>
        <h1>연락처</h1>
        <p>전화번호가 저장된 연락처 1개</p>
      </div>
      <header className={styles.topbar}>
        <span />
        <span className={styles.topActions}>
          <button className={styles.iconButton} aria-label="검색">
            <Search />
          </button>
          <button className={styles.iconButton} aria-label="더보기">
            <More />
          </button>
        </span>
      </header>
      <div className={styles.list}>
        <h3 className={styles.groupLabel}>ㅇ</h3>
        <div className={styles.group}>
          <button className={styles.row} onClick={() => onDial(CONTACT.digits)}>
            <Avatar name={CONTACT.name} />
            <span className={styles.rowText}>
              <strong>{CONTACT.name}</strong>
            </span>
          </button>
        </div>
      </div>
    </>
  )
}

function Avatar({ name }: { name: string | null }) {
  return name ? (
    <span className={styles.avatar}>{name.slice(0, 1)}</span>
  ) : (
    <span className={`${styles.avatar} ${styles.avatarUnknown}`}>
      <Person size={22} />
    </span>
  )
}

function groupByDay(calls: RecentCall[]): Array<[string, RecentCall[]]> {
  const groups = new Map<string, RecentCall[]>()
  const today = new Date().toDateString()
  const yesterday = new Date(Date.now() - 86_400_000).toDateString()
  for (const call of calls) {
    const date = new Date(call.at)
    const key =
      date.toDateString() === today
        ? '오늘'
        : date.toDateString() === yesterday
          ? '어제'
          : `${date.getMonth() + 1}월 ${date.getDate()}일`
    groups.set(key, [...(groups.get(key) ?? []), call])
  }
  return [...groups.entries()]
}

function clock(at: number): string {
  const date = new Date(at)
  const hour = date.getHours()
  const period = hour < 12 ? '오전' : '오후'
  return `${period} ${hour % 12 || 12}:${String(date.getMinutes()).padStart(2, '0')}`
}
