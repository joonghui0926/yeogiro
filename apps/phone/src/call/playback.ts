import { tones } from './tones'

export type PlaybackState = 'waiting' | 'element' | 'webaudio' | 'failed'

export interface Playback {
  attach: (stream: MediaStream) => void
  state: () => PlaybackState
}

// Call this inside the tap handler. Mobile WebViews only let a media element play
// later if its first play() came from a user gesture.
export function unlockPlayback(): Playback {
  const audio = document.getElementById('remote-audio') as HTMLAudioElement
  let state: PlaybackState = 'waiting'
  audio.muted = false
  audio.srcObject = new MediaStream()
  void audio.play().catch(() => undefined)

  return {
    attach(stream) {
      audio.srcObject = stream
      audio.volume = 1
      audio.play().then(
        () => {
          state = 'element'
        },
        () => {
          try {
            audio.muted = true
            const ctx = tones.context
            ctx.createMediaStreamSource(stream).connect(ctx.destination)
            state = 'webaudio'
          } catch {
            state = 'failed'
          }
        },
      )
    },
    state: () => state,
  }
}
