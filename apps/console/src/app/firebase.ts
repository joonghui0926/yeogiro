import { initializeApp } from 'firebase/app'
import { getAuth } from 'firebase/auth'
import { getFirestore } from 'firebase/firestore'

const app = initializeApp({
  apiKey: 'AIzaSyDfQmb02dQCGXoL4a3SkCYHnaQsvrG3UpM',
  authDomain: 'yeogiro-kaist.firebaseapp.com',
  projectId: 'yeogiro-kaist',
  storageBucket: 'yeogiro-kaist.firebasestorage.app',
  messagingSenderId: '990320254644',
  appId: '1:990320254644:web:79cdfd2b6aaf9d20a741e1',
})

export const auth = getAuth(app)
export const db = getFirestore(app)

export const PHONE_ORIGIN = 'https://yeogiro-kaist.web.app'
