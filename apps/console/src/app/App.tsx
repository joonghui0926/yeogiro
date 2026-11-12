import {
  createUserWithEmailAndPassword,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signOut,
  type User,
} from 'firebase/auth'
import { FormEvent, useEffect, useState } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Layout } from '../components/Layout'
import ui from '../components/ui.module.css'
import { CallDetail } from '../pages/CallDetail'
import { Calls } from '../pages/Calls'
import { Live } from '../pages/Live'
import { Overview } from '../pages/Overview'
import { Testers } from '../pages/Testers'
import { auth } from './firebase'
import { isDemo } from '../data/demo'
import styles from './gate.module.css'

const EMAIL_DOMAIN = 'yeogiro.local'

export function App() {
  const [user, setUser] = useState<User | null | undefined>(undefined)

  useEffect(() => onAuthStateChanged(auth, setUser), [])

  if (!isDemo()) {
    if (user === undefined) return <div className={styles.center} />
    if (!user) return <Login />
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

function Login() {
  const [id, setId] = useState('')
  const [pw, setPw] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!id.trim() || !pw) return
    setBusy(true)
    setError('')
    const email = `${id.trim().toLowerCase()}@${EMAIL_DOMAIN}`
    try {
      await signInWithEmailAndPassword(auth, email, pw)
    } catch {
      try {
        await createUserWithEmailAndPassword(auth, email, pw)
      } catch (create) {
        setError(
          (create as { code?: string }).code === 'auth/email-already-in-use'
            ? '비밀번호가 맞지 않아요.'
            : '로그인하지 못했어요. 아이디와 비밀번호를 확인해 주세요.',
        )
        setBusy(false)
      }
    }
  }

  return (
    <div className={styles.center}>
      <form className={styles.gate} onSubmit={submit}>
        <img src="/console/icons/icon-192.png" alt="" width={64} height={64} />
        <h1>여기로 운영</h1>
        <p>운영 아이디로 로그인하세요.</p>
        <input
          className={ui.input}
          placeholder="아이디"
          value={id}
          onChange={(e) => setId(e.target.value)}
          autoCapitalize="off"
          autoCorrect="off"
          autoComplete="username"
        />
        <input
          className={ui.input}
          type="password"
          placeholder="비밀번호"
          value={pw}
          onChange={(e) => setPw(e.target.value)}
          autoComplete="current-password"
        />
        {error && <p className={styles.error}>{error}</p>}
        <button className={ui.buttonPrimary} type="submit" disabled={busy}>
          {busy ? '들어가는 중…' : '로그인'}
        </button>
      </form>
    </div>
  )
}

export function signOutConsole() {
  void signOut(auth)
}
