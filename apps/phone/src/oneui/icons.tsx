import type { SVGProps } from 'react'

type IconProps = SVGProps<SVGSVGElement> & { size?: number }

function Svg({ size = 24, children, ...rest }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true" {...rest}>
      {children}
    </svg>
  )
}

const stroke = { stroke: 'currentColor', strokeWidth: 1.6, strokeLinecap: 'round', strokeLinejoin: 'round' } as const

export const Handset = (p: IconProps) => (
  <Svg {...p}>
    <path
      fill="currentColor"
      d="M6.6 10.8a15.1 15.1 0 0 0 6.6 6.6l2.2-2.2c.3-.3.7-.4 1-.2 1.1.4 2.3.6 3.6.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1A17 17 0 0 1 3 4c0-.6.4-1 1-1h3.4c.6 0 1 .4 1 1 0 1.3.2 2.5.6 3.6.1.3 0 .7-.2 1z"
    />
  </Svg>
)

export const Video = (p: IconProps) => (
  <Svg {...p}>
    <rect x="3" y="6.5" width="12.5" height="11" rx="2.5" {...stroke} />
    <path d="M15.5 10.5 21 7.5v9l-5.5-3" {...stroke} />
  </Svg>
)

export const Backspace = (p: IconProps) => (
  <Svg {...p}>
    <path d="M8.5 5.5H20a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H8.5L3 12z" {...stroke} />
    <path d="m11.5 9.5 5 5m0-5-5 5" {...stroke} />
  </Svg>
)

export const More = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="5.5" r="1.6" fill="currentColor" />
    <circle cx="12" cy="12" r="1.6" fill="currentColor" />
    <circle cx="12" cy="18.5" r="1.6" fill="currentColor" />
  </Svg>
)

export const Search = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="10.5" cy="10.5" r="6" {...stroke} />
    <path d="m15 15 5 5" {...stroke} />
  </Svg>
)

export const Record = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8" {...stroke} />
    <circle cx="12" cy="12" r="3.2" fill="currentColor" />
  </Svg>
)

export const Bluetooth = (p: IconProps) => (
  <Svg {...p}>
    <path d="m7 7.5 10 9-5 4.5v-18l5 4.5-10 9" {...stroke} />
  </Svg>
)

export const Speaker = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z" {...stroke} />
    <path d="M15.5 9a4.2 4.2 0 0 1 0 6M18 6.5a8 8 0 0 1 0 11" {...stroke} />
  </Svg>
)

export const Mute = (p: IconProps) => (
  <Svg {...p}>
    <rect x="9" y="3.5" width="6" height="11" rx="3" {...stroke} />
    <path d="M6 11a6 6 0 0 0 12 0M12 17v3.5M4 4l16 16" {...stroke} />
  </Svg>
)

export const Keypad = (p: IconProps) => (
  <Svg {...p}>
    {[6, 12, 18].flatMap((x) =>
      [5, 10.5, 16].map((y) => <circle key={`${x}-${y}`} cx={x} cy={y} r="1.5" fill="currentColor" />),
    )}
    <circle cx="12" cy="21" r="1.5" fill="currentColor" />
  </Svg>
)

export const Back = (p: IconProps) => (
  <Svg {...p}>
    <path d="M15 5 8 12l7 7" {...stroke} strokeWidth={1.9} />
  </Svg>
)

export const Plus = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 5v14M5 12h14" {...stroke} />
  </Svg>
)

export const Smile = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.5" {...stroke} />
    <path d="M8.5 14a4.5 4.5 0 0 0 7 0" {...stroke} />
    <circle cx="9.3" cy="10" r="1" fill="currentColor" />
    <circle cx="14.7" cy="10" r="1" fill="currentColor" />
  </Svg>
)

export const Mic = (p: IconProps) => (
  <Svg {...p}>
    <rect x="9" y="3.5" width="6" height="11" rx="3" {...stroke} />
    <path d="M6 11a6 6 0 0 0 12 0M12 17v3.5" {...stroke} />
  </Svg>
)

export const Person = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="8.5" r="4.2" fill="currentColor" />
    <path d="M3.8 21a8.2 8.2 0 0 1 16.4 0z" fill="currentColor" />
  </Svg>
)

export const Outgoing = (p: IconProps) => (
  <Svg {...p}>
    <path d="M7 17 17 7M9 7h8v8" {...stroke} />
  </Svg>
)

export const Check = (p: IconProps) => (
  <Svg {...p}>
    <path d="m5 12.5 4.5 4.5L19 7.5" {...stroke} strokeWidth={2.4} />
  </Svg>
)

export const Close = (p: IconProps) => (
  <Svg {...p}>
    <path d="M6 6l12 12M18 6 6 18" {...stroke} strokeWidth={1.9} />
  </Svg>
)

export const Fingerprint = (p: IconProps) => (
  <Svg {...p}>
    <path
      d="M12 11v3.5a6 6 0 0 1-1.5 4M8.5 9.5A4 4 0 0 1 16 11v2.5m-7.5-1V11a3.5 3.5 0 0 1 .3-1.4M5 13.5V11a7 7 0 0 1 12.6-4.2M19 11v1.5M15.8 16.5a9 9 0 0 1-.8 3"
      {...stroke}
    />
  </Svg>
)

export const MessageBubble = (p: IconProps) => (
  <Svg {...p}>
    <path
      fill="currentColor"
      d="M12 4c4.7 0 8.5 3.1 8.5 7s-3.8 7-8.5 7c-.8 0-1.6-.1-2.3-.3L5.5 20l1-3.4A6.6 6.6 0 0 1 3.5 11c0-3.9 3.8-7 8.5-7z"
    />
  </Svg>
)

export const Store = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4 9.5 5.5 5h13L20 9.5M4 9.5h16M4 9.5a2.7 2.7 0 0 0 5.3 0 2.7 2.7 0 0 0 5.4 0 2.7 2.7 0 0 0 5.3 0M5.5 12v7h13v-7" {...stroke} />
  </Svg>
)
