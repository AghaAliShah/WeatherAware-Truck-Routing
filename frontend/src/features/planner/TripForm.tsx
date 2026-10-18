import { useState } from 'react'
import { defaultDeparture, toLocalInputValue } from '../../lib/format'
import type { Place, PlanRequest } from '../../lib/types'
import Segmented from '../../components/ui/Segmented'
import Tip from '../../components/ui/Tip'
import LocationInput from './LocationInput'

interface Props {
  busy: boolean
  initial: PlanRequest | null
  onSubmit: (req: PlanRequest) => void
}

const EXAMPLE: { origin: Place; destination: Place } = {
  origin: { label: 'Chicago, Illinois', lat: 41.8755616, lon: -87.6244212 },
  destination: { label: 'Denver, Colorado', lat: 39.7392364, lon: -104.984862 },
}

const LOAD_PRESETS = [
  { label: 'Empty', lb: 10000 },
  { label: 'Light', lb: 25000 },
  { label: 'Typical', lb: 40000 },
  { label: 'Heavy', lb: 60000 },
  { label: 'Max', lb: 80000 },
] as const

const DEPARTURE_PRESETS: readonly { label: string; at: () => Date }[] = [
  { label: 'In 1 h', at: () => new Date(Date.now() + 3_600_000) },
  { label: 'In 6 h', at: () => new Date(Date.now() + 6 * 3_600_000) },
  {
    label: 'Tomorrow 6 AM',
    at: () => {
      const d = new Date()
      d.setDate(d.getDate() + 1)
      d.setHours(6, 0, 0, 0)
      return d
    },
  },
]

type Spacing = 'auto' | '10' | '25' | '50'
const SPACING_OPTIONS = [
  { value: 'auto', label: 'Auto', hint: '10 mi under 150 mi trips, 25 mi to 500 mi, else 50 mi' },
  { value: '10', label: '10 mi' },
  { value: '25', label: '25 mi' },
  { value: '50', label: '50 mi' },
] as const

/** Plain-language summary of which wind rules the entered load triggers. */
function loadHint(lb: number): string {
  if (lb > 40000) return 'Over 40,000 lb: 35+ mph wind is Severe, 45+ mph is No Travel.'
  if (lb > 30000) return 'Over 30,000 lb: 45+ mph wind is No Travel.'
  return 'No load rule applies. Only 55+ mph wind is No Travel.'
}

export default function TripForm({ busy, initial, onSubmit }: Props) {
  const [origin, setOrigin] = useState<Place | null>(initial?.origin ?? null)
  const [destination, setDestination] = useState<Place | null>(initial?.destination ?? null)
  const [departure, setDeparture] = useState(() => (initial ? toLocalInputValue(new Date(initial.departure)) : defaultDeparture()))
  const [load, setLoad] = useState(String(initial?.load_lb ?? 40000))
  const [spacing, setSpacing] = useState<Spacing>(initial?.interval_mi ? (String(initial.interval_mi) as Spacing) : 'auto')
  const [error, setError] = useState('')

  const loadNum = Number(load)

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const when = new Date(departure)
    if (!origin || !destination) return setError('Choose an origin and a destination from the suggestions.')
    if (Number.isNaN(when.getTime())) return setError('Enter a valid departure date and time.')
    if (!Number.isInteger(loadNum) || loadNum < 0 || loadNum > 150000)
      return setError('Load weight must be a whole number between 0 and 150,000 lb.')
    setError('')
    onSubmit({
      origin,
      destination,
      departure: when.toISOString(),
      load_lb: loadNum,
      interval_mi: spacing === 'auto' ? null : (Number(spacing) as 10 | 25 | 50),
    })
  }

  return (
    <form className="trip-form" onSubmit={submit} noValidate>
      <div className="stops">
        <LocationInput label="Origin" marker="A" value={origin} onChange={setOrigin} placeholder="City or address" />
        <LocationInput label="Destination" marker="B" value={destination} onChange={setDestination} placeholder="City or address" />
        <Tip text="Swap origin and destination">
          <button
            type="button"
            className="swap"
            aria-label="Swap origin and destination"
            onClick={() => {
              setOrigin(destination)
              setDestination(origin)
            }}
          >
            <svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M7 16V4M3.5 7.5 7 4l3.5 3.5" />
              <path d="M13 4v12M9.5 12.5 13 16l3.5-3.5" />
            </svg>
          </button>
        </Tip>
      </div>

      <div className="field">
        <label htmlFor="departure">Departure (local time)</label>
        <input id="departure" className="input" type="datetime-local" value={departure} onChange={(e) => setDeparture(e.target.value)} required />
        <div className="chips" role="group" aria-label="Departure shortcuts">
          {DEPARTURE_PRESETS.map((p) => (
            <button key={p.label} type="button" className="chip" onClick={() => setDeparture(toLocalInputValue(p.at()))}>
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <div className="field">
        <label htmlFor="load">Load weight (lb)</label>
        <input
          id="load"
          className="input tabular"
          type="number"
          inputMode="numeric"
          min={0}
          max={150000}
          step={500}
          value={load}
          onChange={(e) => setLoad(e.target.value)}
          required
        />
        <div className="chips" role="group" aria-label="Load presets">
          {LOAD_PRESETS.map((p) => (
            <button
              key={p.lb}
              type="button"
              className={`chip${loadNum === p.lb ? ' on' : ''}`}
              onClick={() => setLoad(String(p.lb))}
              title={`${p.lb.toLocaleString()} lb`}
            >
              {p.label}
            </button>
          ))}
        </div>
        {Number.isFinite(loadNum) && <div className="hint rule-hint">{loadHint(loadNum)}</div>}
      </div>

      <div className="field">
        <span className="field-label">Checkpoint spacing</span>
        <Segmented label="Checkpoint spacing" value={spacing} options={SPACING_OPTIONS} onChange={setSpacing} />
      </div>

      {error && (
        <p className="error-text" role="alert">
          {error}
        </p>
      )}

      <div className="form-actions">
        <button type="submit" className="btn primary grow" disabled={busy}>
          {busy ? 'Planning route...' : 'Find safest route'}
        </button>
        <button
          type="button"
          className="btn ghost"
          disabled={busy}
          onClick={() => {
            setOrigin(EXAMPLE.origin)
            setDestination(EXAMPLE.destination)
            setError('')
          }}
        >
          Example
        </button>
      </div>
    </form>
  )
}
