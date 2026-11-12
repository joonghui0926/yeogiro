import { RAIL_MODE_LABEL } from '@yeogiro/contracts'
import { signOut } from 'firebase/auth'
import type { ReactNode } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { auth } from '../app/firebase'
import { useCalls, useFlags } from '../data/hooks'
import styles from './layout.module.css'

const NAV: Array<{ to: string; label: string; icon: ReactNode; end?: boolean }> = [
  { to: '/', label: '개요', end: true, icon: <path d="M4 13h6V4H4zm10 7h6V11h-6zM4 20h6v-4H4zm10-11h6V4h-6z" /> },
  { to: '/calls', label: '통화', icon: <path d="M6.6 10.8a15 15 0 0 0 6.6 6.6l2.2-2.2c.3-.3.7-.4 1-.2 1.1.4 2.3.6 3.6.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1A17 17 0 0 1 3 4c0-.6.4-1 1-1h3.4c.6 0 1 .4 1 1 0 1.3.2 2.5.6 3.6.1.3 0 .7-.2 1z" /> },
  { to: '/live', label: '실시간', icon: <path d="M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7zM5 12a7 7 0 0 1 2-4.9M19 12a7 7 0 0 0-2-4.9M5 12a7 7 0 0 0 2 4.9M19 12a7 7 0 0 1-2 4.9" /> },
  { to: '/testers', label: '테스터', icon: <path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm-7 8a7 7 0 0 1 14 0" /> },
]

export function Layout() {
  const [flags] = useFlags()
  const calls = useCalls(20)
  const live = calls?.filter((call) => call.status === 'live').length ?? 0

  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <div className={styles.brand}>
          <img src="/console/icons/icon-64.png" alt="" width={32} height={32} />
          <span>
            여기로
            <em>운영</em>
          </span>
        </div>
        <nav className={styles.nav}>
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => (isActive ? styles.navOn : styles.navItem)}>
              <NavIcon>{item.icon}</NavIcon>
              {item.label}
              {item.to === '/live' && live > 0 && <span className={styles.badge}>{live}</span>}
            </NavLink>
          ))}
        </nav>
        <div className={styles.status}>
          <span className={styles.statusLabel}>지금 설정</span>
          <span>{RAIL_MODE_LABEL[flags.railMode]}</span>
          <span className={flags.bookingEnabled ? styles.on : styles.off}>
            {flags.bookingEnabled ? '예약 받는 중' : '예약 멈춤'}
          </span>
          <button className={styles.signOut} onClick={() => void signOut(auth)}>
            {(auth.currentUser?.email ?? '').split('@')[0].toUpperCase() || '운영자'} · 로그아웃
          </button>
        </div>
      </aside>

      <main className={styles.main}>
        <Outlet />
      </main>

      <nav className={styles.tabbar}>
        {NAV.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => (isActive ? styles.tabOn : styles.tab)}>
            <NavIcon>{item.icon}</NavIcon>
            <span>{item.label}</span>
            {item.to === '/live' && live > 0 && <span className={styles.tabBadge} />}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}

function NavIcon({ children }: { children: ReactNode }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {children}
    </svg>
  )
}
