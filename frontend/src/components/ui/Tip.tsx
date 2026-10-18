import type { ReactNode } from 'react'

interface Props {
  text: string
  children: ReactNode
  /** Where the bubble opens relative to the wrapped control. */
  side?: 'top' | 'bottom'
}

/** CSS-only tooltip: shows on hover and keyboard focus, no layout cost. */
export default function Tip({ text, children, side = 'top' }: Props) {
  return (
    <span className={`tip tip-${side}`} data-tip={text}>
      {children}
    </span>
  )
}
