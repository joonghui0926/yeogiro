import styles from './viz.module.css'

const clamp = (value: number, min = 0, max = 1) => Math.min(max, Math.max(min, value))

interface MeterProps {
  value: number | null
  max: number
  goal: number
  met?: boolean
  goalLabel?: string
}

/** A horizontal gauge: fill to value, a tick at the goal. Empty data shows the track + tick only. */
export function Meter({ value, max, goal, met = true, goalLabel = '목표' }: MeterProps) {
  const fill = value === null ? 0 : clamp(value / max) * 100
  const tick = clamp(goal / max) * 100
  return (
    <div className={styles.meter}>
      <div className={styles.track}>
        {value !== null && (
          <div
            className={styles.fill}
            style={{ width: `${fill}%`, background: met ? 'var(--accent)' : 'var(--warn)' }}
          />
        )}
        <div className={styles.tick} style={{ left: `${tick}%` }} />
      </div>
      <div className={styles.scale}>
        <span>0</span>
        <span className={styles.goalMark} style={{ left: `${tick}%` }}>
          {goalLabel}
        </span>
        <span>{max}</span>
      </div>
    </div>
  )
}

/** Filled area sparkline for a short recent series; a flat dashed baseline when empty. */
export function Sparkline({ values, height = 40 }: { values: number[]; height?: number }) {
  const width = 240
  if (values.length < 2) {
    return (
      <svg className={styles.spark} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden="true">
        <line x1="0" y1={height - 6} x2={width} y2={height - 6} className={styles.baseline} />
      </svg>
    )
  }
  const max = Math.max(...values)
  const min = Math.min(...values)
  const span = max - min || 1
  const step = width / (values.length - 1)
  const y = (v: number) => height - 6 - (clamp((v - min) / span) * (height - 12))
  const pts = values.map((v, i) => `${(i * step).toFixed(1)},${y(v).toFixed(1)}`)
  const line = `M${pts.join(' L')}`
  const area = `${line} L${width},${height} L0,${height} Z`
  return (
    <svg className={styles.spark} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden="true">
      <path d={area} className={styles.sparkArea} />
      <path d={line} className={styles.sparkLine} />
      <circle cx={width} cy={y(values[values.length - 1])} r="3" className={styles.sparkDot} />
    </svg>
  )
}

/** A reserved-status strip: a dot + label, never color alone. */
export function StatusStrip({ good, goodText, badText }: { good: boolean; goodText: string; badText: string }) {
  return (
    <div className={`${styles.status} ${good ? styles.statusGood : styles.statusBad}`}>
      <span className={styles.statusDot} />
      {good ? goodText : badText}
    </div>
  )
}

/** Large ring gauge for the headline rate, with a notch at the goal. */
export function Donut({ value, goal }: { value: number | null; goal: number }) {
  const r = 78
  const c = 2 * Math.PI * r
  const frac = value === null ? 0 : clamp(value / 100)
  const goalAngle = -90 + 360 * clamp(goal / 100)
  const rad = (goalAngle * Math.PI) / 180
  const inner = r - 11
  const outer = r + 11
  const cx = 95
  const cy = 95
  return (
    <svg className={styles.donut} viewBox="0 0 190 190" aria-hidden="true">
      <circle cx={cx} cy={cy} r={r} className={styles.donutTrack} />
      {value !== null && (
        <circle
          cx={cx}
          cy={cy}
          r={r}
          className={styles.donutValue}
          strokeDasharray={`${frac * c} ${c}`}
          transform={`rotate(-90 ${cx} ${cy})`}
        />
      )}
      <line
        x1={cx + inner * Math.cos(rad)}
        y1={cy + inner * Math.sin(rad)}
        x2={cx + outer * Math.cos(rad)}
        y2={cy + outer * Math.sin(rad)}
        className={styles.donutGoal}
      />
      <text x={cx} y={cy - 2} className={styles.donutValueText}>
        {value === null ? '–' : value}
        {value !== null && <tspan className={styles.donutUnit}>%</tspan>}
      </text>
      <text x={cx} y={cy + 24} className={styles.donutCaption}>
        목표 {goal}%
      </text>
    </svg>
  )
}

/** A compact unboxed metric row for the secondary stats beside the hero. */
export function MiniStat({
  label,
  value,
  unit,
  children,
}: {
  label: string
  value: string
  unit?: string
  children: React.ReactNode
}) {
  return (
    <div className={styles.mini}>
      <div className={styles.miniHead}>
        <span className={styles.miniLabel}>{label}</span>
        <span className={styles.miniValue}>
          {value}
          {unit && <span className={styles.miniUnit}>{unit}</span>}
        </span>
      </div>
      <div className={styles.miniViz}>{children}</div>
    </div>
  )
}
