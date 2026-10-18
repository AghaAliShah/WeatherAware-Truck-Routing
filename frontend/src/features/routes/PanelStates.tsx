import { useEffect, useState } from 'react'
import Skeleton from '../../components/ui/Skeleton'

const STEPS = [
  { label: 'Finding three routes', after: 0 },
  { label: 'Timing every checkpoint', after: 5 },
  { label: 'Fetching the forecast for each ETA', after: 9 },
  { label: 'Scoring risk and ranking', after: 16 },
] as const

/** Phases are inferred from elapsed time: the server does the work in one request. */
export function PlanningState() {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => clearInterval(t)
  }, [])
  const current = STEPS.reduce((acc, s, i) => (seconds >= s.after ? i : acc), 0)

  return (
    <div className="panel-state" role="status" aria-live="polite">
      <ol className="phases">
        {STEPS.map((s, i) => (
          <li key={s.label} className={i < current ? 'done' : i === current ? 'now' : ''}>
            <span className="phase-mark">{i < current ? '✓' : i === current ? <span className="spinner" /> : ''}</span>
            {s.label}
          </li>
        ))}
      </ol>
      <div className="skeleton-card">
        <Skeleton height={14} width="45%" />
        <Skeleton height={10} width="70%" />
        <Skeleton height={34} />
        <Skeleton height={10} width="85%" />
      </div>
      <div className="skeleton-card">
        <Skeleton height={14} width="40%" />
        <Skeleton height={10} width="65%" />
        <Skeleton height={34} />
      </div>
    </div>
  )
}

export function EmptyState() {
  return (
    <div className="panel-state empty-state">
      <h2>Plan around the weather</h2>
      <p className="hint">Enter a trip to compare three routes by the forecast at your arrival time at every checkpoint.</p>
      <ul>
        <li>
          <b>Forecast at your ETA</b>, not at departure
        </li>
        <li>
          <b>Load-aware</b> wind rules for heavy trailers
        </li>
        <li>
          <b>48-hour slider</b> to watch weather move across the corridor
        </li>
      </ul>
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="panel-state error-state" role="alert">
      <h2>Could not plan this trip</h2>
      <p>{message}</p>
      <button type="button" className="btn sm" onClick={onRetry}>
        Edit and retry
      </button>
    </div>
  )
}
