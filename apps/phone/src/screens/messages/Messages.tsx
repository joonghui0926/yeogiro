import type { InboxMessage } from '@yeogiro/contracts'
import { useEffect, useRef } from 'react'
import { CONTACT } from '../../app/contact'
import { Back, Handset, Mic, More, Plus, Search, Smile } from '../../oneui/icons'
import styles from './messages.module.css'

interface Props {
  messages: InboxMessage[]
  thread: boolean
  onOpenThread: () => void
  onBack: () => void
  onCall: () => void
}

export function Messages({ messages, thread, onOpenThread, onBack, onCall }: Props) {
  return thread ? (
    <Thread messages={messages} onBack={onBack} onCall={onCall} />
  ) : (
    <Conversations messages={messages} onOpen={onOpenThread} onBack={onBack} />
  )
}

function Conversations({
  messages,
  onOpen,
  onBack,
}: {
  messages: InboxMessage[]
  onOpen: () => void
  onBack: () => void
}) {
  const last = messages.at(-1)
  return (
    <div className={`screen ${styles.list}`}>
      <div className={styles.largeTitle}>
        <h1>메시지</h1>
      </div>
      <header className={styles.toolbar}>
        <button className={styles.icon} onClick={onBack} aria-label="뒤로">
          <Back />
        </button>
        <span className={styles.toolbarRight}>
          <button className={styles.icon} aria-label="검색">
            <Search />
          </button>
          <button className={styles.icon} aria-label="더보기">
            <More />
          </button>
        </span>
      </header>
      <div className={styles.conversations}>
        {last ? (
          <button className={styles.conversation} onClick={onOpen}>
            <span className={styles.avatar}>{CONTACT.initial}</span>
            <span className={styles.conversationText}>
              <strong>{last.sender}</strong>
              <em>{last.body.replace(/\n/g, ' ')}</em>
            </span>
            <span className={styles.conversationTime}>{shortTime(last.sentAt)}</span>
          </button>
        ) : (
          <p className={styles.empty}>메시지 없음</p>
        )}
      </div>
    </div>
  )
}

function Thread({ messages, onBack, onCall }: { messages: InboxMessage[]; onBack: () => void; onCall: () => void }) {
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length])

  return (
    <div className={`screen ${styles.thread}`}>
      <header className={styles.appbar}>
        <button className={styles.icon} onClick={onBack} aria-label="뒤로">
          <Back />
        </button>
        <span className={styles.title}>
          <strong>{messages[0]?.sender ?? '여기로'}</strong>
        </span>
        <button className={styles.icon} onClick={onCall} aria-label="전화">
          <Handset size={22} />
        </button>
        <button className={styles.icon} aria-label="더보기">
          <More />
        </button>
      </header>

      <div className={styles.bubbles}>
        {groupByDay(messages).map(([day, items]) => (
          <section key={day}>
            <p className={styles.day}>{day}</p>
            {items.map((message) => (
              <div key={message.id} className={styles.incoming}>
                <span className={styles.bubbleAvatar}>{CONTACT.initial}</span>
                <div className={styles.bubbleColumn}>
                  <p className={styles.bubble}>{message.body}</p>
                  <span className={styles.time}>{shortTime(message.sentAt)}</span>
                </div>
              </div>
            ))}
          </section>
        ))}
        <div ref={end} />
      </div>

      <footer className={styles.composer}>
        <button className={styles.composerPlus} aria-label="첨부">
          <Plus size={22} />
        </button>
        <div className={styles.input}>
          <span>메시지 입력</span>
          <Smile size={22} />
        </div>
        <button className={styles.icon} aria-label="음성 입력">
          <Mic size={22} />
        </button>
      </footer>
    </div>
  )
}

function groupByDay(messages: InboxMessage[]): Array<[string, InboxMessage[]]> {
  const groups = new Map<string, InboxMessage[]>()
  for (const message of messages) {
    const date = new Date(message.sentAt)
    const key = date.toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      weekday: 'long',
    })
    groups.set(key, [...(groups.get(key) ?? []), message])
  }
  return [...groups.entries()]
}

export function shortTime(iso: string): string {
  const date = new Date(iso)
  const hour = date.getHours()
  return `${hour < 12 ? '오전' : '오후'} ${hour % 12 || 12}:${String(date.getMinutes()).padStart(2, '0')}`
}
