import { collection, deleteDoc, doc, getDocs, query, where, writeBatch } from 'firebase/firestore'
import { db } from '../app/firebase'

const BATCH_LIMIT = 400

export async function deleteCallRecord(callId: string): Promise<void> {
  const callRef = doc(db, 'calls', callId)
  const [events, bookings, payments] = await Promise.all([
    getDocs(collection(callRef, 'events')),
    getDocs(query(collection(db, 'bookings'), where('callId', '==', callId))),
    getDocs(query(collection(db, 'payments'), where('callId', '==', callId))),
  ])
  const refs = [...events.docs, ...bookings.docs, ...payments.docs].map((snapshot) => snapshot.ref)
  for (let start = 0; start < refs.length; start += BATCH_LIMIT) {
    const batch = writeBatch(db)
    refs.slice(start, start + BATCH_LIMIT).forEach((ref) => batch.delete(ref))
    await batch.commit()
  }
  await deleteDoc(callRef)
}
