import { onAuthStateChanged, signInAnonymously, type User } from 'firebase/auth'
import { useEffect, useState } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Layout } from '../components/Layout'
import { CallDetail } from '../pages/CallDetail'
import { Calls } from '../pages/Calls'
import { Live } from '../pages/Live'
import { Overview } from '../pages/Overview'
import { Testers } from '../pages/Testers'
import { auth } from './firebase'
import { isDemo } from '../data/demo'
import styles from './gate.module.css'

export function App() {
  const [user, setUser] = useState<User | null | undefined>(undefined)
  const [failed, setFailed] = useState(false)

  useEffect(
    () =>
      onAuthStateChanged(auth, (next) => {
        setUser(next)
        if (!next && !isDemo()) signInAnonymously(auth).catch(() => setFailed(true))
      }),
    [],
  )

  if (!isDemo() && !user) {
    return (
      <div className={styles.center}>
        {failed && <p className={styles.error}>콘솔에 연결하지 못했어요. 새로고침해 주세요.</p>}
      </div>
    )
  }

  return (
    <BrowserRouter basename="/console">
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Overview />} />
          <Route path="calls" element={<Calls />} />
          <Route path="calls/:callId" element={<CallDetail />} />
          <Route path="live" element={<Live />} />
          <Route path="testers" element={<Testers />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
