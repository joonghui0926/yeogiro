const DTMF: Record<string, [number, number]> = {
  '1': [697, 1209], '2': [697, 1336], '3': [697, 1477],
  '4': [770, 1209], '5': [770, 1336], '6': [770, 1477],
  '7': [852, 1209], '8': [852, 1336], '9': [852, 1477],
  '*': [941, 1209], '0': [941, 1336], '#': [941, 1477],
}

const RINGBACK_HZ: [number, number] = [440, 480]
const BUSY_HZ: [number, number] = [480, 620]

export class Tones {
  private ctx: AudioContext | null = null

  unlock(): AudioContext {
    if (!this.ctx) this.ctx = new AudioContext({ latencyHint: 'interactive' })
    if (this.ctx.state === 'suspended') void this.ctx.resume()
    return this.ctx
  }

  get context(): AudioContext {
    return this.unlock()
  }

  key(digit: string): void {
    const pair = DTMF[digit]
    if (pair) this.burst(pair, 0, 0.12, 0.08)
    navigator.vibrate?.(15)
  }

  ringback(): () => void {
    const ctx = this.unlock()
    const gain = ctx.createGain()
    gain.gain.value = 0
    gain.connect(ctx.destination)
    const oscillators = RINGBACK_HZ.map((hz) => {
      const osc = ctx.createOscillator()
      osc.frequency.value = hz
      osc.connect(gain)
      osc.start()
      return osc
    })
    const start = ctx.currentTime + 0.05
    for (let cycle = 0; cycle < 20; cycle += 1) {
      const on = start + cycle * 3
      gain.gain.setValueAtTime(0.06, on)
      gain.gain.setValueAtTime(0, on + 1)
    }
    return () => {
      gain.gain.cancelScheduledValues(ctx.currentTime)
      gain.gain.setValueAtTime(0, ctx.currentTime)
      oscillators.forEach((osc) => osc.stop(ctx.currentTime + 0.02))
    }
  }

  hangup(): void {
    for (let i = 0; i < 3; i += 1) this.burst(BUSY_HZ, i * 1, 0.5, 0.06)
  }

  notification(): void {
    this.chime([1318.5, 1760], 0.09)
    navigator.vibrate?.([120, 80, 120])
  }

  payComplete(): void {
    this.chime([987.8, 1318.5, 1975.5], 0.08)
  }

  private chime(notes: number[], step: number): void {
    const ctx = this.unlock()
    notes.forEach((hz, index) => {
      const at = ctx.currentTime + index * step
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.type = 'sine'
      osc.frequency.value = hz
      gain.gain.setValueAtTime(0.0001, at)
      gain.gain.exponentialRampToValueAtTime(0.12, at + 0.01)
      gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.35)
      osc.connect(gain).connect(ctx.destination)
      osc.start(at)
      osc.stop(at + 0.4)
    })
  }

  private burst(pair: [number, number], delay: number, length: number, level: number): void {
    const ctx = this.unlock()
    const at = ctx.currentTime + delay
    const gain = ctx.createGain()
    gain.gain.setValueAtTime(level, at)
    gain.gain.setValueAtTime(0, at + length)
    gain.connect(ctx.destination)
    pair.forEach((hz) => {
      const osc = ctx.createOscillator()
      osc.frequency.value = hz
      osc.connect(gain)
      osc.start(at)
      osc.stop(at + length + 0.02)
    })
  }
}

export const tones = new Tones()

export async function openMicrophone(phoneBand: boolean): Promise<{ track: MediaStreamTrack; stop: () => void }> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
  })
  if (!phoneBand) {
    return { track: stream.getAudioTracks()[0], stop: () => stream.getTracks().forEach((t) => t.stop()) }
  }

  const ctx = tones.context
  const source = ctx.createMediaStreamSource(stream)
  const highpass = new BiquadFilterNode(ctx, { type: 'highpass', frequency: 300, Q: 0.7 })
  const lowpass = new BiquadFilterNode(ctx, { type: 'lowpass', frequency: 3400, Q: 0.7 })
  const destination = ctx.createMediaStreamDestination()
  source.connect(highpass).connect(lowpass).connect(destination)
  return {
    track: destination.stream.getAudioTracks()[0],
    stop: () => {
      source.disconnect()
      stream.getTracks().forEach((t) => t.stop())
    },
  }
}
