import { useEffect, useState } from 'react'
import type { PlanResponse } from '../../lib/types'
import ComparisonTable from './ComparisonTable'

interface Props {
  plan: PlanResponse
  /** A/B: show the criteria table expanded on first render. */
  defaultOpen: boolean
  onExposed: () => void
  onToggled: () => void
}

export default function Recommendation({ plan, defaultOpen, onExposed, onToggled }: Props) {
  const best = plan.routes.find((r) => r.recommended)
  const blocked = (best?.metrics.no_travel_miles ?? 0) > 0
  const [open, setOpen] = useState(defaultOpen)

  // The visitor has "seen" the variant once the recommendation is on screen.
  useEffect(() => {
    onExposed()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plan])

  return (
    <section className={`recommendation${blocked ? ' blocked' : ''}`} aria-label="Recommendation">
      <span className="eyebrow">{blocked ? 'No safe route' : `Recommended: ${best?.label ?? ''}`}</span>
      <p className="rationale">{plan.recommendation}</p>
      <details
        className="why"
        open={open}
        onToggle={(e) => {
          const next = e.currentTarget.open
          if (next !== open) {
            setOpen(next)
            onToggled()
          }
        }}
      >
        <summary>Why this route?</summary>
        <p className="hint">
          Routes are ranked by No Travel, then Severe miles, High miles, average risk and finally drive time. The best value in each
          row is highlighted.
        </p>
        <ComparisonTable routes={[...plan.routes].sort((a, b) => a.id.localeCompare(b.id))} />
      </details>
      {plan.notes.map((n) => (
        <p key={n} className="hint note">
          {n}
        </p>
      ))}
    </section>
  )
}
